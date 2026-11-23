#!/usr/bin/env python3
"""Make silkscreen artwork footprints: a QR code or a logo.

    python silk_art.py qr "https://example.org/board/tree/rev-A" -o kicad/lib/art.pretty/QR_docs.kicad_mod
    python silk_art.py logo logo.png --width 12 -o kicad/lib/art.pretty/LOGO_org.kicad_mod

Both write a board-only footprint (not in the BOM or placement file) made of filled
rectangles on a silkscreen layer. Needs the `qrcode` and `Pillow` packages (in the
tools environment created by install.sh).

QR polarity. A scanner expects dark modules on a light background. On a board the
silkscreen is usually the LIGHT colour and the solder mask the dark one, so by default
the silkscreen prints the light modules and the quiet zone, and the mask shows through
as the dark modules. Use --dark-silk for dark ink on a light mask.
"""
import argparse
import os
import sys
import uuid


def runs_to_rects(grid):
    """grid[y][x] truthy = ink. Merge horizontal runs, then identical runs on
    consecutive rows, into (x0, y0, x1, y1) cell rectangles."""
    open_runs, rects = {}, []
    for y, row in enumerate(list(grid) + [[]]):
        runs, x = set(), 0
        while x < len(row):
            if row[x]:
                x0 = x
                while x < len(row) and row[x]:
                    x += 1
                runs.add((x0, x))
            else:
                x += 1
        for r in list(open_runs):
            if r not in runs:
                rects.append((r[0], open_runs.pop(r), r[1], y))
        for r in runs:
            open_runs.setdefault(r, y)
    return rects


def footprint(name, rects, cell, layer, descr, cols=None, rows=None):
    w = (cols or max(r[2] for r in rects)) * cell
    h = (rows or max(r[3] for r in rects)) * cell
    out = ['(footprint "%s"' % name, '\t(version 20241229)', '\t(generator "pcb_design_silk_art")',
           '\t(layer "F.Cu")', '\t(descr "%s")' % descr.replace('"', "'"),
           '\t(attr board_only exclude_from_pos_files exclude_from_bom)']
    for (x0, y0, x1, y1) in rects:
        out.append('\t(fp_rect\n\t\t(start %.4f %.4f)\n\t\t(end %.4f %.4f)\n\t\t(stroke\n\t\t\t(width 0)\n'
                   '\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)'
                   % (x0 * cell - w / 2, y0 * cell - h / 2, x1 * cell - w / 2, y1 * cell - h / 2, layer, uuid.uuid4()))
    out.append(')')
    return '\n'.join(out) + '\n', w, h


def cmd_qr(a):
    import qrcode
    ecc = {'L': qrcode.constants.ERROR_CORRECT_L, 'M': qrcode.constants.ERROR_CORRECT_M,
           'Q': qrcode.constants.ERROR_CORRECT_Q, 'H': qrcode.constants.ERROR_CORRECT_H}[a.ecc]
    q = qrcode.QRCode(error_correction=ecc, border=a.quiet_zone, box_size=1)
    q.add_data(a.text)
    q.make(fit=True)
    dark = q.get_matrix()                      # includes the quiet zone; True = dark module
    grid = dark if a.dark_silk else [[not c for c in row] for row in dark]
    text, w, h = footprint(a.name or 'QR_code', runs_to_rects(grid), a.module, a.layer,
                           'QR code: %s' % a.text)
    n = len(dark) - 2 * a.quiet_zone
    print('QR version %d (%dx%d modules), %d characters, error correction %s'
          % (q.version, n, n, len(a.text), a.ecc))
    print('size on board: %.1f x %.1f mm including quiet zone, module %.2f mm' % (w, h, a.module))
    if a.module < 2 * a.min_line:
        print('WARNING: module %.2f mm is under twice the minimum silk line (%.2f mm); it may not print. '
              'Shorten the URL or raise --module.' % (a.module, a.min_line))
    return text


def cmd_logo(a):
    from PIL import Image
    im = Image.open(a.image).convert('RGBA')
    cols = max(1, min(im.width, int(a.width / a.min_line)))
    rows = max(1, round(im.height * cols / im.width))
    im = im.resize((cols, rows), Image.LANCZOS)
    cell = a.width / cols
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, b, alpha = im.getpixel((x, y))
            dark = alpha > 127 and (0.299 * r + 0.587 * g + 0.114 * b) < a.threshold
            row.append(dark != a.invert if alpha > 127 or a.invert else False)
        grid.append(row)
    rects = runs_to_rects(grid)
    if not rects:
        sys.exit('nothing to draw: try --invert or another --threshold')
    text, w, h = footprint(a.name or 'LOGO', rects, cell, a.layer,
                           'Logo from %s' % os.path.basename(a.image), cols, rows)
    print('logo: %.1f x %.1f mm, %d rectangles, smallest feature %.2f mm' % (w, h, len(rects), cell))
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('qr', 'logo'):
        p = sub.add_parser(name)
        p.add_argument('text' if name == 'qr' else 'image')
        p.add_argument('-o', '--output', required=True, help='.kicad_mod file inside a .pretty folder')
        p.add_argument('--name', help='footprint name (default: the output file name)')
        p.add_argument('--layer', default='F.SilkS')
        p.add_argument('--min-line', type=float, default=0.15, help="fab's minimum silkscreen line width, mm")
        if name == 'qr':
            p.add_argument('--module', type=float, default=0.4, help='module size in mm (default 0.4)')
            p.add_argument('--quiet-zone', type=int, default=2, help='quiet zone in modules (standard is 4; 2 usually scans)')
            p.add_argument('--ecc', choices='LMQH', default='M', help='error correction level')
            p.add_argument('--dark-silk', action='store_true', help='silk is the dark colour (dark ink on light mask)')
        else:
            p.add_argument('--width', type=float, required=True, help='logo width on the board, mm')
            p.add_argument('--threshold', type=int, default=128, help='luminance below this is ink (0-255)')
            p.add_argument('--invert', action='store_true', help='draw the light areas instead of the dark ones')
    a = ap.parse_args()
    a.name = a.name or os.path.splitext(os.path.basename(a.output))[0]
    text = cmd_qr(a) if a.cmd == 'qr' else cmd_logo(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    with open(a.output, 'w', encoding='utf-8') as f:
        f.write(text)
    print('wrote %s' % a.output)


if __name__ == '__main__':
    main()
