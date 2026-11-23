#!/usr/bin/env python3
"""Pin-by-pin check of two connectors that plug into each other.

    python mating_check.py boardA.kicad_pcb J1 boardB.kicad_pcb J7 [--map straight|mirror|rows|FILE]
                           [--alias NAME_A=NAME_B ...] [--md out.md]

Prints, for every pin, the net on each side and whether they agree. The two boards may
be the same file (board-to-board on one design, or a cable board). Net names are
compared after dropping the sheet path (`/Sheet/NAME` -> `NAME`); use --alias for nets
that are deliberately named differently on the two sides (e.g. TX=RX).

Pin maps:
  straight  pin n mates with pin n (most board-to-wire and pin-header pairs)
  mirror    pin n mates with pin N+1-n (FFC/FPC with contacts on the same side at both
            ends, or a connector seen from the other side)
  rows      two-row parts, row swap: 1<->2, 3<->4, ... (a header facing a socket on the
            opposite side of a board)
  FILE      a text file with "pinA pinB" per line, for anything else

This check does not know your connector. Decide the map from the two datasheets'
mating drawings, write the reason in design-notes.md, and attach this table.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr                                    # noqa: E402


def pins(board, ref):
    root = sexpr.load(board)
    for fp in sexpr.children(root, 'footprint'):
        if any(p[1] == 'Reference' and str(p[2]) == ref for p in sexpr.children(fp, 'property')):
            out = {}
            for pd in sexpr.children(fp, 'pad'):
                n = sexpr.child(pd, 'net')
                name = str(n[-1]) if n and len(n) > 1 else ''
                if str(pd[1]):
                    out.setdefault(str(pd[1]), name)
            return out
    sys.exit('%s: no footprint with reference %s' % (board, ref))


def short(net):
    return net.rsplit('/', 1)[-1] if net else ''


def key(p):
    return (0, int(p)) if p.isdigit() else (1, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board_a')
    ap.add_argument('ref_a')
    ap.add_argument('board_b')
    ap.add_argument('ref_b')
    ap.add_argument('--map', default='straight')
    ap.add_argument('--alias', action='append', default=[], metavar='A=B')
    ap.add_argument('--md', help='also write the table as Markdown to this file')
    a = ap.parse_args()
    pa, pb = pins(a.board_a, a.ref_a), pins(a.board_b, a.ref_b)
    na = sorted((p for p in pa if p.isdigit()), key=int)
    if a.map == 'straight':
        m = {p: p for p in pa}
    elif a.map == 'mirror':
        m = {p: str(len(na) + 1 - int(p)) for p in na}
    elif a.map == 'rows':
        m = {p: str(int(p) + 1 if int(p) % 2 else int(p) - 1) for p in na}
    elif os.path.isfile(a.map):
        m = dict(l.split()[:2] for l in open(a.map) if len(l.split()) >= 2 and not l.startswith('#'))
    else:
        sys.exit('unknown --map %r' % a.map)
    alias = dict(x.split('=', 1) for x in a.alias)
    rows, bad = [], 0
    for p in sorted(pa, key=key):
        q = m.get(p)
        netb = pb.get(q) if q else None
        sa, sb = short(pa[p]), short(netb or '')
        if q is None or netb is None:
            verdict = 'NO MATE'
        elif sa == sb or alias.get(sa) == sb:
            verdict = 'ok' if sa else 'both unconnected'
        elif not sa or not sb:
            verdict = 'ONE SIDE OPEN'
        else:
            verdict = 'MISMATCH'
        bad += verdict.isupper()
        rows.append((p, pa[p] or '-', q or '-', netb or '-', verdict))
    unused = sorted(set(pb) - set(m.values()), key=key)
    head = '| %s pin | net | %s pin | net | |' % (a.ref_a, a.ref_b)
    lines = [head, '|---|---|---|---|---|'] + ['| %s | %s | %s | %s | %s |' % r for r in rows]
    title = '%s.%s <-> %s.%s (map: %s)' % (os.path.basename(a.board_a), a.ref_a, os.path.basename(a.board_b), a.ref_b, a.map)
    print(title)
    print('\n'.join(lines))
    if unused:
        print('pins of %s with no mate: %s' % (a.ref_b, ', '.join(unused)))
    print('%d pin(s), %d problem(s)' % (len(rows), bad))
    if a.md:
        open(a.md, 'w').write('### %s\n\n%s\n\n%d pin(s), %d problem(s)\n' % (title, '\n'.join(lines), len(rows), bad))
    return 1 if bad or unused else 0


if __name__ == '__main__':
    sys.exit(main())
