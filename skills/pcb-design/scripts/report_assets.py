#!/usr/bin/env python3
"""Generate the standard figures for the README, design report and test documents.

    python report_assets.py PROJECT_ROOT

Writes into PROJECT_ROOT/docs/img/:
  board-top.png, board-bottom.png      3D renders (kicad-cli pcb render)
  layer-<name>.svg                     one drawing per copper layer, plus silkscreen
  sch-<sheet>.svg                      one drawing per schematic sheet
and prints the Markdown to paste. Reports lead with these; see references/design-report.md.
"""
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr                                    # noqa: E402


def find_cli():
    for c in (shutil.which('kicad-cli'), '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
              r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'):
        if c and os.path.isfile(c):
            return c
    sys.exit('kicad-cli not found')


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = os.path.abspath(sys.argv[1])
    cli = find_cli()
    boards = glob.glob(os.path.join(root, 'kicad', '*.kicad_pcb'))
    if len(boards) != 1:
        sys.exit('expected exactly one .kicad_pcb in %s/kicad' % root)
    board = boards[0]
    name = os.path.splitext(os.path.basename(board))[0]
    out = os.path.join(root, 'docs', 'img')
    os.makedirs(out, exist_ok=True)
    made, failed = [], []

    def run(label, target, cmd):
        r = subprocess.run(cmd, capture_output=True, text=True)
        (made if r.returncode == 0 and (os.path.exists(target)) else failed).append(label)

    for side in ('top', 'bottom'):
        f = os.path.join(out, 'board-%s.png' % side)
        run('board-%s.png' % side, f, [cli, 'pcb', 'render', '--side', side, '--quality', 'basic', '-o', f, board])
    layers = [l[1] for l in sexpr.child(sexpr.load(board), 'layers')[1:]
              if isinstance(l, list) and (l[1].endswith('.Cu') or l[1].endswith('.SilkS'))]
    for l in layers:
        f = os.path.join(out, 'layer-%s.svg' % l.replace('.', '_'))
        run(os.path.basename(f), f, [cli, 'pcb', 'export', 'svg', '--layers', l + ',Edge.Cuts', '--mode-single',
                                     '--page-size-mode', '2', '--exclude-drawing-sheet', '-o', f, board])
    sch = os.path.join(root, 'kicad', name + '.kicad_sch')
    sheets = []
    if os.path.isfile(sch):
        tmp = os.path.join(out, '_sch')
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([cli, 'sch', 'export', 'svg', '--exclude-drawing-sheet', '-o', tmp, sch], capture_output=True, text=True)
        for f in sorted(glob.glob(os.path.join(tmp, '*.svg'))):
            dst = os.path.join(out, 'sch-' + os.path.basename(f).replace(' ', '_'))
            os.replace(f, dst)
            sheets.append(os.path.basename(dst))
        shutil.rmtree(tmp, ignore_errors=True)
        (made if sheets else failed).append('schematic sheets (%d)' % len(sheets))
    print('wrote to %s: %s' % (out, ', '.join(made) or 'nothing'))
    if failed:
        print('FAILED: %s' % ', '.join(failed))
    print('\nMarkdown (paths relative to docs/):\n')
    print('| Top | Bottom |\n|---|---|\n| ![Top](img/board-top.png) | ![Bottom](img/board-bottom.png) |\n')
    for l in layers:
        print('![%s](img/layer-%s.svg)' % (l, l.replace('.', '_')))
    for s in sheets:
        print('![%s](img/%s)' % (s[4:-4], s))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
