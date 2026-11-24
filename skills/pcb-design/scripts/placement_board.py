#!/usr/bin/env python3
"""Interactive placement review board (SKILL.md G5, "Placement review").

    python placement_board.py export board.kicad_pcb -o outdir [--classes classes.json] [--title "..."]
    python placement_board.py apply board.kicad_pcb moves.json -o new.kicad_pcb [--report report.md]
                              [--classes classes.json] [--allow-locked] [--strip-tracks-of REFS|moved]
                              [--no-validate] [--drc-refill]
    python placement_board.py moves-from-db db_list.json -o moves.json [--review review.json]

export   writes <outdir>/layout.json (outline, footprints with courtyards and pads, class
         fixed / region / free, regions and keep-outs, per-net ratsnest) and <outdir>/index.html
         (the review page; publish both together as an Artifact with capabilities {"db": {}}).
apply    moves footprints to the positions in moves.json ([{ref, x, y, rot, side?}], mm and
         degrees, KiCad convention). Only each footprint's own (at), its pads' and texts'
         angles and the absolute polygons of zones inside it are rewritten. Fixed and locked
         parts are refused; tracks are left in place and reported as stale.
moves-from-db converts an ArtifactData `list` export of the page's `moves` collection into
         moves.json (and prints the review state from a `review` export).

classes.json: {"fixed": ["U1", "J*"], "region": {"TP*": "testpoints"}, "free": ["C*", "R*"],
               "regions": {"testpoints": [[x, y], ...]  or  [[[x, y], ...], [[x, y], ...]]}}
Exact refs win over glob patterns; among globs fixed > region > free. A region polygon
comes from classes.json "regions" or from a named rule area in the board with that name.
Without a classes file, locked footprints are fixed and everything else is free.
"""
import argparse
import fnmatch
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr                                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'placement_board_template.html')
KICAD_CLI_DEFAULT = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
POWER_NET = re.compile(r'^(/.*/)?([AD]?GND\w*|VSS\w*|VCC\w*|VDD\w*|V?BAT\w*|[+-]\S+)$', re.I)
DRAWING_LAYERS = ('Dwgs.User', 'Cmts.User', 'Eco1.User', 'Eco2.User')


# ---------------------------------------------------------------- small helpers

def r4(v):
    return round(float(v), 4)


def fnum(v):
    """Format a number the way KiCad writes it (no trailing zeros, no -0)."""
    s = ('%.6f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def norm180(a):
    a = math.fmod(a, 360.0)
    if a <= -180:
        a += 360
    if a > 180:
        a -= 360
    return 0.0 if abs(a) < 1e-9 else a


def norm360(a):
    a = math.fmod(a, 360.0)
    if a < 0:
        a += 360
    return 0.0 if abs(a) < 1e-9 or abs(a - 360) < 1e-9 else a


def rot_pt(x, y, deg):
    """KiCad footprint-local -> board offset (y down, positive angle counter-clockwise)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return x * c + y * s, -x * s + y * c


def fl(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def layer_of(node):
    l = sexpr.child(node, 'layer')
    return l[1] if l and len(l) > 1 else ''


def prop(fp, name):
    for p in sexpr.children(fp, 'property'):
        if len(p) > 2 and p[1] == name:
            return str(p[2])
    for t in sexpr.children(fp, 'fp_text'):       # KiCad 6/7 boards
        if len(t) > 2 and t[1] == name.lower():
            return str(t[2])
    return ''


def is_locked(fp):
    lk = sexpr.child(fp, 'locked')
    if lk is not None:
        return len(lk) == 1 or lk[1] == 'yes'
    return 'locked' in fp[1:4]


def xy(node, tag):
    c = sexpr.child(node, tag)
    return (fl(c[1]), fl(c[2])) if c and len(c) > 2 else None


def arc_points(p0, pm, p1, max_seg_deg=10.0):
    """Approximate a three-point arc by a polyline (includes both ends)."""
    (ax, ay), (bx, by), (cx, cy) = p0, pm, p1
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [p0, p1]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0, tm, t1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (p0, pm, p1))

    def ccw_span(a, b):
        return (b - a) % (2 * math.pi)
    sweep = ccw_span(t0, t1)
    if ccw_span(t0, tm) > sweep:           # the mid point is on the other way round
        sweep = sweep - 2 * math.pi
    n = max(2, int(abs(math.degrees(sweep)) / max_seg_deg) + 1)
    pts = [(ux + r * math.cos(t0 + sweep * i / n), uy + r * math.sin(t0 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = p0, p1
    return pts


def circle_points(c, r, n=32):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def pts_list(pts_node):
    """Points of a (pts ...) node: xy entries and arcs expanded."""
    out = []
    for c in pts_node[1:]:
        if not isinstance(c, list):
            continue
        if c[0] == 'xy':
            out.append((fl(c[1]), fl(c[2])))
        elif c[0] == 'arc':
            a = arc_points(xy(c, 'start'), xy(c, 'mid'), xy(c, 'end'))
            if out and math.hypot(out[-1][0] - a[0][0], out[-1][1] - a[0][1]) < 1e-6:
                a = a[1:]
            out.extend(a)
    return out


def shape_paths(g, kind):
    """A graphic item -> list of (points, closed). kind is the tag without gr_/fp_ prefix."""
    if kind == 'line':
        return [([xy(g, 'start'), xy(g, 'end')], False)]
    if kind == 'arc':
        return [(arc_points(xy(g, 'start'), xy(g, 'mid'), xy(g, 'end')), False)]
    if kind == 'rect':
        (x0, y0), (x1, y1) = xy(g, 'start'), xy(g, 'end')
        return [([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)]
    if kind == 'circle':
        c, e = xy(g, 'center'), xy(g, 'end')
        return [(circle_points(c, math.hypot(e[0] - c[0], e[1] - c[1])), True)]
    if kind == 'poly':
        p = sexpr.child(g, 'pts')
        return [(pts_list(p), True)] if p else []
    return []


def chain(paths, tol=0.01):
    """Join open polylines end to end into loops / longer polylines. Returns [(pts, closed)]."""
    done = [(p, True) for p, closed in paths if closed and len(p) > 2]
    open_ = [list(p) for p, closed in paths if not closed and len(p) > 1]

    def near(a, b):
        return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol
    while open_:
        cur = open_.pop()
        grew = True
        while grew and not near(cur[0], cur[-1]):
            grew = False
            for i, p in enumerate(open_):
                if near(cur[-1], p[0]):
                    cur += p[1:]
                elif near(cur[-1], p[-1]):
                    cur += p[::-1][1:]
                elif near(cur[0], p[-1]):
                    cur = p[:-1] + cur
                elif near(cur[0], p[0]):
                    cur = p[::-1][:-1] + cur
                else:
                    continue
                open_.pop(i)
                grew = True
                break
        closed = len(cur) > 2 and near(cur[0], cur[-1])
        done.append((cur[:-1] if closed else cur, closed))
    return done


def mst(points):
    """Prim's MST on a list of (x, y); returns index pairs."""
    n = len(points)
    if n < 2:
        return []
    INF = float('inf')
    best = [INF] * n
    link = [-1] * n
    used = [False] * n
    best[0] = 0
    edges = []
    for _ in range(n):
        u, bu = -1, INF
        for i in range(n):
            if not used[i] and best[i] < bu:
                u, bu = i, best[i]
        used[u] = True
        if link[u] >= 0:
            edges.append((link[u], u))
        ux, uy = points[u]
        for i in range(n):
            if not used[i]:
                d = (points[i][0] - ux) ** 2 + (points[i][1] - uy) ** 2
                if d < best[i]:
                    best[i], link[i] = d, u
    return edges


# ---------------------------------------------------------------- classes

def load_classes(path):
    if not path:
        return None
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    c.setdefault('fixed', [])
    c.setdefault('region', {})
    c.setdefault('free', [])
    c.setdefault('regions', {})
    if isinstance(c['region'], list):          # tolerate ["TP*:testpoints", ...]
        c['region'] = dict(s.split(':', 1) for s in c['region'])
    return c


def classify(ref, locked, classes):
    """-> (class, region name or None, explicit?)"""
    if classes is None:
        return ('fixed' if locked else 'free'), None, False
    if ref in classes['fixed']:
        return 'fixed', None, True
    if ref in classes['region']:
        return 'region', classes['region'][ref], True
    if ref in classes['free']:
        return 'free', None, True
    for pat in classes['fixed']:
        if fnmatch.fnmatchcase(ref, pat):
            return 'fixed', None, True
    for pat, name in classes['region'].items():
        if fnmatch.fnmatchcase(ref, pat):
            return 'region', name, True
    for pat in classes['free']:
        if fnmatch.fnmatchcase(ref, pat):
            return 'free', None, True
    return ('fixed' if locked else 'free'), None, False


def region_polys(spec):
    """classes.json region value -> list of polygons."""
    if not spec:
        return []
    if isinstance(spec[0][0], (int, float)):
        return [[(float(x), float(y)) for x, y in spec]]
    return [[(float(x), float(y)) for x, y in p] for p in spec]


# ---------------------------------------------------------------- netclasses

def netclass_map(board_path):
    pro = os.path.splitext(board_path)[0] + '.kicad_pro'
    assign, patterns = {}, []
    if os.path.exists(pro):
        try:
            with open(pro, encoding='utf-8') as f:
                ns = json.load(f).get('net_settings', {})
            for net, cls in (ns.get('netclass_assignments') or {}).items():
                assign[net] = cls[0] if isinstance(cls, list) and cls else cls
            for p in ns.get('netclass_patterns') or []:
                patterns.append((p.get('pattern', ''), p.get('netclass', 'Default')))
        except (OSError, ValueError):
            pass

    def lookup(net):
        if net in assign:
            return assign[net]
        for pat, cls in patterns:
            if pat == net or fnmatch.fnmatchcase(net, pat):
                return cls
            try:
                if re.fullmatch(pat, net):
                    return cls
            except re.error:
                pass
        return 'Default'
    return lookup, os.path.exists(pro)


# ---------------------------------------------------------------- export

def footprint_record(fp):
    ref = prop(fp, 'Reference')
    fx, fy, frot = sexpr.at(fp) or (0.0, 0.0, 0.0)
    side = 'B' if layer_of(fp).startswith('B.') else 'F'
    pads = []
    for pd in sexpr.children(fp, 'pad'):
        a = sexpr.at(pd) or (0.0, 0.0, 0.0)
        size = sexpr.child(pd, 'size')
        w, h = (fl(size[1]), fl(size[2] if len(size) > 2 else size[1])) if size else (0.5, 0.5)
        net = sexpr.child(pd, 'net')
        netname = None
        if net and len(net) > 1:
            netname = str(net[-1]) if len(net) > 2 else str(net[1])   # (net 3 "name") or (net "name")
        if netname == '' or netname is None:
            netname = None
        lyrs = ' '.join(str(v) for v in (sexpr.child(pd, 'layers') or [])[1:])
        pl = ('F' if ('F.Cu' in lyrs or '*.Cu' in lyrs) else '') + ('B' if ('B.Cu' in lyrs or '*.Cu' in lyrs) else '')
        pads.append({'num': str(pd[1]) if len(pd) > 1 else '', 'x': r4(a[0]), 'y': r4(a[1]),
                     'w': r4(w), 'h': r4(h), 'a': r4(norm180(a[2] - frot)),
                     'shape': str(pd[3]) if len(pd) > 3 else 'rect', 'net': netname, 'l': pl or side})
    crt = []
    for g in fp:
        if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_arc', 'fp_rect', 'fp_circle', 'fp_poly'):
            if layer_of(g).endswith('.CrtYd'):
                crt += shape_paths(g, g[0][3:])
    crt = chain(crt)
    if crt:
        allp = [p for path, _ in crt for p in path]
        bbox = [min(p[0] for p in allp), min(p[1] for p in allp), max(p[0] for p in allp), max(p[1] for p in allp)]
        src = 'courtyard'
    else:
        ext = []
        for p in pads:
            hw, hh = p['w'] / 2, p['h'] / 2
            c, s = abs(math.cos(math.radians(p['a']))), abs(math.sin(math.radians(p['a'])))
            ex, ey = hw * c + hh * s, hw * s + hh * c
            ext.append((p['x'] - ex, p['y'] - ey, p['x'] + ex, p['y'] + ey))
        if ext:
            bbox = [min(e[0] for e in ext) - 0.25, min(e[1] for e in ext) - 0.25,
                    max(e[2] for e in ext) + 0.25, max(e[3] for e in ext) + 0.25]
        else:
            bbox = [-0.5, -0.5, 0.5, 0.5]
        crt = [([(bbox[0], bbox[1]), (bbox[2], bbox[1]), (bbox[2], bbox[3]), (bbox[0], bbox[3])], True)]
        src = 'pads'
    return {'ref': ref, 'value': prop(fp, 'Value'), 'footprint': str(fp[1]) if len(fp) > 1 else '',
            'side': side, 'x': r4(fx), 'y': r4(fy), 'rot': r4(norm180(frot)),
            'courtyard': [{'pts': [[r4(x), r4(y)] for x, y in path], 'closed': closed} for path, closed in crt],
            'courtyard_source': src, 'bbox': [r4(v) for v in bbox], 'pads': pads,
            'locked': is_locked(fp)}


def zone_layers(z):
    l = sexpr.child(z, 'layers') or sexpr.child(z, 'layer')
    return [str(v) for v in l[1:]] if l else []


def zone_polys(z):
    out = []
    for p in sexpr.children(z, 'polygon'):
        pts = sexpr.child(p, 'pts')
        if pts:
            out.append(pts_list(pts))
    return out


def board_outline(root):
    paths = []
    for g in root:
        if isinstance(g, list) and g and g[0] in ('gr_line', 'gr_arc', 'gr_rect', 'gr_circle', 'gr_poly'):
            if layer_of(g) == 'Edge.Cuts':
                paths += shape_paths(g, g[0][3:])
    for fp in sexpr.children(root, 'footprint'):
        fx, fy, frot = sexpr.at(fp) or (0, 0, 0)
        for g in fp:
            if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_arc', 'fp_rect', 'fp_circle', 'fp_poly'):
                if layer_of(g) == 'Edge.Cuts':
                    for pts, closed in shape_paths(g, g[0][3:]):
                        paths.append(([(fx + rot_pt(x, y, frot)[0], fy + rot_pt(x, y, frot)[1]) for x, y in pts], closed))
    return chain(paths)


def export(a):
    root = sexpr.load(a.board)
    classes = load_classes(a.classes)
    lookup, have_pro = netclass_map(a.board)
    warnings = []
    if not have_pro:
        warnings.append('no .kicad_pro beside the board: netclasses unknown')

    fps = []
    for fp in sexpr.children(root, 'footprint'):
        rec = footprint_record(fp)
        if not rec['ref'] or rec['ref'].startswith('#') or rec['ref'] == 'REF**':
            continue
        cls, region, explicit = classify(rec['ref'], rec['locked'], classes)
        rec['class'], rec['region'], rec['classified'] = cls, region, explicit
        fps.append(rec)

    outline = board_outline(root)
    outline_out = [{'pts': [[r4(x), r4(y)] for x, y in p], 'closed': c} for p, c in outline]
    if not outline:
        warnings.append('no Edge.Cuts outline found')

    areas = []
    for z in sexpr.children(root, 'zone'):
        ko = sexpr.child(z, 'keepout')
        nm = sexpr.child(z, 'name')
        if not ko:
            continue                       # copper pour (named or not): not drawn
        name = str(nm[1]) if nm else ''
        restricted = [c[0] for c in ko[1:] if isinstance(c, list) and len(c) > 1 and c[1] == 'not_allowed']
        kind = 'keepout' if restricted else 'rule_area'
        for poly in zone_polys(z):
            areas.append({'name': name or ('keep-out' if kind == 'keepout' else 'rule area'), 'kind': kind,
                          'layers': zone_layers(z), 'restricts': restricted,
                          'polygon': [[r4(x), r4(y)] for x, y in poly]})
    for fp in sexpr.children(root, 'footprint'):
        ref = prop(fp, 'Reference')
        for z in sexpr.children(fp, 'zone'):          # footprint rule areas: absolute coordinates
            ko = sexpr.child(z, 'keepout')
            if not ko:
                continue
            restricted = [c[0] for c in ko[1:] if isinstance(c, list) and len(c) > 1 and c[1] == 'not_allowed']
            nm = sexpr.child(z, 'name')
            for poly in zone_polys(z):
                areas.append({'name': str(nm[1]) if nm else '%s keep-out' % ref, 'owner': ref,
                              'kind': 'keepout' if restricted else 'rule_area', 'layers': zone_layers(z),
                              'restricts': restricted, 'polygon': [[r4(x), r4(y)] for x, y in poly]})
    user_layers = set(DRAWING_LAYERS)
    for g in root:
        if isinstance(g, list) and g and g[0] in ('gr_rect', 'gr_poly', 'gr_circle', 'gr_line', 'gr_arc'):
            l = layer_of(g)
            if l in user_layers or re.fullmatch(r'User\.\d+', l):
                for pts, closed in shape_paths(g, g[0][3:]):
                    areas.append({'name': l, 'kind': 'user_drawing', 'layers': [l], 'closed': closed,
                                  'polygon': [[r4(x), r4(y)] for x, y in pts]})

    # regions referenced by the classes
    regions = {}
    used = sorted({f['region'] for f in fps if f['region']})
    for name in used:
        polys = region_polys((classes or {}).get('regions', {}).get(name))
        src = 'classes.json'
        if not polys:
            polys = [ar['polygon'] for ar in areas if ar['kind'] != 'user_drawing' and ar['name'] == name]
            src = 'board rule area'
        if not polys:
            warnings.append('region "%s" has no polygon (classes.json "regions" or a named rule area): '
                            'its parts are not held' % name)
            continue
        regions[name] = True
        for p in polys:
            areas.append({'name': name, 'kind': 'region', 'layers': [], 'source': src,
                          'polygon': [[r4(x), r4(y)] for x, y in p]})

    # nets and ratsnest
    nets = {}
    for f in fps:
        for i, p in enumerate(f['pads']):
            if p['net'] and not p['net'].startswith('unconnected-'):
                gx, gy = rot_pt(p['x'], p['y'], f['rot'])
                nets.setdefault(p['net'], []).append((f['ref'], i, f['x'] + gx, f['y'] + gy))
    ratsnest, netinfo = [], {}
    for net, members in sorted(nets.items()):
        cls = lookup(net)
        power = bool(POWER_NET.match(net)) or bool(re.search(r'power|pwr|gnd', cls, re.I))
        netinfo[net] = {'netclass': cls, 'power': power, 'pads': len(members)}
        if len(members) < 2:
            continue
        edges = mst([(m[2], m[3]) for m in members])
        ratsnest.append({'net': net, 'netclass': cls, 'power': power,
                         'segments': [[r4(members[i][2]), r4(members[i][3]), r4(members[j][2]), r4(members[j][3])]
                                      for i, j in edges]})

    unclassified = [f['ref'] for f in fps if classes is not None and not f['classified']]
    if unclassified:
        warnings.append('%d part(s) not in classes.json (defaulted: locked -> fixed, else free): %s' % (
            len(unclassified), ', '.join(unclassified[:20]) + (' ...' if len(unclassified) > 20 else '')))
    locked_movable = [f['ref'] for f in fps if f['locked'] and f['class'] != 'fixed']
    if locked_movable:
        warnings.append('%d part(s) are locked in KiCad but classed region/free: %s (apply needs --allow-locked)' % (
            len(locked_movable), ', '.join(locked_movable[:20]) + (' ...' if len(locked_movable) > 20 else '')))

    allpts = [p for o in outline for p in o[0]] or [(f['x'], f['y']) for f in fps] or [(0, 0)]
    layout = {
        'version': 1, 'units': 'mm', 'generator': 'placement_board.py',
        'title': a.title or os.path.splitext(os.path.basename(a.board))[0],
        'board': os.path.basename(a.board), 'exported': time.strftime('%Y-%m-%d %H:%M'),
        'bounds': [r4(min(p[0] for p in allpts)), r4(min(p[1] for p in allpts)),
                   r4(max(p[0] for p in allpts)), r4(max(p[1] for p in allpts))],
        'outline': outline_out,
        'footprints': fps,
        'areas': areas,
        'nets': netinfo,
        'ratsnest': ratsnest,
        'conventions': {'rotation': 'degrees, counter-clockwise positive as in KiCad; y grows downwards',
                        'pad_xy': 'footprint-local, unrotated', 'pad_a': 'pad angle relative to the footprint',
                        'board_from_local': 'x = X + lx*cos(r) + ly*sin(r); y = Y - lx*sin(r) + ly*cos(r)'},
        'warnings': warnings,
    }
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'layout.json'), 'w', encoding='utf-8') as f:
        json.dump(layout, f, separators=(',', ':'))
    with open(TEMPLATE, encoding='utf-8') as f:
        page = f.read()
    page = page.replace('__TITLE__', html.escape(a.title or 'Placement Review'))
    with open(os.path.join(a.out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)
    counts = {}
    for f_ in fps:
        counts[f_['class']] = counts.get(f_['class'], 0) + 1
    print('%s: %d footprints (%s), %d pads, %d nets with ratsnest, %d areas' % (
        os.path.basename(a.board), len(fps), ', '.join('%d %s' % (v, k) for k, v in sorted(counts.items())),
        sum(len(f_['pads']) for f_ in fps), len(ratsnest), len(areas)))
    for w in warnings:
        print('  [warn ] ' + w)
    print('  wrote %s and %s' % (os.path.join(a.out, 'layout.json'), os.path.join(a.out, 'index.html')))
    return 0


# ---------------------------------------------------------------- span scanner (for apply)

_TOK = re.compile(r'"(?:[^"\\]|\\.)*"|[()]', re.S)


def list_spans(text, start=0, end=None):
    """Direct child lists of the block text[start:end] (start at its '(').
    Returns [(tag, s, e)] with text[s] == '(' and text[e-1] == ')'."""
    end = len(text) if end is None else end
    out, depth, cs = [], 0, None
    for m in _TOK.finditer(text, start, end):
        t = m.group(0)
        if t == '(':
            depth += 1
            if depth == 2:
                cs = m.start()
        elif t == ')':
            depth -= 1
            if depth == 1 and cs is not None:
                tm = re.match(r'\(\s*([^\s()"]+)', text[cs:cs + 64])
                out.append((tm.group(1) if tm else '', cs, m.end()))
                cs = None
            if depth == 0:
                break
    return out


def top_spans(text):
    """Top-level blocks inside the root (kicad_pcb ...)."""
    i = text.index('(')
    return list_spans(text, i)


def removal(text, s, e):
    """Span that deletes the block text[s:e] together with its own line when it is alone on it."""
    ls = text.rfind('\n', 0, s) + 1
    if text[ls:s].strip() == '':
        s = ls
        if text[e:e + 1] == '\n':
            e += 1
    return (s, e, '')


def apply_moves(a):
    with open(a.board, encoding='utf-8') as f:
        text = f.read()
    with open(a.moves, encoding='utf-8') as f:
        moves = json.load(f)
    if isinstance(moves, dict):
        moves = moves.get('moves') or list(moves.values())
    classes = load_classes(a.classes)
    by_ref = {}
    for m in moves:
        if m.get('ref'):
            by_ref[str(m['ref'])] = m

    spans = top_spans(text)
    edits = []                 # (s, e, replacement)
    report = {'moved': [], 'refused': [], 'unchanged': [], 'missing': [], 'stale': {}, 'stripped': {}}
    moved_nets, moved_refs, fp_nets = set(), [], {}
    seen = set()
    for tag, s, e in spans:
        if tag != 'footprint':
            continue
        node = sexpr.parse(text[s:e])
        ref = prop(node, 'Reference')
        nets_here = set()
        for pd in sexpr.children(node, 'pad'):
            n = sexpr.child(pd, 'net')
            if n and len(n) > 1 and str(n[-1]):
                nets_here.add(str(n[-1]))
        fp_nets[ref] = nets_here
        if ref not in by_ref:
            continue
        seen.add(ref)
        m = by_ref[ref]
        ox, oy, orot = sexpr.at(node) or (0.0, 0.0, 0.0)
        side = 'B' if layer_of(node).startswith('B.') else 'F'
        try:
            nx, ny = float(m['x']), float(m['y'])
            nrot = norm180(float(m.get('rot', orot)))
        except (KeyError, TypeError, ValueError):
            report['refused'].append((ref, 'bad x / y / rot in moves.json'))
            continue
        locked = is_locked(node)
        cls, _, _ = classify(ref, locked, classes)
        if m.get('side') and str(m['side'])[:1].upper() != side:
            report['refused'].append((ref, 'side change %s -> %s is not supported: flip it in KiCad' % (side, m['side'])))
            continue
        if abs(nx - ox) < 1e-6 and abs(ny - oy) < 1e-6 and abs(norm180(nrot - orot)) < 1e-6:
            report['unchanged'].append(ref)
            continue
        if cls == 'fixed':
            report['refused'].append((ref, 'fixed part'))
            continue
        if locked and not a.allow_locked:
            report['refused'].append((ref, 'locked in KiCad (re-run with --allow-locked if its class allows moving)'))
            continue
        delta = norm180(nrot - orot)
        local = []
        for ctag, cs_, ce in list_spans(text, s, e):
            if ctag == 'at':
                vals = sexpr.parse(text[cs_:ce])
                rep = '(at %s %s%s)' % (fnum(nx), fnum(ny), '' if abs(nrot) < 1e-9 else ' ' + fnum(nrot))
                extra = [str(v) for v in vals[1:] if not sexpr._isnum(v)]
                if extra:
                    rep = rep[:-1] + ' ' + ' '.join(extra) + ')'
                local.append((cs_, ce, rep))
            elif ctag in ('pad', 'property', 'fp_text') and abs(delta) > 1e-9:
                for gtag, gs, ge in list_spans(text, cs_, ce):
                    if gtag != 'at':
                        continue
                    vals = sexpr.parse(text[gs:ge])
                    nums = [v for v in vals[1:] if sexpr._isnum(v)]
                    extra = [str(v) for v in vals[1:] if not sexpr._isnum(v)]
                    ang = norm360((float(nums[2]) if len(nums) > 2 else 0.0) + delta)
                    rep = '(at %s %s' % (nums[0], nums[1])
                    if ctag != 'pad' or abs(ang) > 1e-9:
                        rep += ' ' + fnum(ang)
                    rep += (' ' + ' '.join(extra) if extra else '') + ')'
                    local.append((gs, ge, rep))
            elif ctag == 'zone':
                # zones inside a footprint store absolute coordinates: transform them, drop stale fill
                for ztag, zs, ze in list_spans(text, cs_, ce):
                    if ztag == 'filled_polygon':
                        local.append(removal(text, zs, ze))
                    elif ztag == 'polygon':
                        for ptag, ps, pe in list_spans(text, zs, ze):
                            if ptag != 'pts':
                                continue
                            for xtag, xs, xe in list_spans(text, ps, pe):
                                targets = [(xs, xe)] if xtag == 'xy' else \
                                    [(q[1], q[2]) for q in list_spans(text, xs, xe) if q[0] in ('start', 'mid', 'end')] \
                                    if xtag == 'arc' else []
                                for ts, te in targets:
                                    v = sexpr.parse(text[ts:te])
                                    lx, ly = rot_pt(float(v[1]) - ox, float(v[2]) - oy, -orot)    # board -> local
                                    bx, by = rot_pt(lx, ly, nrot)
                                    local.append((ts, te, '(%s %s %s)' % (v[0], fnum(nx + bx), fnum(ny + by))))
        edits += local
        moved_refs.append(ref)
        moved_nets |= nets_here
        report['moved'].append((ref, (ox, oy, orot), (nx, ny, nrot)))
    report['missing'] = sorted(set(by_ref) - seen)

    strip_refs = set()
    if a.strip_tracks_of:
        if a.strip_tracks_of.strip().lower() == 'moved':
            strip_refs = set(moved_refs)
        else:
            strip_refs = {r.strip() for r in a.strip_tracks_of.split(',') if r.strip()}
    strip_nets = set()
    for r in strip_refs:
        strip_nets |= fp_nets.get(r, set())
    for tag, s, e in spans:
        if tag not in ('segment', 'arc', 'via'):
            continue
        for ctag, cs_, ce in list_spans(text, s, e):
            if ctag == 'net':
                v = sexpr.parse(text[cs_:ce])
                net = str(v[-1]) if len(v) > 1 else ''
                if net in strip_nets:
                    report['stripped'][net] = report['stripped'].get(net, 0) + 1
                    edits.append(removal(text, s, e))
                elif net in moved_nets:
                    report['stale'][net] = report['stale'].get(net, 0) + 1
                break

    edits.sort()
    for i in range(1, len(edits)):
        if edits[i][0] < edits[i - 1][1]:
            raise SystemExit('internal error: overlapping edits at %d' % edits[i][0])
    out, pos = [], 0
    for s, e, rep in edits:
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:])
    new = ''.join(out)
    sexpr.parse(new)            # must still parse
    if os.path.abspath(a.out) == os.path.abspath(a.board):
        raise SystemExit('refusing to overwrite the input board; write to a new file')
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(new)

    validation = None if a.no_validate else validate(a)
    lines = ['# Placement apply report', '',
             '- input: `%s`' % a.board, '- moves: `%s` (%d entries)' % (a.moves, len(by_ref)), '- output: `%s`' % a.out, '']
    lines.append('## Moved (%d)' % len(report['moved']))
    for ref, o, n in report['moved']:
        lines.append('- %s: (%.4f, %.4f) %g deg -> (%.4f, %.4f) %g deg' % (ref, o[0], o[1], o[2], n[0], n[1], n[2]))
    if report['refused']:
        lines += ['', '## Refused (%d)' % len(report['refused'])] + ['- %s: %s' % r for r in report['refused']]
    if report['unchanged']:
        lines += ['', '## Unchanged (%d)' % len(report['unchanged']), '- ' + ', '.join(report['unchanged'])]
    if report['missing']:
        lines += ['', '## Not on the board (%d)' % len(report['missing']), '- ' + ', '.join(report['missing'])]
    if report['stale']:
        lines += ['', '## Stale tracks (%d segments/vias on %d nets)' % (sum(report['stale'].values()), len(report['stale'])),
                  'Tracks were not moved with the parts. Re-route or delete them (or re-run with '
                  '`--strip-tracks-of moved`).', '']
        lines += ['- %s: %d' % kv for kv in sorted(report['stale'].items())]
    if report['stripped']:
        lines += ['', '## Stripped tracks (%d segments/vias)' % sum(report['stripped'].values())]
        lines += ['- %s: %d' % kv for kv in sorted(report['stripped'].items())]
    if validation:
        lines += ['', '## Validation', validation]
    md = '\n'.join(lines) + '\n'
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write(md)
    print(md)
    return 0 if validation is None or not validation.startswith('FAILED') else 2


def find_cli():
    for c in (os.environ.get('KICAD_CLI'), KICAD_CLI_DEFAULT, shutil.which('kicad-cli')):
        if c and os.path.exists(c):
            return c
    return None


def validate(a):
    cli = find_cli()
    if not cli:
        return 'skipped: kicad-cli not found (set KICAD_CLI)'
    base_in, base_out = os.path.splitext(a.board)[0], os.path.splitext(a.out)[0]
    copied = []
    for ext in ('.kicad_pro', '.kicad_dru'):
        if os.path.exists(base_in + ext) and not os.path.exists(base_out + ext):
            shutil.copyfile(base_in + ext, base_out + ext)
            copied.append(os.path.basename(base_out + ext))
    with tempfile.TemporaryDirectory() as td:
        rpt = os.path.join(td, 'drc.json')
        cmd = [cli, 'pcb', 'drc', '--format', 'json', '-o', rpt] + (['--refill-zones'] if a.drc_refill else []) + [a.out]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if not os.path.exists(rpt):
            return 'FAILED: kicad-cli could not load the output (exit %d): %s' % (p.returncode, (p.stderr or p.stdout).strip()[-400:])
        with open(rpt, encoding='utf-8') as f:
            d = json.load(f)
    viol = d.get('violations', [])
    errs = sum(1 for v in viol if v.get('severity') == 'error')
    msg = 'kicad-cli loaded the board and ran DRC%s: %d violation(s) (%d errors), %d unconnected item(s).' % (
        ' with zone refill' if a.drc_refill else ' without zone refill (load check; use --drc-refill for real connectivity)',
        len(viol), errs, len(d.get('unconnected_items', [])))
    if copied:
        msg += ' Copied %s beside the output so the board rules apply.' % ', '.join(copied)
    return msg


# ---------------------------------------------------------------- moves-from-db

def _docs(obj):
    if isinstance(obj, dict):
        for k in ('docs', 'documents', 'items', 'results', 'data'):
            if isinstance(obj.get(k), list):
                return obj[k]
        if 'id' in obj or 'data' in obj:
            return [obj]
        return [dict(v, id=k) if isinstance(v, dict) else v for k, v in obj.items()]
    return obj if isinstance(obj, list) else []


def _body(doc):
    if isinstance(doc, dict) and isinstance(doc.get('data'), dict):
        b = dict(doc['data'])
        b.setdefault('_id', doc.get('id'))
        return b
    return doc if isinstance(doc, dict) else {}


def moves_from_db(a):
    with open(a.db_list, encoding='utf-8') as f:
        docs = _docs(json.load(f))
    out = []
    for d in docs:
        b = _body(d)
        ref = b.get('ref') or b.get('_id') or (d.get('id') if isinstance(d, dict) else None)
        if not ref or b.get('x') is None or b.get('y') is None:
            continue
        m = {'ref': str(ref), 'x': float(b['x']), 'y': float(b['y']), 'rot': float(b.get('rot') or 0)}
        if b.get('side'):
            m['side'] = b['side']
        if b.get('note'):
            m['note'] = b['note']
        if b.get('updatedAt'):
            m['updatedAt'] = b['updatedAt']
        out.append(m)
    out.sort(key=lambda m: m['ref'])
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    print('wrote %d move(s) to %s' % (len(out), a.out))
    for m in out:
        if m.get('note'):
            print('  note %s: %s' % (m['ref'], m['note']))
    if a.review:
        with open(a.review, encoding='utf-8') as f:
            rv = _docs(json.load(f))
        st = None
        for d in rv:
            b = _body(d)
            if b.get('_id', d.get('id') if isinstance(d, dict) else None) in (None, 'status') or 'state' in b:
                st = b
                break
        if st and st.get('state'):
            print('review: %s%s%s' % (st['state'], (' at ' + st['updatedAt']) if st.get('updatedAt') else '',
                                      (' - ' + st['comment']) if st.get('comment') else ''))
        else:
            print('review: no decision recorded yet')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('export', help='write layout.json and index.html')
    e.add_argument('board')
    e.add_argument('-o', '--out', required=True, help='output directory')
    e.add_argument('--classes', help='classes.json (fixed / region / free)')
    e.add_argument('--title', help='page title')
    p = sub.add_parser('apply', help='apply moves.json to a copy of the board')
    p.add_argument('board')
    p.add_argument('moves')
    p.add_argument('-o', '--out', required=True, help='output .kicad_pcb (never the input)')
    p.add_argument('--report', help='write a Markdown report here')
    p.add_argument('--classes', help='classes.json used at export (fixed parts are refused)')
    p.add_argument('--allow-locked', action='store_true',
                   help='move parts that are locked in KiCad but not classed fixed (the lock flag is kept)')
    p.add_argument('--strip-tracks-of', metavar='REFS',
                   help='comma-separated refs, or "moved": delete tracks and vias on every net touching them')
    p.add_argument('--no-validate', action='store_true', help='skip the kicad-cli load / DRC check')
    p.add_argument('--drc-refill', action='store_true', help='refill zones in the validation DRC (slower)')
    m = sub.add_parser('moves-from-db', help='ArtifactData list export -> moves.json')
    m.add_argument('db_list')
    m.add_argument('-o', '--out', required=True)
    m.add_argument('--review', help='ArtifactData export of the review collection')
    a = ap.parse_args()
    return {'export': export, 'apply': apply_moves, 'moves-from-db': moves_from_db}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
