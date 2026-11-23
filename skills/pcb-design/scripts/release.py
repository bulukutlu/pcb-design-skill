#!/usr/bin/env python3
"""Freeze one revision's manufacturing outputs.

    python release.py PROJECT_ROOT --rev A [--no-step] [--force]

Writes PROJECT_ROOT/manufacturing/rev-<REV>/ with gerbers, drill files, placement,
IPC-D-356 netlist, BOM, schematic PDF, board STEP, a SHA-256 manifest and an order
record to fill in. It refuses to run when the folder already exists (a released
revision is never regenerated; make a new revision) and when KiCad's DRC reports
errors or unconnected items (--force overrides and records that it did).

It does not commit or tag: it prints the commands, for the user to approve.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys


def find_cli():
    for c in (shutil.which('kicad-cli'), '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
              r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'):
        if c and os.path.isfile(c):
            return c
    sys.exit('kicad-cli not found')


def run(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True)
    log.append('$ ' + ' '.join(cmd))
    if r.returncode:
        log.append((r.stdout + r.stderr).strip()[-600:])
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root')
    ap.add_argument('--rev', required=True)
    ap.add_argument('--no-step', action='store_true', help='skip the STEP export (slow on large boards)')
    ap.add_argument('--force', action='store_true', help='release despite DRC errors or unconnected items')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    cli = find_cli()
    boards = [b for b in glob.glob(os.path.join(root, 'kicad', '*.kicad_pcb')) if not os.path.basename(b).startswith('_')]
    if len(boards) != 1:
        sys.exit('expected exactly one .kicad_pcb in %s/kicad, found %d' % (root, len(boards)))
    board = boards[0]
    name = os.path.splitext(os.path.basename(board))[0]
    sch = os.path.join(root, 'kicad', name + '.kicad_sch')
    out = os.path.join(root, 'manufacturing', 'rev-' + a.rev)
    if os.path.exists(out):
        sys.exit('%s exists: a released revision is frozen. Use a new --rev.' % out)

    drc_json = os.path.join(root, 'manufacturing', '.drc-rev-%s.json' % a.rev)
    os.makedirs(os.path.dirname(drc_json), exist_ok=True)
    cmd = [cli, 'pcb', 'drc', '--refill-zones', '--severity-all', '--format', 'json', '-o', drc_json]
    if os.path.isfile(sch):
        cmd.insert(4, '--schematic-parity')
    subprocess.run(cmd + [board], capture_output=True, text=True)
    d = json.load(open(drc_json))
    errors = sum(1 for v in d.get('violations', []) if v.get('severity') == 'error')
    unconnected = len(d.get('unconnected_items', []))
    parity = len(d.get('schematic_parity', []))
    print('DRC: %d error(s), %d unconnected, %d parity issue(s)' % (errors, unconnected, parity))
    if (errors or unconnected or parity) and not a.force:
        os.remove(drc_json)
        sys.exit('not released: fix these first (or --force, which is recorded in the order record)')

    os.makedirs(os.path.join(out, 'gerbers'))
    os.replace(drc_json, os.path.join(out, 'drc.json'))
    log, failed = [], []
    steps = [
        ('gerbers', [cli, 'pcb', 'export', 'gerbers', '-o', os.path.join(out, 'gerbers') + os.sep, board]),
        ('drill', [cli, 'pcb', 'export', 'drill', '-o', os.path.join(out, 'gerbers') + os.sep, board]),
        ('placement', [cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
                       '-o', os.path.join(out, name + '-pos.csv'), board]),
        ('IPC-D-356 netlist', [cli, 'pcb', 'export', 'ipcd356', '-o', os.path.join(out, name + '.d356'), board]),
        ('board statistics', [cli, 'pcb', 'export', 'stats', '-o', os.path.join(out, name + '-stats.txt'), board]),
    ]
    if not a.no_step:
        steps.append(('STEP', [cli, 'pcb', 'export', 'step', '--subst-models', '-o',
                               os.path.join(out, name + '.step'), board]))
    if os.path.isfile(sch):
        steps += [('schematic PDF', [cli, 'sch', 'export', 'pdf', '-o', os.path.join(out, name + '-schematic.pdf'), sch]),
                  ('BOM', [cli, 'sch', 'export', 'bom', '-o', os.path.join(out, name + '-bom.csv'), sch])]
    else:
        failed.append('schematic PDF and BOM (no %s)' % os.path.basename(sch))
    for label, cmd in steps:
        ok = run(cmd, log)
        print('  %-18s %s' % (label, 'ok' if ok else 'FAILED'))
        if not ok:
            failed.append(label)

    lines = []
    for dp, _, files in os.walk(out):
        for fn in sorted(files):
            full = os.path.join(dp, fn)
            lines.append('%s  %s' % (hashlib.sha256(open(full, 'rb').read()).hexdigest(), os.path.relpath(full, out)))
    open(os.path.join(out, 'SHA256SUMS'), 'w').write('\n'.join(sorted(lines, key=lambda l: l.split('  ')[1])) + '\n')
    open(os.path.join(out, 'export.log'), 'w').write('\n'.join(log) + '\n')
    commit = subprocess.run(['git', '-C', root, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', '-C', root, 'status', '--porcelain', '--', 'kicad'],
                                capture_output=True, text=True).stdout.strip())
    open(os.path.join(out, 'ORDER.md'), 'w').write(f"""# Order record: {name} rev {a.rev}

| | |
|---|---|
| Released | {datetime.date.today().isoformat()} |
| Design commit | {commit or 'not under git'}{' (kicad/ had uncommitted changes)' if dirty else ''} |
| DRC at release | {errors} error(s), {unconnected} unconnected, {parity} parity issue(s){' - RELEASED WITH --force' if (errors or unconnected or parity) else ''} |
| Exports that failed | {', '.join(failed) or 'none'} |

## Fabrication (fill in when ordering; compare each line with the fab's order page)
| Option | Ordered | From design |
|---|---|---|
| Fab and order number | | |
| Quantity | | |
| Layers | | |
| Thickness | | |
| Material / flex build / stiffener | | |
| Copper weight outer / inner | | |
| Surface finish | | |
| Solder mask / silkscreen colour | | |
| Impedance control and stackup id | | |
| Via covering | | |
| Edge plating, castellations, gold fingers | | |
| Electrical test | | |
| Panelisation | | |
| Quote and lead time | | |

## Assembly
| Option | Ordered |
|---|---|
| Assembler and order number | |
| Sides | |
| Parts supplied by | |
| DNP list sent | |
| Placement rotations confirmed in the assembler's preview | |

## Checks before paying
- [ ] Gerbers opened in a viewer; layer count, outline and drill alignment correct
- [ ] Fab's rendered preview matches `docs/img/board-top.png` and `board-bottom.png`
- [ ] Placement preview: every polarised part and pin 1 correct
- [ ] BOM lines match the assembler's part selection, substitutions approved
""")
    print('wrote %s' % out)
    if failed:
        print('incomplete: %s (see export.log)' % ', '.join(failed))
    print('next, with the user\'s approval:\n  git -C "%s" add manufacturing/rev-%s && git -C "%s" commit -m "Release rev %s"\n'
          '  git -C "%s" tag -a rev-%s -m "Rev %s as sent to fab"' % (root, a.rev, root, a.rev, root, a.rev, a.rev))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
