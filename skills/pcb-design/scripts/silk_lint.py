#!/usr/bin/env python3
"""Silkscreen lint for a .kicad_pcb (see references/silkscreen.md).

    python silk_lint.py board.kicad_pcb [--min-height 0.8] [--min-line 0.15]

Errors (exit code 1): no revision or date on the silkscreen, text below the fab minimum.
Warnings: missing board name, designer, logo or QR code; hidden reference designators;
text that probably overlaps a pad. Overlap is estimated from text size, so treat it as
"look here", not as proof.
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr                                    # noqa: E402

DATE = re.compile(r'\$\{(ISSUE_DATE|CURRENT_DATE)\}|\b20\d\d[-./]\d{1,2}([-./]\d{1,2})?\b|\b\d{1,2}[-./]20\d\d\b', re.I)
REV = re.compile(r'\$\{REVISION\}|\brev(ision)?\.?\s*[A-Z0-9]|\bv\d+(\.\d+)*\b', re.I)


def hidden(node):
    for h in sexpr.walk(node, 'hide'):
        if len(h) == 1 or h[1] == 'yes':
            return True
    return 'hide' in node


def font(node):
    f = sexpr.child(sexpr.child(node, 'effects') or [], 'font') or []
    size = sexpr.child(f, 'size')
    th = sexpr.child(f, 'thickness')
    return (float(size[1]) if size else 1.0, float(size[2]) if size and len(size) > 2 else 1.0,
            float(th[1]) if th else None)


def layer_of(node):
    l = sexpr.child(node, 'layer')
    return l[1] if l else ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('--min-height', type=float, default=0.8, help="fab's minimum silkscreen text height, mm")
    ap.add_argument('--min-line', type=float, default=0.15, help="fab's minimum silkscreen line width, mm")
    a = ap.parse_args()
    root = sexpr.load(a.board)
    errors, warns, info = [], [], []
    texts = []          # (string, x, y, height, width, thickness, layer, where)
    pads = []           # (x, y, half-extent, side)
    names = []
    hidden_refs = 0
    for g in sexpr.children(root, 'gr_text'):
        if layer_of(g).endswith('.SilkS') and not hidden(g):
            x, y, _ = sexpr.at(g) or (0, 0, 0)
            h, w, t = font(g)
            texts.append((str(g[1]), x, y, h, w, t, layer_of(g), 'board text'))
    for fp in sexpr.children(root, 'footprint'):
        names.append(str(fp[1]))
        fx, fy, fr = sexpr.at(fp) or (0, 0, 0)
        c, s = math.cos(math.radians(fr)), math.sin(math.radians(fr))
        ref = ''
        for p in sexpr.children(fp, 'property'):
            if p[1] == 'Reference':
                ref = str(p[2])
                if hidden(p):
                    hidden_refs += 1
                elif layer_of(p).endswith('.SilkS'):
                    px, py, _ = sexpr.at(p) or (0, 0, 0)
                    h, w, t = font(p)
                    texts.append((ref, fx + px * c + py * s, fy - px * s + py * c, h, w, t, layer_of(p), 'reference'))
        for t_ in sexpr.children(fp, 'fp_text'):
            if layer_of(t_).endswith('.SilkS') and not hidden(t_):
                px, py, _ = sexpr.at(t_) or (0, 0, 0)
                h, w, t = font(t_)
                texts.append((str(t_[2]), fx + px * c + py * s, fy - px * s + py * c, h, w, t, layer_of(t_), ref))
        for pd in sexpr.children(fp, 'pad'):
            px, py, _ = sexpr.at(pd) or (0, 0, 0)
            size = sexpr.child(pd, 'size')
            ls = ' '.join(sexpr.child(pd, 'layers')[1:]) if sexpr.child(pd, 'layers') else ''
            ext = max(float(size[1]), float(size[2])) / 2 if size else 0.5
            for side in ('F', 'B'):
                if side + '.Cu' in ls or '*.Cu' in ls:
                    pads.append((fx + px * c + py * s, fy - px * s + py * c, ext, side))

    silk_all = ' \n '.join(t[0] for t in texts)
    tb = sexpr.child(root, 'title_block') or []
    tbv = {k: (sexpr.child(tb, k) or [None, ''])[1] for k in ('title', 'rev', 'date', 'company')}
    for k, v in tbv.items():
        if not v:
            warns.append('title block field "%s" is empty (the silkscreen text variables read from it)' % k)
    if not REV.search(silk_all):
        errors.append('no revision on the silkscreen (use the text variable ${REVISION})')
    if not DATE.search(silk_all):
        errors.append('no date on the silkscreen (use ${ISSUE_DATE})')
    if '${TITLE}' not in silk_all and not (tbv['title'] and tbv['title'].lower() in silk_all.lower()):
        warns.append('board name not found on the silkscreen (use ${TITLE})')
    if '${COMPANY}' not in silk_all and not (tbv['company'] and tbv['company'].lower() in silk_all.lower()):
        warns.append('designer / organisation not found on the silkscreen (use ${COMPANY} or plain text)')
    if not any(re.search(r'qr|barcode', n, re.I) for n in names) and not list(sexpr.walk(root, 'barcode')):
        warns.append('no QR code footprint found (scripts/silk_art.py qr ...)')
    if not any(re.search(r'logo', n, re.I) for n in names):
        warns.append('no logo footprint found (scripts/silk_art.py logo ...)')
    if hidden_refs:
        info.append('%d reference designator(s) hidden: make sure an assembly drawing shows them' % hidden_refs)

    small = [t for t in texts if t[3] < a.min_height - 1e-6]
    thin = [t for t in texts if t[5] is not None and t[5] < a.min_line - 1e-6]
    if small:
        errors.append('%d text(s) below %.2f mm height, e.g. %s' % (
            len(small), a.min_height, ', '.join('"%s" %.2f' % (t[0][:12], t[3]) for t in small[:5])))
    if thin:
        errors.append('%d text(s) with line thickness below %.2f mm, e.g. %s' % (
            len(thin), a.min_line, ', '.join('"%s" %.2f' % (t[0][:12], t[5]) for t in thin[:5])))
    over = []
    for (txt, x, y, h, w, _, layer, where) in texts:
        half_w = max(1, len(txt.split('\n')[0])) * w * 0.45
        r = math.hypot(half_w, h / 2)
        side = layer[0]
        for (px, py, ext, pside) in pads:
            if pside == side and abs(px - x) < half_w + ext and abs(py - y) < h / 2 + ext and math.hypot(px - x, py - y) < r + ext:
                over.append('"%s" at (%.1f, %.1f)' % (txt[:12], x, y))
                break
    if over:
        warns.append('%d text(s) probably over a pad, e.g. %s' % (len(over), ', '.join(over[:5])))

    print('%s: %d silkscreen text(s) checked' % (os.path.basename(a.board), len(texts)))
    for tag, items in (('ERROR', errors), ('warn ', warns), ('info ', info)):
        for i in items:
            print('  [%s] %s' % (tag, i))
    if not errors and not warns:
        print('  silkscreen checks passed')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
