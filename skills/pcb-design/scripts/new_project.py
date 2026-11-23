#!/usr/bin/env python3
"""Create the standard project folder for a board.

    python new_project.py /path/to/MyBoard --title "My board" [--designer "Name"]
                          [--org "Institute"] [--repo-url URL] [--git] [--ci]

Creates the folders and starter documents described in
references/project-structure.md. Never overwrites an existing file, so it is
safe to run on a project that already has some of them. It does not create or
move KiCad files: put the KiCad project in `kicad/` (ask the user before
moving an existing one).
"""
import argparse
import datetime
import os
import subprocess

GATES = [('G0', 'Requirements'), ('G1', 'Architecture, fab and stackup'), ('G2', 'Schematic'),
         ('G3', 'Simulation'), ('G4', 'Floorplan'), ('G5', 'Placement'), ('G6', 'Routing'),
         ('G7', 'DRC / DFM / DFT audit'), ('G8', 'Pre-order validation'), ('G9', 'Outputs and release')]

DIRS = {
    'kicad': 'KiCad project (.kicad_pro, .kicad_sch, .kicad_pcb), project-local libraries.',
    'kicad/3dmodels': 'STEP models for parts not in the KiCad library; referenced as ${KIPRJMOD}/3dmodels/...',
    'kicad/lib': 'Project-local symbols and footprints, including generated logo and QR footprints.',
    'sim': 'One folder per simulated block: deck, models (with source URL), raw data, plots.',
    'docs': 'design-notes.md (working log), design-report.md (release report), img/ (figures).',
    'docs/img': 'Renders, schematic SVGs and plots embedded in the documents.',
    'docs/datasheets': 'Datasheets or, for a public repository, a links.md file instead of the PDFs.',
    'manufacturing': 'One frozen folder per released revision, written by scripts/release.py. Never edited by hand.',
    'assembly': 'Interactive BOM, assembly drawings, DNP list, programming files and instructions.',
    'testing': 'Test plan, bring-up procedure, first-article checklist, fixtures.',
    'testing/results': 'One result file per board serial number.',
    'mechanical': 'Board STEP export, enclosure models, fit checks.',
}

GITIGNORE = """# KiCad
*-backups/
_autosave-*
*.kicad_prl
*.lck
~*.lck
fp-info-cache
*.bak
*-cache.lib
# tools
__pycache__/
*.pyc
.DS_Store
*.drc.json
# simulation raw data can be large; keep plots, drop raw
sim/**/*.raw
"""

CI = """# Runs ERC and DRC on every push. Template: check the image tag matches your KiCad version.
name: kicad-checks
on: [push, pull_request]
jobs:
  checks:
    runs-on: ubuntu-latest
    container: kicad/kicad:10.0
    steps:
      - uses: actions/checkout@v4
      - name: ERC
        run: |
          for f in kicad/*.kicad_sch; do
            kicad-cli sch erc --exit-code-violations --format json -o "erc-$(basename "$f").json" "$f"
          done
      - name: DRC
        run: |
          for f in kicad/*.kicad_pcb; do
            kicad-cli pcb drc --refill-zones --schematic-parity --exit-code-violations \\
              --format json -o "drc-$(basename "$f").json" "$f"
          done
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: check-reports
          path: "*.json"
"""


def write(path, text, made):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    made.append(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root')
    ap.add_argument('--title', help='human-readable board name (default: folder name)')
    ap.add_argument('--designer', default='')
    ap.add_argument('--org', default='')
    ap.add_argument('--repo-url', default='', help='where the repository will live online (for README and the QR code)')
    ap.add_argument('--git', action='store_true', help='git init if the folder is not a repository yet')
    ap.add_argument('--ci', action='store_true', help='add a GitHub Actions workflow that runs ERC and DRC')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    title = a.title or os.path.basename(root)
    today = datetime.date.today().isoformat()
    made = []
    for d, why in DIRS.items():
        os.makedirs(os.path.join(root, d), exist_ok=True)
        if d in ('kicad/3dmodels', 'kicad/lib', 'docs/img', 'docs/datasheets', 'testing/results', 'mechanical',
                 'manufacturing', 'assembly', 'sim'):
            write(os.path.join(root, d, 'README.md'), '# %s\n\n%s\n' % (d, why), made)

    write(os.path.join(root, 'README.md'), f"""# {title}

<!-- Replace with a render: scripts/report_assets.py writes docs/img/board-top.png -->
![Board, top side](docs/img/board-top.png)

| | |
|---|---|
| Designer | {a.designer or '_fill in_'} |
| Organisation | {a.org or '_fill in_'} |
| Repository | {a.repo_url or '_fill in_'} |
| Status | see [STATUS.md](STATUS.md) |

## What it is
_One paragraph: function, interfaces, where it is used._

## Revisions
| Rev | Date | Tag | Changes | Fab order |
|---|---|---|---|---|
| A | | | First release | |

## Where things are
| Folder | Contents |
|---|---|
""" + ''.join('| `%s/` | %s |\n' % (d, w) for d, w in DIRS.items() if '/' not in d) + """
Start with [docs/design-report.md](docs/design-report.md) for the design, and
[testing/bringup.md](testing/bringup.md) to power up a board.
""", made)

    write(os.path.join(root, 'STATUS.md'), f"""# Gate status: {title}

One row per gate. A gate is passed only when its exit criteria hold and, where marked,
the user has signed off. Update this file when a gate closes or is reopened.

| Gate | What | State | Date | Evidence | Signed off by |
|---|---|---|---|---|---|
""" + ''.join('| %s | %s | open | | | |\n' % g for g in GATES) + """
States: `open`, `in progress`, `passed`, `reopened (reason)`.
""", made)

    write(os.path.join(root, 'docs', 'design-notes.md'), f"""# Design notes: {title}

Working log. Each gate appends its decisions, calculations and results here, newest at
the bottom of its section. The release report (design-report.md) is compiled from this.

## G0 Requirements
| # | Requirement | Value / limit | Source | Verified by (test id) |
|---|---|---|---|---|
| R1 | | | | |

## Placement classes (fixed / region / free)
| Ref | Position | Orientation | Reason |
|---|---|---|---|

## 3D models
| Ref / MPN | Source | Checked against |
|---|---|---|

## Waivers
| Check | Item | Reason | Approved by |
|---|---|---|---|
""", made)

    write(os.path.join(root, 'docs', 'errata.md'), f"""# Errata and lessons: {title}

Read this before starting a new revision. One row per problem found after release.

| Rev | Found (date, serial) | Problem | Root cause | Workaround on built boards | Fix for next rev | Fixed in |
|---|---|---|---|---|---|---|
""", made)

    write(os.path.join(root, 'testing', 'test-plan.md'), f"""# Test plan: {title}

Every requirement in docs/design-notes.md maps to at least one test here. Limits come
from the calculations and simulations in the design report, not from guesses.

| Test id | Requirement | Stage | Method and equipment | Lower limit | Upper limit | Unit |
|---|---|---|---|---|---|---|
| T1 | R1 | bring-up / functional / production | | | | |

Stages: `first article` (once per batch), `bring-up` (first power-on of each board),
`functional` (each board), `production` (fixture, each board), `qualification` (once per revision).
""", made)

    write(os.path.join(root, 'testing', 'results', 'TEMPLATE.md'), f"""# Test record: {title}

| | |
|---|---|
| Serial number | |
| Board revision | |
| Assembled by / batch | |
| Tested by | |
| Date | |
| Firmware version | |
| Equipment (model, serial, calibration) | |

<!-- Add a photo of the board as tested: ![board](img/<serial>.jpg) -->

| Test id | Measured | Lower | Upper | Unit | Pass |
|---|---|---|---|---|---|

Deviations and rework:

Verdict: PASS / FAIL
""", made)

    write(os.path.join(root, 'testing', 'first-article.md'), f"""# First-article inspection: {title}

Done once on the first board of every fabrication or assembly batch, before the rest
are powered. Photograph both sides and attach.

## Bare board
- [ ] Outline, slots and hole positions match the fab drawing (measure 3 dimensions)
- [ ] Thickness and, for flex, stiffener position and thickness
- [ ] Copper finish and solder-mask colour as ordered
- [ ] Silkscreen legible; revision and date correct; QR code scans and opens this revision
- [ ] Impedance or test report from the fab, if ordered

## Assembled board
- [ ] Every polarised part oriented per the assembly drawing (list them: ...)
- [ ] Pin 1 of every IC and connector
- [ ] DNP parts absent, variants correct
- [ ] No bridges, tombstones or missing parts (magnifier / AOI images)
- [ ] BGA / QFN: X-ray images if ordered
- [ ] Connectors mate with their cables or boards
- [ ] Fits the enclosure or mounting

Findings go to docs/errata.md.
""", made)

    write(os.path.join(root, 'testing', 'bringup.md'), f"""# Bring-up procedure: {title}

Generated at G9 from references/dft-bringup.md §6 with this board's rails, testpoints and
expected values filled in. Until then this is a placeholder.
""", made)

    write(os.path.join(root, '.gitignore'), GITIGNORE, made)
    if a.ci:
        write(os.path.join(root, '.github', 'workflows', 'kicad-checks.yml'), CI, made)
    if a.git and not os.path.isdir(os.path.join(root, '.git')):
        subprocess.check_call(['git', 'init', '-q', '-b', 'main', root])
        print('initialised git repository (nothing committed)')
    for p in made:
        print('created', os.path.relpath(p, root))
    print('%d file(s) created in %s (%s)' % (len(made), root, today))


if __name__ == '__main__':
    main()
