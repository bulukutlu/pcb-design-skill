#!/usr/bin/env python3
"""Post-route trace clean-up for KiCad boards (G6 step 6 of the pcb-design skill).

    trace_cleanup.py <in.kicad_pcb> -o <out.kicad_pcb> [--report report.md]
                     [--fine-pitch 0.5] [--min-chamfer MM] [--max-chamfer MM]
                     [--refill] [--skip-locked] [--extra-clearance 'GLOB_A=GLOB_B:MM' ...]
                     [--dry-run]

Finds and fixes, per net and copper layer, on straight track segments only (arcs, pads,
vias, footprints and zones are never moved):

  (a) jogs, doglegs, U-turns and detours that no obstacle forces: the chain between two
      terminals (pad, via, junction, free end) is rebuilt with the fewest octilinear bends
      whose new copper clears every other-net item by the net-class clearance;
  (b) collinear chains: consecutive segments in one direction are merged;
  (c) dangling stubs: track ends that touch no copper of their own net are removed;
  (d) 90-degree corners: chamfered to 45 degrees with the largest leg that clears
      (between --min-chamfer and --max-chamfer).

Fine-pitch pad rows (pads <= --fine-pitch apart in one footprint) get no new diagonal
copper inside them plus a margin: parallel 45-degree fan-outs do not fit at 0.5 mm pitch,
lanes keep their straight drops and are chamfered once they have spread out.

Clearances: net classes, patterns and assignments from the .kicad_pro beside the input
(required), min_copper_edge_clearance and min_hole_clearance from its board rules. A
.kicad_dru beside it is read conservatively: area-scoped rules (intersectsArea /
insideArea / enclosedByArea with a known rule area) that raise the clearance apply where
the new copper touches that area; any other rule that raises the clearance is applied
board-wide; rules that only lower it are ignored. A change that would need a rule this
script cannot evaluate is skipped and reported. Other-net zone fills are obstacles unless
--refill (the caller refills the zones, e.g. kicad-cli drc --refill-zones). Same-net copper
that a chain does not already touch is kept untouched as well (keeps Kelvin lanes apart).
Teardrop zones at changed track ends are removed (regenerate teardrops afterwards).

ALWAYS re-run DRC afterwards beside the original .kicad_pro, e.g.
    kicad-cli pcb drc --refill-zones --schematic-parity --severity-all --format json out.kicad_pcb
The pass must add no violation and no unconnected item; this script checks geometry only.

Python stdlib only (+ sexpr.py from this folder).  Blocks are located with a paren-depth
scanner; changed segments are dropped whole and re-emitted, the rest of the file is kept
byte for byte.
"""
import argparse
import fnmatch
import json
import math
import os
import sys
import uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse  # noqa: E402

EPS = 1e-4
ANG_TOL = 0.05          # degrees: octilinear tolerance


# ------------------------------------------------------------------ s-expression blocks
def top_blocks(text):
    """Spans (start, end, tag) of the root's direct children, by paren depth."""
    out = []
    i, n = text.index('('), len(text)
    depth = 0
    start = None
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif c == '(':
            depth += 1
            if depth == 2:
                start = i
        elif c == ')':
            if depth == 2:
                j = start + 1
                while text[j] not in ' \t\r\n()':
                    j += 1
                out.append((start, i + 1, text[start + 1:j]))
            depth -= 1
            if depth == 0:
                break
        i += 1
    return out


def ch(node, tag):
    for c in node:
        if isinstance(c, list) and c and c[0] == tag:
            return c
    return None


def chs(node, tag):
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ geometry
def pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_cross(a, b, c, d):
    d1, d2, d3, d4 = _orient(c, d, a), _orient(c, d, b), _orient(a, b, c), _orient(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 * d2 < 0 and d3 * d4 < 0


def seg_seg(a, b, c, d):
    if seg_cross(a, b, c, d):
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def in_poly(p, pts):
    x, y = p
    ins = False
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                ins = not ins
    return ins


def rot(x, y, deg):
    if not deg:
        return x, y
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return x * c + y * s, -x * s + y * c


def angle(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def turn(a1, a2):
    d = a2 - a1
    while d > 180:
        d -= 360
    while d <= -180:
        d += 360
    return d


def octi(a, b):
    """Octilinear direction (0..7) of a->b or None."""
    if math.dist(a, b) < EPS:
        return None
    ang = angle(a, b) % 360
    k = round(ang / 45.0)
    return k % 8 if abs(ang - 45.0 * k) < ANG_TOL else None


def K(p):
    return (round(p[0], 4), round(p[1], 4))


def arc_pts(s, m, e, n=12):
    ax, ay = s
    bx, by = m
    cx, cy = e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0 = math.atan2(ay - uy, ax - ux)
    t1 = math.atan2(by - uy, bx - ux)
    t2 = math.atan2(cy - uy, cx - ux)

    def norm(t):
        return t % (2 * math.pi)
    ccw = norm(t1 - t0) < norm(t2 - t0)
    span = norm(t2 - t0) if ccw else -norm(t0 - t2)
    return [(ux + r * math.cos(t0 + span * k / n), uy + r * math.sin(t0 + span * k / n)) for k in range(n + 1)]


# ------------------------------------------------------------------ spatial index
class Index:
    def __init__(self, cell=1.0):
        self.cell = cell
        self.cells = defaultdict(set)
        self.objs = {}
        self.nid = 0

    def _keys(self, bb):
        c = self.cell
        for i in range(int(math.floor(bb[0] / c)), int(math.floor(bb[2] / c)) + 1):
            for j in range(int(math.floor(bb[1] / c)), int(math.floor(bb[3] / c)) + 1):
                yield (i, j)

    def add(self, o):
        self.nid += 1
        o['id'] = self.nid
        self.objs[self.nid] = o
        for k in self._keys(o['bb']):
            self.cells[k].add(self.nid)
        return self.nid

    def remove(self, oid):
        o = self.objs.pop(oid, None)
        if o:
            for k in self._keys(o['bb']):
                self.cells[k].discard(oid)

    def query(self, bb):
        seen = set()
        for k in self._keys(bb):
            seen |= self.cells.get(k, set())
        return [self.objs[i] for i in seen if i in self.objs]


def seg_obj(a, b, r, **kw):
    o = dict(kind='seg', a=a, b=b, r=r,
             bb=(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r))
    o.update(kw)
    return o


def poly_objs(pts, r=0.0, **kw):
    """Polygon as edge objects + one area object (containment test)."""
    out = []
    n = len(pts)
    for k in range(n):
        out.append(seg_obj(pts[k], pts[(k + 1) % n], r, **kw))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    area = dict(kind='area', pts=pts, bb=(min(xs), min(ys), max(xs), max(ys)))
    area.update(kw)
    out.append(area)
    return out


# ------------------------------------------------------------------ rules
class Rules:
    def __init__(self, pro_path, dru_path, extra):
        self.notes = []
        d = json.load(open(pro_path))
        ns = d.get('net_settings', {})
        self.cls = {c['name']: float(c.get('clearance', 0.2)) for c in ns.get('classes', [])}
        self.default = self.cls.get('Default', 0.2)
        self.patterns = [(p['pattern'], p['netclass']) for p in (ns.get('netclass_patterns') or [])]
        self.assign = ns.get('netclass_assignments') or {}
        r = d.get('board', {}).get('design_settings', {}).get('rules', {})
        self.edge = float(r.get('min_copper_edge_clearance', 0.0) or 0.0)
        self.hole = float(r.get('min_hole_clearance', 0.0) or 0.0)
        self.minclr = float(r.get('min_clearance', 0.0) or 0.0)
        self.extra = []
        for e in extra or []:
            pair, mm = e.rsplit(':', 1)
            a, b = pair.split('=')
            self.extra.append((a, b, float(mm)))
        self._ncache = {}
        self.area_rules = []      # (area name, clearance)
        self.global_raise = 0.0
        self.edge_raise = 0.0
        self.unevaluated = []
        if dru_path and os.path.exists(dru_path):
            self._dru(open(dru_path).read())

    def _dru(self, text):
        lines = []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith('#'):
                continue
            lines.append(ln)
        tree = parse('(rules ' + '\n'.join(lines) + ')')
        base = min(self.cls.values()) if self.cls else self.default
        for r in chs(tree, 'rule'):
            name = r[1]
            cond = ch(r, 'condition')
            cond = cond[1] if cond else ''
            for c in chs(r, 'constraint'):
                typ = c[0 + 1]
                mn = ch(c, 'min')
                v = None
                if mn:
                    t = mn[1]
                    v = float(t.replace('mm', '')) if t.endswith('mm') or num(t) is not None else None
                if typ in ('clearance', 'physical_clearance', 'hole_clearance', 'edge_clearance'):
                    tA = _cond_type(cond, 'A')
                    tB = _cond_type(cond, 'B')
                    nontrk = ('Via', 'Pad', 'Footprint', 'Zone', 'Text', 'Graphic')
                    if typ == 'edge_clearance' and tA in nontrk:
                        continue
                    if tA in nontrk and tB in nontrk:
                        continue
                    if v is None:
                        self.unevaluated.append('%s: %s (no min)' % (name, typ))
                        continue
                    ref = self.edge if typ == 'edge_clearance' else (self.hole if typ == 'hole_clearance' else base)
                    if v <= ref + 1e-9:
                        self.notes.append('rule "%s" (%s %.3f) only lowers the clearance: ignored' % (name, typ, v))
                        continue
                    areas = _cond_areas(cond)
                    if areas and ('||' not in cond):
                        for a in areas:
                            self.area_rules.append((a, typ, v))
                        self.notes.append('rule "%s" (%s %.3f) applied inside area(s) %s' % (name, typ, v, ', '.join(areas)))
                    else:
                        if typ == 'edge_clearance':
                            self.edge_raise = max(self.edge_raise, v)
                        else:
                            self.global_raise = max(self.global_raise, v)
                        self.notes.append('rule "%s" (%s %.3f) cannot be evaluated: applied board-wide (conservative)' % (name, typ, v))
                elif typ == 'disallow' and 'track' in [str(x) for x in c[2:]]:
                    areas = _cond_areas(cond)
                    if areas:
                        for a in areas:
                            self.area_rules.append((a, 'disallow', 0.0))
                        self.notes.append('rule "%s" disallows tracks in %s: treated as keep-out' % (name, ', '.join(areas)))
                    else:
                        self.unevaluated.append('%s: disallow track (condition not evaluated)' % name)

    def netclass(self, net):
        if net in self._ncache:
            return self._ncache[net]
        c = None
        a = self.assign.get(net)
        if a:
            c = a if isinstance(a, str) else a[0]
        if c is None:
            for p, nc in self.patterns:
                if fnmatch.fnmatchcase(net, p):
                    c = nc
                    break
        self._ncache[net] = c or 'Default'
        return self._ncache[net]

    def clr(self, n1, n2):
        c = max(self.cls.get(self.netclass(n1), self.default), self.cls.get(self.netclass(n2), self.default),
                self.global_raise, self.minclr)
        for a, b, v in self.extra:
            if (fnmatch.fnmatchcase(n1, a) and fnmatch.fnmatchcase(n2, b)) or \
               (fnmatch.fnmatchcase(n1, b) and fnmatch.fnmatchcase(n2, a)):
                c = max(c, v)
        return c


def _cond_type(cond, who):
    for q in ("'", '"'):
        key = who + '.Type == ' + q
        i = cond.find(key)
        if i >= 0:
            j = cond.index(q, i + len(key))
            return cond[i + len(key):j]
    return None


def _cond_areas(cond):
    out = []
    for fn in ('intersectsArea(', 'insideArea(', 'enclosedByArea(', 'intersectsCourtyard('):
        i = 0
        while True:
            i = cond.find(fn, i)
            if i < 0:
                break
            j = cond.index(')', i)
            arg = cond[i + len(fn):j].strip().strip('\'"')
            if fn != 'intersectsCourtyard(':
                out.append(arg)
            else:
                out.append('\0courtyard')
            i = j
    return [a for a in out if a != '\0courtyard'] if '\0courtyard' not in out else []


# ------------------------------------------------------------------ board model
class Board:
    def __init__(self, path, rules, refill):
        self.text = open(path, encoding='utf-8').read()
        self.blocks = top_blocks(self.text)
        self.rules = rules
        self.refill = refill
        self.idx = Index(1.0)
        self.segs = {}            # sid -> dict
        self.netnames = {}
        self.numeric_nets = False
        self.cu_layers = []
        self.fine_zones = []      # (layer, bbox)
        self.areas = {}           # rule-area name -> list of (layers, pts)
        self.teardrops = []       # (block index, net, layers, pts)
        self.locked_ok = True
        self.vias = []
        self.arc_nodes = defaultdict(set)
        self.anchor_objs = defaultdict(list)    # (net, layer) -> objects for anchoring
        self._load()

    def _netname(self, node):
        n = ch(node, 'net')
        if not n or len(n) < 2:
            return ''
        if len(n) >= 3:
            return n[2]
        v = n[1]
        if self.numeric_nets and num(v) is not None:
            return self.netnames.get(int(float(v)), '')
        return v

    def _layers(self, node):
        ls = []
        l1 = ch(node, 'layer')
        if l1:
            ls.append(l1[1])
        l2 = ch(node, 'layers')
        if l2:
            ls += l2[1:]
        out = []
        for L in ls:
            if L in ('*.Cu', 'F&B.Cu'):
                out += self.cu_layers if L == '*.Cu' else ['F.Cu', 'B.Cu']
            elif L.endswith('.Cu'):
                out.append(L)
        return out

    def _load(self):
        T = self.text
        parsed = []
        for k, (s, e, tag) in enumerate(self.blocks):
            if tag in ('layers', 'net', 'segment', 'arc', 'via', 'footprint', 'zone', 'gr_line', 'gr_rect',
                       'gr_poly', 'gr_arc', 'gr_circle'):
                parsed.append((k, tag, parse(T[s:e])))
        for k, tag, node in parsed:
            if tag == 'layers':
                self.cu_layers = [c[1] for c in node[1:] if isinstance(c, list) and len(c) > 1 and str(c[1]).endswith('.Cu')]
            elif tag == 'net':
                self.numeric_nets = True
                self.netnames[int(float(node[1]))] = node[2] if len(node) > 2 else ''
        R = self.rules
        for k, tag, node in parsed:
            if tag == 'segment':
                a = tuple(float(v) for v in ch(node, 'start')[1:3])
                b = tuple(float(v) for v in ch(node, 'end')[1:3])
                lk = ch(node, 'locked')
                locked = (lk is not None and (len(lk) == 1 or lk[1] == 'yes')) or 'locked' in node[1:2]
                s = dict(blk=k, a=a, b=b, w=float(ch(node, 'width')[1]), L=ch(node, 'layer')[1],
                         net=self._netname(node), locked=locked)
                sid = self.idx.add(seg_obj(a, b, s['w'] / 2, net=s['net'], layers=(s['L'],), typ='track'))
                s['oid'] = sid
                self.segs[sid] = s
            elif tag == 'arc':
                pts = arc_pts(*(tuple(float(v) for v in ch(node, t)[1:3]) for t in ('start', 'mid', 'end')))
                w = float(ch(node, 'width')[1])
                net = self._netname(node)
                L = ch(node, 'layer')[1]
                for p, q in zip(pts, pts[1:]):
                    self.idx.add(seg_obj(p, q, w / 2, net=net, layers=(L,), typ='arc'))
                self.arc_nodes[(net, L)].add(K(pts[0]))
                self.arc_nodes[(net, L)].add(K(pts[-1]))
            elif tag == 'via':
                at = tuple(float(v) for v in ch(node, 'at')[1:3])
                size = float(ch(node, 'size')[1])
                drill = float(ch(node, 'drill')[1]) if ch(node, 'drill') else 0.0
                ls = ch(node, 'layers')[1:] if ch(node, 'layers') else ['F.Cu', 'B.Cu']
                if len(ls) == 2 and ls[0] in self.cu_layers and ls[1] in self.cu_layers:
                    i0, i1 = sorted((self.cu_layers.index(ls[0]), self.cu_layers.index(ls[1])))
                    ls = self.cu_layers[i0:i1 + 1]
                net = self._netname(node)
                self.vias.append((at, size, net))
                self.idx.add(seg_obj(at, at, size / 2, net=net, layers=tuple(ls), typ='via', hole=drill / 2))
            elif tag == 'footprint':
                self._footprint(node)
            elif tag == 'zone':
                self._zone(k, node)
            elif tag in ('gr_line', 'gr_rect', 'gr_poly', 'gr_arc', 'gr_circle'):
                self._graphic(node, tag, (0, 0, 0))
        self._fine_pitch_done = False

    def _shape_objs(self, node, tag, xf, net, layers, typ):
        """Graphic (board or footprint) -> objects; xf=(x, y, rot) of the parent."""
        def P(p):
            x, y = rot(p[0], p[1], xf[2])
            return (x + xf[0], y + xf[1])
        st = ch(node, 'stroke')
        w = float(ch(st, 'width')[1]) if st and ch(st, 'width') else (float(ch(node, 'width')[1]) if ch(node, 'width') else 0.0)
        fill = ch(node, 'fill')
        filled = fill is not None and len(fill) > 1 and (fill[1] in ('yes', 'solid') or (isinstance(fill[1], list) and 'solid' in fill[1]))
        if isinstance(fill, list) and ch(fill, 'type') and ch(fill, 'type')[1] in ('solid', 'color'):
            filled = True
        kw = dict(net=net, layers=tuple(layers), typ=typ)
        out = []
        if tag.endswith('line'):
            out.append(seg_obj(P(tuple(float(v) for v in ch(node, 'start')[1:3])), P(tuple(float(v) for v in ch(node, 'end')[1:3])), w / 2, **kw))
        elif tag.endswith('rect'):
            a = tuple(float(v) for v in ch(node, 'start')[1:3])
            b = tuple(float(v) for v in ch(node, 'end')[1:3])
            pts = [P(a), P((b[0], a[1])), P(b), P((a[0], b[1]))]
            o = poly_objs(pts, w / 2, **kw)
            out += o if filled else o[:-1]
        elif tag.endswith('poly'):
            pts = [P((float(x[1]), float(x[2]))) for x in chs(ch(node, 'pts'), 'xy')]
            if len(pts) >= 2:
                o = poly_objs(pts, w / 2, **kw)
                out += o if (filled or typ == 'copper') else o[:-1]
        elif tag.endswith('arc'):
            pts = arc_pts(*(P(tuple(float(v) for v in ch(node, t)[1:3])) for t in ('start', 'mid', 'end')))
            out += [seg_obj(p, q, w / 2, **kw) for p, q in zip(pts, pts[1:])]
        elif tag.endswith('circle'):
            c = P(tuple(float(v) for v in ch(node, 'center')[1:3]))
            e = P(tuple(float(v) for v in ch(node, 'end')[1:3]))
            r = math.dist(c, e)
            if filled:
                out.append(seg_obj(c, c, r + w / 2, **kw))
            else:
                pts = [(c[0] + r * math.cos(t * math.pi / 16), c[1] + r * math.sin(t * math.pi / 16)) for t in range(33)]
                out += [seg_obj(p, q, w / 2, **kw) for p, q in zip(pts, pts[1:])]
        return out

    def _graphic(self, node, tag, xf, ref=''):
        lay = ch(node, 'layer')
        if not lay:
            return
        L = lay[1]
        if L == 'Edge.Cuts':
            for o in self._shape_objs(node, tag, xf, '', self.cu_layers, 'edge'):
                if o['kind'] == 'seg':
                    self.idx.add(o)
        elif L.endswith('.Cu'):
            net = self._netname(node)
            objs = self._shape_objs(node, tag, xf, net, [L], 'copper')
            for o in objs:
                self.idx.add(o)
                if net:
                    self.anchor_objs[(net, L)].append(o)

    def _footprint(self, node):
        at = ch(node, 'at')
        fx, fy = float(at[1]), float(at[2])
        fr = float(at[3]) if len(at) > 3 else 0.0
        ref = ''
        for p in chs(node, 'property'):
            if p[1] == 'Reference':
                ref = p[2]
        fp_ref = ch(node, 'fp_text')
        if not ref and fp_ref and fp_ref[1] == 'reference':
            ref = fp_ref[2]
        pads = []
        for pad in chs(node, 'pad'):
            pat = ch(pad, 'at')
            px, py = rot(float(pat[1]), float(pat[2]), fr)
            cx, cy = fx + px, fy + py
            prot = float(pat[3]) if len(pat) > 3 else 0.0
            shape = pad[3]
            size = ch(pad, 'size')
            sx, sy = float(size[1]), float(size[2])
            net = self._netname(pad)
            layers = self._layers(pad)
            dr = ch(pad, 'drill')
            hole = 0.0
            if dr:
                vals = [num(v) for v in dr[1:] if not isinstance(v, list) and num(v) is not None]
                hole = (min(vals) / 2) if vals else 0.0
            kw = dict(net=net, layers=tuple(layers), typ='pad', ref=ref, pad=pad[1])
            objs = []
            if layers:
                if shape == 'circle':
                    objs.append(seg_obj((cx, cy), (cx, cy), sx / 2, hole=hole, **kw))
                elif shape == 'oval':
                    if sx >= sy:
                        d, r = (sx - sy) / 2, sy / 2
                        a, b = rot(-d, 0, prot), rot(d, 0, prot)
                    else:
                        d, r = (sy - sx) / 2, sx / 2
                        a, b = rot(0, -d, prot), rot(0, d, prot)
                    objs.append(seg_obj((cx + a[0], cy + a[1]), (cx + b[0], cy + b[1]), r, hole=hole, **kw))
                else:
                    corners = [rot(x, y, prot) for x, y in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]
                    objs += poly_objs([(cx + x, cy + y) for x, y in corners], 0.0, **kw)
                    if hole:
                        objs.append(seg_obj((cx, cy), (cx, cy), 0.0, hole=hole, **kw))
                prim = ch(pad, 'primitives')
                if prim:
                    for g in prim[1:]:
                        if isinstance(g, list) and g[0] in ('gr_poly', 'gr_line', 'gr_rect', 'gr_circle', 'gr_arc'):
                            g2 = list(g)
                            if not ch(g2, 'fill') and g[0] == 'gr_poly':
                                g2.append(['fill', 'yes'])
                            objs += self._shape_objs(g2, g[0], (cx, cy, prot), net, layers, 'pad')
                for o in objs:
                    o['ref'], o['pad'] = ref, pad[1]
                    self.idx.add(o)
                    if net:
                        for L in layers:
                            self.anchor_objs[(net, L)].append(o)
            elif hole:     # NPTH
                self.idx.add(seg_obj((cx, cy), (cx, cy), 0.0, hole=hole, net='', layers=tuple(self.cu_layers), typ='npth', ref=ref))
            pads.append((cx, cy, layers, ref))
        self._fp_pads = getattr(self, '_fp_pads', [])
        self._fp_pads.append((ref, pads))
        for g in node:
            if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_rect', 'fp_poly', 'fp_arc', 'fp_circle'):
                self._graphic(g, g[0], (fx, fy, fr), ref)

    def fine_pitch(self, pitch, margin):
        for ref, pads in self._fp_pads:
            by = defaultdict(list)
            for cx, cy, layers, _ in pads:
                for L in layers:
                    by[L].append((cx, cy))
            for L, pts in by.items():
                fine = []
                for i, p in enumerate(pts):
                    d = min((math.dist(p, q) for j, q in enumerate(pts) if j != i and math.dist(p, q) > 1e-6), default=9e9)
                    if d <= pitch + 0.005:
                        fine.append(p)
                if len(fine) >= 3:
                    xs = [p[0] for p in fine]
                    ys = [p[1] for p in fine]
                    self.fine_zones.append((L, (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin), ref))

    def _zone(self, k, node):
        net = self._netname(node)
        layers = self._layers(node)
        ko = ch(node, 'keepout')
        nm = ch(node, 'name')
        name = nm[1] if nm else ''
        poly = ch(node, 'polygon')
        pts = [(float(x[1]), float(x[2])) for x in chs(ch(poly, 'pts'), 'xy')] if poly else []
        attr = ch(node, 'attr')
        is_td = attr is not None and ch(attr, 'teardrop') is not None
        if ko is not None:
            if name:
                self.areas.setdefault(name, []).append((layers, pts))
            tr = ch(ko, 'tracks')
            if tr and tr[1] == 'not_allowed' and pts:
                for o in poly_objs(pts, 0.0, net='', layers=tuple(layers), typ='keepout', name=name):
                    self.idx.add(o)
            return
        if is_td:
            self.teardrops.append((k, net, layers, pts))
            for o in poly_objs(pts, 0.0, net=net, layers=tuple(layers), typ='teardrop'):
                self.idx.add(o)
            return
        for fp in chs(node, 'filled_polygon'):
            L = ch(fp, 'layer')[1]
            fpts = [(float(x[1]), float(x[2])) for x in chs(ch(fp, 'pts'), 'xy')]
            objs = poly_objs(fpts, 0.0, net=net, layers=(L,), typ='zone')
            for o in objs:
                if net:
                    self.anchor_objs[(net, L)].append(o)
                if not self.refill:
                    self.idx.add(o)

    # ---------------------------------------------------------- clearance query
    def check(self, a, b, hw, net, L, exempt, diag_ok=True):
        """None if the segment a-b (half width hw) on L clears everything, else a blocker text."""
        R = self.rules
        if not diag_ok:
            return 'fine-pitch pad row'
        M = max(R.cls.values() or [0.2]) + max(R.global_raise, R.edge, R.edge_raise, R.hole, 0.5) + hw + 0.6
        bb = (min(a[0], b[0]) - M, min(a[1], b[1]) - M, max(a[0], b[0]) + M, max(a[1], b[1]) + M)
        for o in self.idx.query(bb):
            if o['id'] in exempt or L not in o['layers']:
                continue
            t = o['typ']
            if o['kind'] == 'area':
                same = o['net'] == net and net
                if same and t in ('zone', 'teardrop', 'track', 'via'):
                    continue
                if in_poly(a, o['pts']) or in_poly(b, o['pts']):
                    if same:
                        return 'same-net %s %s (new contact)' % (t, o.get('ref', ''))
                    return '%s %s inside' % (t, o.get('name') or o['net'] or o.get('ref', ''))
                continue
            if o['net'] == net and net and t in ('zone', 'teardrop'):
                continue
            d = seg_seg(a, b, o['a'], o['b']) - hw
            if t == 'edge':
                need = max(R.edge, R.edge_raise)
                if d < need - 1e-6:
                    return 'board edge (%.3f < %.3f)' % (d, need)
                continue
            if t == 'keepout':
                if d < 1e-6:
                    return 'keep-out %s' % o.get('name', '')
                continue
            hole = o.get('hole', 0.0)
            if hole and o['net'] != net and R.hole:
                dh = seg_seg(a, b, o['a'], o['a']) - hw - hole
                if dh < R.hole - 1e-6:
                    return '%s hole %s (%.3f)' % (t, o.get('ref', '') or o['net'], dh)
            if t == 'npth':
                continue
            dc = d - o['r']
            if o['net'] == net and net:
                if dc < 1e-4:
                    return 'same-net %s %s (new contact)' % (t, o.get('ref', '') or '')
                continue
            need = R.clr(net, o['net'])
            if dc < need - 1e-6:
                return '%s %s %s (%.3f < %.3f)' % (t, o['net'] or '-', o.get('ref', ''), dc, need)
        for name, typ, v in R.area_rules:
            for layers, pts in self.areas.get(name, []):
                if L in layers and pts and (in_poly(a, pts) or in_poly(b, pts) or
                                             any(seg_cross(a, b, pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))):
                    if typ == 'disallow':
                        return 'rule area %s disallows tracks' % name
                    # re-check against the raised clearance inside the area
                    for o in self.idx.query(bb):
                        if o['id'] in exempt or L not in o['layers'] or o['kind'] != 'seg' or o['net'] == net:
                            continue
                        if typ == 'edge_clearance' and o['typ'] != 'edge':
                            continue
                        if typ != 'edge_clearance' and o['typ'] == 'edge':
                            continue
                        dc = seg_seg(a, b, o['a'], o['b']) - hw - o['r']
                        if dc < v - 1e-6:
                            return 'area rule %s %s %.3f' % (name, typ, v)
        return None

    def anchored(self, p, hw, net, L, exclude_sids):
        """Does a track end at p (half width hw) touch same-net copper other than exclude_sids?"""
        bb = (p[0] - hw - 0.01, p[1] - hw - 0.01, p[0] + hw + 0.01, p[1] + hw + 0.01)
        for o in self.idx.query(bb):
            if o['id'] in exclude_sids or o['net'] != net or L not in o['layers']:
                continue
            if o['kind'] == 'seg':
                # another track counts only when p lies on it (T-junction); pads/vias when p is inside
                # KiCad joins an end that lies inside other copper of the net; pads and vias
                # also when the track's own width overlaps them
                lim = o['r'] + 1e-4 if o['typ'] in ('track', 'arc') else o['r'] + hw
                if pt_seg(p, o['a'], o['b']) <= lim:
                    return o['typ']
            if o['kind'] == 'area' and in_poly(p, o['pts']):
                return o['typ']
        for o in self.anchor_objs.get((net, L), []):
            if o['kind'] == 'area' and o['bb'][0] <= p[0] <= o['bb'][2] and o['bb'][1] <= p[1] <= o['bb'][3] and in_poly(p, o['pts']):
                return o['typ']
            if o['kind'] == 'seg' and o['typ'] == 'zone' and pt_seg(p, o['a'], o['b']) <= hw * 0.5:
                return 'zone'
        return None

    def in_fine(self, a, b, L):
        for ZL, bb, _ in self.fine_zones:
            if ZL != L:
                continue
            if seg_box(a, b, bb):
                return True
        return False


def seg_box(a, b, bb):
    x0, y0, x1, y1 = bb
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1 or x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    box = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(seg_cross(a, b, box[i], box[(i + 1) % 4]) for i in range(4))


# ------------------------------------------------------------------ chains
def build_chains(bd):
    """Polylines per (net, layer) between terminals."""
    by = defaultdict(list)
    for sid, s in bd.segs.items():
        by[(s['net'], s['L'])].append(sid)
    out = []
    for (net, L), sids in by.items():
        adj = defaultdict(list)
        for sid in sids:
            s = bd.segs[sid]
            adj[K(s['a'])].append(sid)
            adj[K(s['b'])].append(sid)
        arcs = bd.arc_nodes.get((net, L), set())
        term = {}
        for n, lst in adj.items():
            if len(lst) != 2 or n in arcs:
                term[n] = True
                continue
            hw = min(bd.segs[i]['w'] for i in lst) / 2
            # the node's own segments and their neighbours (a staircase's next step lies
            # within a track width but is not a junction)
            near = set(lst)
            for i in lst:
                s_ = bd.segs[i]
                for e in (K(s_['a']), K(s_['b'])):
                    if e != n:
                        near |= set(adj.get(e, []))
            term[n] = bool(bd.anchored(n, hw, net, L, near))
        used = set()

        def walk(n0, sid):
            pts, sl = [n0], []
            cur = n0
            while True:
                used.add(sid)
                sl.append(sid)
                s = bd.segs[sid]
                nxt = K(s['b']) if K(s['a']) == cur else K(s['a'])
                pts.append(nxt)
                cur = nxt
                if term[cur]:
                    break
                cand = [t for t in adj[cur] if t != sid and t not in used]
                if not cand:
                    break
                sid = cand[0]
            return pts, sl
        for n0 in adj:
            if term[n0]:
                for sid in adj[n0]:
                    if sid not in used:
                        pts, sl = walk(n0, sid)
                        out.append(dict(net=net, L=L, pts=pts, sids=sl, deg=(len(adj[pts[0]]), len(adj[pts[-1]]))))
        for n0 in adj:           # closed loops without a terminal
            for sid in adj[n0]:
                if sid not in used:
                    pts, sl = walk(n0, sid)
                    out.append(dict(net=net, L=L, pts=pts, sids=sl, deg=(2, 2), loop=True))
    return out


def classify(pts):
    """Per interior vertex: (point, turn, cat)."""
    res = []
    for k in range(1, len(pts) - 1):
        if math.dist(pts[k - 1], pts[k]) < EPS or math.dist(pts[k], pts[k + 1]) < EPS:
            res.append((pts[k], 0.0, 'zero'))
            continue
        t = turn(angle(pts[k - 1], pts[k]), angle(pts[k], pts[k + 1]))
        a = abs(t)
        cat = ('collinear' if a < 0.5 else '45' if abs(a - 45) < 0.5 else '90' if abs(a - 90) < 0.5 else
               '135' if abs(a - 135) < 0.5 else 'u-turn' if a > 179.5 else 'odd')
        res.append((pts[k], t, cat))
    return res


def jogs(pts):
    """Doglegs (two opposite turns restoring the direction) and U-turns: list of (k, kind, offset)."""
    out = []
    c = classify(pts)
    for k in range(len(c) - 1):
        t1, t2 = c[k][1], c[k + 1][1]
        if abs(t1) < 0.5 or abs(t2) < 0.5:
            continue
        p0, p1, p2, p3 = pts[k], pts[k + 1], pts[k + 2], pts[k + 3]
        if abs(t1 + t2) < 0.5:
            ang = math.radians(angle(p0, p1))
            off = abs(-(p2[0] - p1[0]) * math.sin(ang) + (p2[1] - p1[1]) * math.cos(ang))
            out.append((k + 1, 'dogleg', off))
        elif abs(abs(t1 + t2) - 180) < 0.5:
            out.append((k + 1, 'u-turn', math.dist(p1, p2)))
    return out


def stats(bd):
    cs = build_chains(bd)
    st = defaultdict(int)
    for c in cs:
        for p, t, cat in classify(c['pts']):
            st['corner ' + cat] += 1
        for k, kind, off in jogs(c['pts']):
            st[kind] += 1
    st['segments'] = len(bd.segs)
    return dict(st), cs


# ------------------------------------------------------------------ edits
class Editor:
    def __init__(self, bd, args):
        self.bd = bd
        self.a = args
        self.new = {}           # sid -> segment dict (new)
        self.dropped = set()    # block indices
        self.changed_ends = []  # (net, L, point)
        self.log = defaultdict(list)
        self.zwhy = {}

    def replace(self, chain, newpts, widths, locked):
        bd = self.bd
        net, L = chain['net'], chain['L']
        old_ends = set()
        for sid in chain['sids']:
            s = bd.segs.pop(sid)
            bd.idx.remove(sid)
            if 'blk' in s:
                self.dropped.add(s['blk'])
            self.new.pop(sid, None)
            old_ends |= {K(s['a']), K(s['b'])}
        new_ids = []
        for (p, q), w in zip(zip(newpts, newpts[1:]), widths):
            if math.dist(p, q) < EPS:
                continue
            sid = bd.idx.add(seg_obj(p, q, w / 2, net=net, layers=(L,), typ='track'))
            s = dict(a=p, b=q, w=w, L=L, net=net, locked=locked, oid=sid)
            bd.segs[sid] = s
            self.new[sid] = s
            new_ids.append(sid)
        new_ends = set()
        for sid in new_ids:
            new_ends |= {K(bd.segs[sid]['a']), K(bd.segs[sid]['b'])}
        for p in old_ends ^ new_ends:
            self.changed_ends.append((net, L, p))
        # ends whose track direction changed
        for p in (K(chain['pts'][0]), K(chain['pts'][-1])):
            if len(chain['pts']) > 1 and len(newpts) > 1:
                o_dir = angle(chain['pts'][0], chain['pts'][1]) if p == K(chain['pts'][0]) else angle(chain['pts'][-1], chain['pts'][-2])
                n_dir = angle(newpts[0], newpts[1]) if p == K(newpts[0]) else angle(newpts[-1], newpts[-2])
                if abs(turn(o_dir, n_dir)) > 0.01:
                    self.changed_ends.append((net, L, p))
        return new_ids

    def exempt_for(self, chain):
        bd = self.bd
        ex = set(chain['sids'])
        for p in (chain['pts'][0], chain['pts'][-1]):
            bb = (p[0] - 0.01, p[1] - 0.01, p[0] + 0.01, p[1] + 0.01)
            for o in bd.idx.query((bb[0] - 3, bb[1] - 3, bb[2] + 3, bb[3] + 3)):
                if o['net'] != chain['net'] or chain['L'] not in o['layers'] or o['typ'] in ('zone', 'teardrop'):
                    continue
                if o['kind'] == 'seg' and pt_seg(p, o['a'], o['b']) <= o['r'] + 0.2:
                    ex.add(o['id'])
                    if o['typ'] == 'pad':
                        ex |= {x['id'] for x in bd.idx.query(o['bb']) if x.get('ref') == o.get('ref') and x.get('pad') == o.get('pad')}
                elif o['kind'] == 'area' and in_poly(p, o['pts']):
                    ex.add(o['id'])
                    ex |= {x['id'] for x in bd.idx.query(o['bb']) if x['net'] == o['net'] and x.get('ref') == o.get('ref') and x.get('pad') == o.get('pad') and x['typ'] == o['typ']}
        return ex

    def _covered(self, npts, nws, chain):
        """Is every new segment already lying on one same-net track outside the chain?"""
        bd = self.bd
        own = set(chain['sids'])
        for (p, q), w in zip(zip(npts, npts[1:]), nws):
            bb = (min(p[0], q[0]) - 0.01, min(p[1], q[1]) - 0.01, max(p[0], q[0]) + 0.01, max(p[1], q[1]) + 0.01)
            if not any(o['typ'] == 'track' and o['net'] == chain['net'] and chain['L'] in o['layers'] and o['id'] not in own
                       and o['r'] * 2 >= w - 1e-6 and pt_seg(p, o['a'], o['b']) < 1e-3 and pt_seg(q, o['a'], o['b']) < 1e-3
                       for o in bd.idx.query(bb)):
                return False
        return True

    def touchers(self, chain):
        """Same-net items (other tracks' ends, vias, pads, arcs) touching the chain's copper."""
        bd = self.bd
        net, L = chain['net'], chain['L']
        own = set(chain['sids'])
        pts = chain['pts']
        hw = max(bd.segs[s]['w'] for s in chain['sids']) / 2
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bb = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
        out = []
        for o in bd.idx.query(bb):
            if o['id'] in own or o['net'] != net or L not in o['layers'] or o['kind'] != 'seg':
                continue
            if o['typ'] in ('zone', 'teardrop', 'edge', 'keepout'):
                continue
            cands = [o['a'], o['b']] if o['typ'] in ('track', 'arc') else [None]
            for c in cands:
                if c is None:
                    d = min(seg_seg(p, q, o['a'], o['b']) for p, q in zip(pts, pts[1:])) - o['r'] - hw
                    if d <= 1e-4:
                        out.append(('obj', o))
                        break
                else:
                    d = min(pt_seg(c, p, q) for p, q in zip(pts, pts[1:]))
                    if d <= 1e-3:
                        out.append(('pt', c))
        return out

    def keeps(self, tl, newpts, neww):
        if len(newpts) < 2:
            return not tl
        hw = min(neww) / 2
        for kind, x in tl:
            if kind == 'pt':
                if min(pt_seg(x, p, q) for p, q in zip(newpts, newpts[1:])) > 1e-3:
                    return False
            else:
                if min(seg_seg(p, q, x['a'], x['b']) for p, q in zip(newpts, newpts[1:])) - x['r'] - hw > 1e-4:
                    return False
        return True

    # (c) stubs
    def stubs(self):
        bd = self.bd
        n = 0
        for _ in range(5):
            removed = 0
            for c in build_chains(bd):
                if self.skip(c):
                    continue
                ends = []
                for idx_ in (0, -1):
                    p = c['pts'][idx_]
                    deg = c['deg'][0 if idx_ == 0 else 1]
                    hw = bd.segs[c['sids'][0 if idx_ == 0 else -1]]['w'] / 2
                    free = deg == 1 and not bd.anchored(p, hw, c['net'], c['L'], set(c['sids']))
                    ends.append(free)
                if any(ends) and (c['net'] or True):
                    other = c['pts'][-1] if ends[0] else c['pts'][0]
                    ln = sum(math.dist(p, q) for p, q in zip(c['pts'], c['pts'][1:]))
                    if self.a.max_stub and ln > self.a.max_stub:
                        self.log['stub left'].append('%s %s at (%.3f, %.3f): %.2f mm > --max-stub' % (c['net'], c['L'], *c['pts'][0 if ends[0] else -1], ln))
                        continue
                    if self._via_only(other, c):
                        self.log['stub left'].append('%s %s free end (%.3f, %.3f): removing it would leave its via dangling'
                                                     % (c['net'], c['L'], *(c['pts'][0] if ends[0] else c['pts'][-1])))
                        continue
                    self.replace(c, [], [], False)
                    self.changed_ends.append((c['net'], c['L'], other))
                    self.log['stub removed'].append('%s %s free end (%.3f, %.3f), %.3f mm' % (c['net'], c['L'], *(c['pts'][0] if ends[0] else c['pts'][-1]), ln))
                    removed += 1
            n += removed
            if not removed:
                break
        return n

    def _via_only(self, p, chain):
        """Would the via at p (if any) keep copper on fewer than two layers without this chain?
        (KiCad reports such a via as dangling.)"""
        bd = self.bd
        bb = (p[0] - 0.01, p[1] - 0.01, p[0] + 0.01, p[1] + 0.01)
        vias = [o for o in bd.idx.query(bb) if o['typ'] == 'via' and o['net'] == chain['net'] and math.dist(o['a'], p) <= o['r']]
        if not vias:
            return False
        v = vias[0]
        own = set(chain['sids'])
        layers = set()
        for o in bd.idx.query(v['bb']):
            if o['net'] != chain['net'] or o['id'] in own or o['id'] == v['id']:
                continue
            if o['kind'] == 'seg' and o['typ'] in ('track', 'arc', 'pad', 'copper', 'zone') and \
               pt_seg(v['a'], o['a'], o['b']) <= v['r'] + o['r']:
                layers |= set(o['layers']) & set(v['layers'])
            elif o['kind'] == 'area' and in_poly(v['a'], o['pts']):
                layers |= set(o['layers']) & set(v['layers'])
        for o in bd.anchor_objs.get((chain['net'], chain['L']), []):
            if o['typ'] == 'zone' and o['kind'] == 'area' and in_poly(v['a'], o['pts']):
                layers |= set(o['layers'])
        return len(layers) < 2

    def skip(self, c):
        if self.a.skip_locked and any(self.bd.segs[s]['locked'] for s in c['sids']):
            return True
        return c.get('loop', False)

    # (a)+(b) jogs and collinear
    def straighten(self):
        bd = self.bd
        fixed = 0
        merged = 0
        for c in build_chains(bd):
            if self.skip(c) or len(c['pts']) < 3:
                continue
            pts = c['pts']
            ws = [bd.segs[s]['w'] for s in c['sids']]
            locked = any(bd.segs[s]['locked'] for s in c['sids'])
            ex = self.exempt_for(c)
            net, L = c['net'], c['L']
            orig_cls = classify(pts)
            orig_bends = sum(1 for _, t, cat in orig_cls if cat not in ('collinear', 'zero'))
            ncol = sum(1 for _, t, cat in orig_cls if cat in ('collinear', 'zero'))
            orig_len = sum(math.dist(p, q) for p, q in zip(pts, pts[1:]))
            res = self._dp(pts, ws, net, L, ex)
            if res is None:
                continue
            npts, nws = res
            ncl = classify(npts)
            nb = sum(1 for _, t, cat in ncl if cat not in ('collinear', 'zero'))
            nlen = sum(math.dist(p, q) for p, q in zip(npts, npts[1:]))
            if nb < orig_bends and nlen <= orig_len * 1.02 + 0.01 and not self.keeps(self.touchers(c), npts, nws):
                self.log['jog left'].append('%s %s (%.3f, %.3f): straight path would drop a same-net tap' % (net, L, *pts[1]))
            elif nb < orig_bends and nlen <= orig_len * 1.02 + 0.01 and self._covered(npts, nws, c):
                self.log['jog fixed'].append(dict(net=net, L=L, at=pts[1], dev=max(min(pt_seg(p, a, b) for a, b in zip(npts, npts[1:])) for p in pts),
                                                  bends=(orig_bends, 0), kind='redundant loop removed', locked=locked, sids=list(c['sids'])))
                self.replace(c, [], [], locked)
                fixed += orig_bends
            elif nb < orig_bends and nlen <= orig_len * 1.02 + 0.01:
                dev = max(min(pt_seg(p, a, b) for a, b in zip(npts, npts[1:])) for p in pts)
                kinds = sorted({k for _, k, _ in jogs(pts)}) or ['detour']
                self.log['jog fixed'].append(dict(net=net, L=L, at=pts[1], dev=dev, bends=(orig_bends, nb),
                                                  kind='/'.join(kinds), locked=locked, sids=list(c['sids'])))
                self.replace(c, npts, nws, locked)
                fixed += orig_bends - nb
            elif ncol:
                mp, mw = merge_collinear(pts, ws)
                if len(mp) < len(pts) and self.keeps(self.touchers(c), mp, mw):
                    self.replace(c, mp, mw, locked)
                    merged += len(pts) - len(mp)
        return fixed, merged

    def _dp(self, pts, ws, net, L, ex):
        bd = self.bd
        n = len(pts) - 1
        best = {(0, None): (0, 0.0, [pts[0]], [], [])}     # bends, length, points, widths, orig-flags
        order = [(0, None)]
        cache = {}

        def ok(p, q, w):
            key = (K(p), K(q), w)
            if key not in cache:
                diag = octi(p, q)
                diag_ok = not (diag is not None and diag % 2 == 1 and bd.in_fine(p, q, L))
                cache[key] = bd.check(p, q, w / 2, net, L, ex, diag_ok) is None
            return cache[key]
        states = defaultdict(dict)
        states[0][None] = best[(0, None)]
        for i in range(n):
            for ain, (bends, ln, pp, pw, po) in list(states[i].items()):
                for j in range(i + 1, n + 1):
                    wset = set(ws[i:j])
                    opts = []
                    if j == i + 1:
                        opts.append(([pts[j]], True))
                    if len(wset) == 1:
                        w = ws[i]
                        if j > i + 1 and octi(pts[i], pts[j]) is not None:
                            opts.append(([pts[j]], False))
                        if j > i + 1 or octi(pts[i], pts[j]) is None:
                            for m in dogleg(pts[i], pts[j]):
                                opts.append(([m, pts[j]], False))
                    for seq, orig in opts:
                        w = ws[i] if orig else ws[i]
                        prev = pp[-1]
                        good = True
                        if not orig:
                            q0 = prev
                            for q in seq:
                                if not ok(q0, q, w):
                                    good = False
                                    break
                                q0 = q
                        if not good:
                            continue
                        b = bends
                        a_cur = ain
                        p0 = prev
                        flags = po[:]
                        tturn_ok = True
                        for q in seq:
                            a_new = angle(p0, q)
                            if a_cur is not None:
                                tt = abs(turn(a_cur, a_new))
                                if tt > 0.5:
                                    b += 1
                                if tt > 45.5 and not (orig and (not flags or flags[-1])):
                                    tturn_ok = False
                            flags.append(orig)
                            a_cur = a_new
                            p0 = q
                        if not tturn_ok:
                            continue
                        nl = ln + sum(math.dist(x, y) for x, y in zip([prev] + seq, seq))
                        key = round(a_cur, 2)
                        cur = states[j].get(key)
                        if cur is None or (b, nl) < (cur[0], cur[1]):
                            states[j][key] = (b, nl, pp + seq, pw + [w] * len(seq), flags)
        if not states[n]:
            return None
        b, nl, pp, pw, _ = min(states[n].values(), key=lambda s: (s[0], s[1]))
        mp, mw = merge_collinear(pp, pw)
        return mp, mw

    # (d) chamfers
    def chamfer(self):
        bd = self.bd
        done = 0
        for c in build_chains(bd):
            if self.skip(c) or len(c['pts']) < 3:
                continue
            pts = list(c['pts'])
            ws = [bd.segs[s]['w'] for s in c['sids']]
            locked = any(bd.segs[s]['locked'] for s in c['sids'])
            net, L = c['net'], c['L']
            cls = classify(pts)
            corners = [k + 1 for k, (_, t, cat) in enumerate(cls) if cat == '90']
            if not corners:
                continue
            ex = self.exempt_for(c)
            newpts = [pts[0]]
            neww = []
            changed = False
            # walk vertices; keep track of current start point of the segment into vertex k
            cur_start = pts[0]
            skip_next = False
            for k in range(1, len(pts)):
                if skip_next:
                    skip_next = False
                    continue
                if k in corners and k + 1 in corners and cls[k - 1][1] * cls[k][1] < 0 and ws[k - 1] == ws[k] == ws[k + 1]:
                    z = self._zigzag(pts, k, cur_start, corners, ws[k], net, L, ex)
                    if z:
                        A, B = z
                        newpts += [A, B]
                        neww += [ws[k - 1], ws[k]]
                        cur_start = B
                        skip_next = True
                        changed = True
                        done += 2
                        self.log['corner chamfered'].append((net, L, pts[k], -1))
                        self.log['corner chamfered'].append((net, L, pts[k + 1], -1))
                        continue
                if k not in corners:
                    newpts.append(pts[k])
                    neww.append(ws[k - 1])
                    cur_start = pts[k]
                    continue
                P = pts[k]
                prev, nxt = cur_start, pts[k + 1]
                w = ws[k - 1]
                if ws[k] != w:
                    self.log['corner left'].append('%s %s (%.3f, %.3f): width change at the corner' % (net, L, *P))
                    newpts.append(P)
                    neww.append(ws[k - 1])
                    cur_start = P
                    continue
                if any(ZL == L and bb[0] <= P[0] <= bb[2] and bb[1] <= P[1] <= bb[3] for ZL, bb, _ in bd.fine_zones):
                    self.log['corner left'].append('%s %s (%.3f, %.3f): inside a fine-pitch pad row (straight escape kept)' % (net, L, *P))
                    newpts.append(P)
                    neww.append(w)
                    cur_start = P
                    continue
                # keep >= one track width of straight track between bends; none needed at a chain end
                lp = math.dist(prev, P) - (0.0 if k - 1 == 0 else w)
                ln_ = math.dist(P, nxt)
                ln_ = (ln_ - w) / 2 if (k + 1) in corners else ln_ - (0.0 if k + 1 == len(pts) - 1 else w)
                cmax = min(self.a.max_chamfer, lp, ln_)
                cmin = self.a.min_chamfer or w
                u1 = ((P[0] - prev[0]) / math.dist(prev, P), (P[1] - prev[1]) / math.dist(prev, P))
                u2 = ((nxt[0] - P[0]) / math.dist(P, nxt), (nxt[1] - P[1]) / math.dist(P, nxt))
                chosen = None
                why = 'segments too short (%.3f / %.3f mm for a %.3f mm leg)' % (lp, ln_, cmin) if cmax < cmin else None
                if why and self.zwhy.get(K(P)):
                    why = 'Z-step, 45-degree step blocked by ' + self.zwhy[K(P)]
                cands = []
                cc = cmax
                while cc > cmin + 1e-9:
                    cands.append(cc)
                    cc = round(cc - 0.05, 4)
                if cmax >= cmin - 1e-9:
                    cands.append(cmin)
                for cc in cands:
                    A = (P[0] - u1[0] * cc, P[1] - u1[1] * cc)
                    B = (P[0] + u2[0] * cc, P[1] + u2[1] * cc)
                    oc = octi(A, B)
                    diag_ok = not bd.in_fine(A, B, L) if oc is not None and oc % 2 == 1 else True
                    r = bd.check(A, B, w / 2, net, L, ex, diag_ok)
                    if r is None:
                        chosen = (A, B, cc)
                        break
                    why = r
                if chosen:
                    A, B, cc = chosen
                    newpts += [A, B]
                    neww += [w, w]
                    cur_start = B
                    changed = True
                    done += 1
                    self.log['corner chamfered'].append((net, L, P, cc))
                else:
                    newpts.append(P)
                    neww.append(w)
                    cur_start = P
                    self.log['corner left'].append('%s %s (%.3f, %.3f): %s' % (net, L, P[0], P[1], why or 'no room'))
            if changed:
                if not self.keeps(self.touchers(c), newpts, neww):
                    self.log['corner left'].append('%s %s near (%.3f, %.3f): a chamfer would drop a same-net tap (whole chain kept)' % (net, L, *pts[1]))
                    done -= sum(1 for x in self.log['corner chamfered'] if x[0] == net and x[1] == L and x[2] in pts)
                    continue
                self.replace(c, newpts, neww, locked)
        return done

    def _zigzag(self, pts, k, cur_start, corners, w, net, L, ex):
        """Z of two opposite 90-degree corners (P1=pts[k], P2=pts[k+1]) whose middle is too short
        for two chamfers: replace the middle by one 45-degree segment A->B."""
        bd = self.bd
        P1, P2 = pts[k], pts[k + 1]
        m = math.dist(P1, P2)
        cmin = self.a.min_chamfer or w
        if (m - w) / 2 >= cmin and m <= 2 * self.a.max_chamfer:
            return None                    # ordinary chamfers fit
        u1 = ((P1[0] - cur_start[0]) / math.dist(cur_start, P1), (P1[1] - cur_start[1]) / math.dist(cur_start, P1))
        nx = pts[k + 2]
        u3 = ((nx[0] - P2[0]) / math.dist(P2, nx), (nx[1] - P2[1]) / math.dist(P2, nx))
        ap = math.dist(cur_start, P1) - (0.0 if k - 1 == 0 else w)
        an = math.dist(P2, nx)
        an = (an - w) / 2 if (k + 2) in corners else an - (0.0 if k + 2 == len(pts) - 1 else w)
        if any(ZL == L and bb[0] <= P[0] <= bb[2] and bb[1] <= P[1] <= bb[3] for ZL, bb, _ in bd.fine_zones for P in (P1, P2)):
            return None
        why = None
        for a, b in ((m / 2, m / 2), (m, 0.0), (0.0, m)):
            if a > ap + 1e-9 or b > an + 1e-9:
                why = why or 'no straight length for a 45-degree step'
                continue
            A = (P1[0] - u1[0] * a, P1[1] - u1[1] * a)
            B = (P2[0] + u3[0] * b, P2[1] + u3[1] * b)
            oc = octi(A, B)
            if oc is None:
                continue
            r = bd.check(A, B, w / 2, net, L, ex, not (oc % 2 == 1 and bd.in_fine(A, B, L)))
            if r is None:
                return A, B
            why = r
        self.zwhy[K(P1)] = self.zwhy[K(P2)] = why
        return None

    def remove_teardrops(self):
        bd = self.bd
        drop = set()
        for k, net, layers, pts in bd.teardrops:
            for n, L, p in self.changed_ends:
                if n == net and L in layers and pts and (in_poly(p, pts) or min(pt_seg(p, pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))) < 0.05):
                    drop.add(k)
                    break
        self.dropped |= drop
        return len(drop)


def dogleg(p, q):
    """The two octilinear two-segment paths p->m->q (straight + 45)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    ax, ay = abs(dx), abs(dy)
    if ax < EPS or ay < EPS or abs(ax - ay) < EPS:
        return []
    sx, sy = math.copysign(1, dx), math.copysign(1, dy)
    d = min(ax, ay)
    if ax > ay:
        return [(p[0] + sx * d, p[1] + sy * d), (q[0] - sx * d, q[1] - sy * d)]
    return [(p[0] + sx * d, p[1] + sy * d), (q[0] - sx * d, q[1] - sy * d)]


def merge_collinear(pts, ws):
    op, ow = [pts[0]], []
    for k in range(1, len(pts)):
        if math.dist(op[-1], pts[k]) < EPS:
            continue
        if len(op) >= 2 and ow and ow[-1] == ws[k - 1] and \
           abs(turn(angle(op[-2], op[-1]), angle(op[-1], pts[k]))) < 0.01:
            op[-1] = pts[k]
            continue
        op.append(pts[k])
        ow.append(ws[k - 1])
    return op, ow


# ------------------------------------------------------------------ output
def fmt(x):
    s = ('%.6f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def emit_segment(s, bd):
    net = s['net']
    if bd.numeric_nets:
        inv = {v: k for k, v in bd.netnames.items()}
        nt = '(net %d)' % inv.get(net, 0)
    else:
        nt = '(net %s)' % q(net)
    lines = ['\t(segment', '\t\t(start %s %s)' % (fmt(s['a'][0]), fmt(s['a'][1])),
             '\t\t(end %s %s)' % (fmt(s['b'][0]), fmt(s['b'][1])), '\t\t(width %s)' % fmt(s['w'])]
    if s['locked']:
        lines.append('\t\t(locked yes)')
    lines += ['\t\t(layer %s)' % q(s['L']), '\t\t' + nt, '\t\t(uuid "%s")' % uuid.uuid4(), '\t)']
    return '\n'.join(lines)


def write(bd, ed, path):
    T = bd.text
    news = '\n'.join(emit_segment(s, bd) for s in ed.new.values() if s['oid'] in bd.segs)
    last = max((k for k, (_, _, tag) in enumerate(bd.blocks) if tag in ('segment', 'arc', 'via')), default=None)
    out = []
    pos = 0
    for k, (s, e, tag) in enumerate(bd.blocks):
        if k in ed.dropped:
            out.append(T[pos:s].rstrip(' \t'))
            pos = e
            if T[pos:pos + 1] == '\n':
                pos += 1
        else:
            out.append(T[pos:e])
            pos = e
        if k == last and news:
            if out and not out[-1].endswith('\n'):
                out.append('\n')
            out.append(news + ('\n' if k in ed.dropped else ''))
            news = ''
    out.append(T[pos:])
    txt = ''.join(out)
    if news:
        i = txt.rstrip().rfind(')')
        txt = txt[:i] + news + '\n' + txt[i:]
    parse(txt)
    open(path, 'w', encoding='utf-8').write(txt)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--report')
    ap.add_argument('--fine-pitch', type=float, default=0.5, help='pad pitch at or below which a pad row gets no new diagonals (mm)')
    ap.add_argument('--fine-margin', type=float, default=None, help='margin around fine-pitch pad rows (default = --fine-pitch)')
    ap.add_argument('--min-chamfer', type=float, default=0.0, help='smallest chamfer leg (mm, default = track width)')
    ap.add_argument('--max-chamfer', type=float, default=1.0, help='largest chamfer leg (mm)')
    ap.add_argument('--max-stub', type=float, default=0.0, help='remove dangling stubs only up to this length (0 = any)')
    ap.add_argument('--refill', action='store_true', help='ignore other-net zone fills (zones are refilled afterwards)')
    ap.add_argument('--skip-locked', action='store_true', help='leave locked tracks alone')
    ap.add_argument('--extra-clearance', action='append', default=[], metavar="'GLOB_A=GLOB_B:MM'",
                    help='extra net-pair clearance for new copper, e.g. "/Sense/*=/Heater/*:0.5"')
    ap.add_argument('--no-jogs', action='store_true')
    ap.add_argument('--no-chamfer', action='store_true')
    ap.add_argument('--no-stubs', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    base = os.path.splitext(a.board)[0]
    pro = base + '.kicad_pro'
    if not os.path.exists(pro):
        sys.exit('no %s beside the board: clearances unknown, refusing to run' % pro)
    rules = Rules(pro, base + '.kicad_dru', a.extra_clearance)
    bd = Board(a.board, rules, a.refill)
    bd.fine_pitch(a.fine_pitch, a.fine_margin if a.fine_margin is not None else a.fine_pitch)
    before, _ = stats(bd)
    ed = Editor(bd, a)
    n_stub = 0 if a.no_stubs else ed.stubs()
    n_jog, n_merge = (0, 0) if a.no_jogs else ed.straighten()
    n_ch = 0 if a.no_chamfer else ed.chamfer()
    # final collinear merge pass (chamfers never create collinear runs, jogs may)
    for c in build_chains(bd):
        if ed.skip(c) or len(c['pts']) < 3:
            continue
        ws = [bd.segs[s]['w'] for s in c['sids']]
        mp, mw = merge_collinear(c['pts'], ws)
        if len(mp) < len(c['pts']) and ed.keeps(ed.touchers(c), mp, mw):
            ed.replace(c, mp, mw, any(bd.segs[s]['locked'] for s in c['sids']))
            n_merge += len(c['pts']) - len(mp)
    n_td = ed.remove_teardrops()
    after, chains = stats(bd)
    # remaining jogs with reasons
    left = []
    for c in chains:
        for k, kind, off in jogs(c['pts']):
            p = c['pts']
            a0, a3 = p[max(0, k - 1)], p[min(len(p) - 1, k + 2)]
            if octi(a0, a3) is not None:
                ex = ed.exempt_for(c)
                hw = bd.segs[c['sids'][0]]['w'] / 2
                why = bd.check(a0, a3, hw, c['net'], c['L'], ex) or 'straight path clear but the chain ends need the bends'
            else:
                why = 'ends offset (%.3f mm): the terminals are not aligned' % off
            left.append('%s %s %s at (%.3f, %.3f), offset %.3f mm: %s' % (c['net'], c['L'], kind, p[k][0], p[k][1], off, why))
    cats = sorted(set(before) | set(after))
    lines = ['# Trace clean-up report', '', 'Input `%s`, output `%s`%s.' % (a.board, a.out, ' (dry run, not written)' if a.dry_run else ''), '',
             'Re-run `kicad-cli pcb drc --refill-zones --schematic-parity --severity-all` beside the original .kicad_pro: '
             'this pass checks geometry only.', '', '| Category | Before | After |', '|---|---|---|']
    for k in cats:
        lines.append('| %s | %d | %d |' % (k, before.get(k, 0), after.get(k, 0)))
    lines += ['', 'Changes: %d bends removed in %d chains (jogs/doglegs/U-turns/detours), %d collinear vertices merged, '
              '%d dangling stubs removed, %d 90-degree corners chamfered, %d teardrops removed at changed ends.'
              % (n_jog, len(ed.log['jog fixed']), n_merge, n_stub, n_ch, n_td), '']
    lines += ['## Rules', ''] + ['- ' + x for x in rules.notes] + ['- not evaluated: ' + x for x in rules.unevaluated] + \
             ['- fine-pitch rows (no new diagonals): ' + ', '.join(sorted({'%s %s' % (r, L) for L, _, r in bd.fine_zones})) or '- none', '']
    lines += ['## Jogs fixed', '', '| Net | Layer | at | Deviation mm | Bends before -> after | Kind | Locked |', '|---|---|---|---|---|---|---|']
    for j in ed.log['jog fixed']:
        lines.append('| %s | %s | (%.3f, %.3f) | %.3f | %d -> %d | %s | %s |' % (j['net'], j['L'], j['at'][0], j['at'][1], j['dev'], j['bends'][0], j['bends'][1], j['kind'], 'yes' if j['locked'] else ''))
    lines += ['', '## Jogs left', ''] + ['- ' + x for x in left] + ['- ' + x for x in ed.log['jog left']] + ['']
    lines += ['## 90-degree corners left', ''] + ['- ' + x for x in ed.log['corner left'] if x] + ['']
    lines += ['## Stubs removed', ''] + ['- ' + x for x in ed.log['stub removed']] + ['- ' + x for x in ed.log['stub left']] + ['']
    rep = '\n'.join(lines)
    if a.report:
        open(a.report, 'w').write(rep + '\n')
    js = dict(before=before, after=after, jogs_fixed=[{k: v for k, v in j.items() if k != 'sids'} for j in ed.log['jog fixed']],
              corners_left=ed.log['corner left'], jogs_left=left, chamfered=len(ed.log['corner chamfered']), stubs=ed.log['stub removed'],
              teardrops_removed=n_td)
    if a.report:
        json.dump(js, open(os.path.splitext(a.report)[0] + '.json', 'w'), indent=1, default=str)
    print('before', before)
    print('after ', after)
    print('jog bends removed %d, merged %d, stubs %d, chamfered %d, teardrops removed %d, corners left %d, jogs left %d'
          % (n_jog, n_merge, n_stub, n_ch, n_td, len(ed.log['corner left']), len(left)))
    if not a.dry_run:
        write(bd, ed, a.out)
        print('written', a.out)


if __name__ == '__main__':
    main()
