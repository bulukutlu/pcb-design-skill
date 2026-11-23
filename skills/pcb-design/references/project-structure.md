# Project structure, repository and releases

Every board lives in one folder with the same layout, under version control. Create it
with `python scripts/new_project.py <folder> --title "..." --designer "..." --org "..." --git`
(add `--ci` for a GitHub Actions ERC/DRC workflow). The script never overwrites, so it
is safe on an existing project.

```
<Project>/
  README.md         render of the board, what it is, revision table, where things are
  STATUS.md         gate status: which gate passed, when, evidence, who signed off
  kicad/            the KiCad project; lib/ (project-local symbols, footprints, logo and
                    QR footprints); 3dmodels/
  sim/              one folder per simulated block: deck, models, plots
  docs/             design-notes.md (working log), design-report.md, bom.md, errata.md,
                    img/ (figures), datasheets/ (or links.md)
  manufacturing/    rev-A/, rev-B/, ... frozen outputs, written by scripts/release.py
  assembly/         interactive BOM, assembly drawings, DNP list, programming files
  testing/          test-plan.md, bringup.md, first-article.md, results/<serial>.md
  mechanical/       board STEP, enclosure, fit checks
```

## Rules
- **Existing project.** Do not move a user's KiCad files without asking. If they agree,
  move the whole KiCad project (all `.kicad_*` files and library folders) into `kicad/`
  in one step with KiCad closed, then open it and confirm libraries still resolve.
- **Paths.** Reference project libraries and 3D models through `${KIPRJMOD}` so the
  repository works on any machine.
- **Public or private.** Ask the user before anything is pushed. In a public
  repository do not commit datasheet PDFs or vendor models whose licence forbids
  redistribution; keep `docs/datasheets/links.md` instead.
- **What is not committed.** `.gitignore` from the scaffold excludes KiCad backups,
  lock files, local preferences (`.kicad_prl`) and raw simulation data.
- **STATUS.md** is updated whenever a gate closes or is reopened. It is the first thing
  to read when resuming work.
- **Commits.** Commit at each gate exit with the gate in the message. Never commit or
  push without the user's go-ahead.

## Releasing a revision
1. G7 and G8 pass; `STATUS.md` shows it.
2. Set revision and date in the title block (the silkscreen reads them through text
   variables; see `silkscreen.md`).
3. `python scripts/release.py <Project> --rev A` writes `manufacturing/rev-A/`: gerbers,
   drill, placement, IPC-D-356 netlist, BOM, schematic PDF, STEP, the DRC report, a
   SHA-256 manifest and `ORDER.md`. It refuses if DRC is not clean or the folder exists.
4. Run the pre-order verification in `verification.md` on that folder.
5. With the user's approval: commit, tag `rev-A`, push. The QR code on the board points
   at that tag.
6. When ordering, fill in `ORDER.md` line by line against the fab's order page. Wrong
   thickness, finish, stiffener or impedance option is a common and expensive mistake.
7. A released folder is never edited. Any change is a new revision; problems found on
   built boards go into `docs/errata.md`.

## Comparing revisions
For a visual diff, export the same layer from two tags with `kicad-cli pcb export svg`
and show them side by side in the report, or use KiRi for an interactive diff.
