---
name: plan-pcb-placement
description: "Places a KiCad board by function, and in full mode routes and verifies it. The agent sorts the parts into functional groups, names each switching stage and RF front end, copies its datasheet layout into a template its support parts are held to, place_simple.py anneals one objective over 12 seeds (6 started scattered, 6 with each group gathered), a quick judging route of the 6 its objective rates best keeps the best, and in full mode that board is then routed by /plan-pcb-routing. One independent verifier grades the result, and the board comes back with REPORT.md. Modes are place and full (place + route). Use it to place, arrange, re-place or optimise components, handle an unplaced board or parts piled off the outline, place and route from scratch, or run the GUI's Place / Place + Route. It never changes the outline. To route a placed board without moving parts, use plan-pcb-routing; for sign-off QA, review-routed-board. Runs the KiCadRoutingTools plugin (needs it installed; see the pcb-design skill)."
---

# plan-pcb-placement (KiCadRoutingTools launcher)

The skill itself ships inside the KiCadRoutingTools plugin and changes with it. This
launcher makes it usable from any folder and adds the rules of the `pcb-design`
workflow.

## 1. Find the plugin

Read `~/.config/pcb-design/krt.env` (plain `KEY=VALUE` lines). It gives:

- `KRT_ROOT`: the KiCadRoutingTools folder
- `KRT_BIN`: the folder holding the Python that has the router's dependencies

If the file is missing, or `KRT_ROOT` no longer exists, stop and tell the user to run
`./install.sh` from the pcb-design repository (`./install.sh --check` lists what is
missing). Do not search the disk for the plugin and do not pip-install anything
yourself.

## 2. Load the real skill

Read `$KRT_ROOT/.claude/skills/plan-pcb-placement/SKILL.md` in full and follow it. Files it refers
to (`references/...`, `scripts/...`) are in that same folder; tool paths
(`py_router/...`, `py_tools/...`, `py_placer/...`) are relative to `$KRT_ROOT`.
These launchers were written against KiCadRoutingTools 0.23.7 (`$KRT_ROOT/VERSION`).

## 3. How to run its commands

```bash
cd "$KRT_ROOT" && export PATH="$KRT_BIN:$PATH"
```

Run that first in every shell, so `python3` is the environment that has numpy, scipy,
shapely and Pillow (KiCad's bundled Python does not have them). Give board files as
absolute paths.

## 4. Rules that override the skill where they differ

- **Never work on the user's board in place.** Copy the `.kicad_pcb`, its `.kicad_pro`
  and the `.kicad_sch` files to a work folder next to the project (not inside the
  plugin folder: where the skill says `wk/<run>`, use an absolute work folder outside
  `$KRT_ROOT`), and write every output there. Do not pass `--overwrite`. Never write
  into the plugin folder.
- **Keep the board's design rules.** Add `--escalation board --no-fix-drc-settings` to
  every `route.py`, `route_diff.py`, `route_planes.py`, `qfn_fanout.py` and
  `bga_fanout.py` command. Without them the router shrinks tracks, vias and clearances
  below the board's own minimums to reach 100 % and rewrites the output project's
  rules to match. Measured on a 6-layer, 250-net board: stock defaults gave 250/250
  nets but 270 DRC errors against the original rules; with these two options 244/250
  and 0 errors. Report the nets that stay open rather than loosening anything;
  loosening is the user's decision.
- **Vias in pads** are allowed by the router unless told otherwise. Ask the user once
  per board; to forbid them pass `--same-net-pad-clearance 0.1`.
- **Grade with KiCad, against the original rules.** After any step that adds copper:
  put the original `.kicad_pro` beside the output board under the same basename, then
  `kicad-cli pcb drc --refill-zones --schematic-parity --severity-all --format json`.
  The router's own summary ("250/250 routed") is not the verdict.
- **Close KiCad on that board first**, or tell the user to reload afterwards; KiCad
  writes its in-memory Board Setup back on save.
- Routing a board of a few hundred nets takes 10 to 20 minutes; run long steps in the
  background.
