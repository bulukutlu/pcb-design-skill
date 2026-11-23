---
name: find-high-speed-nets
description: "Analyzes a KiCad PCB to identify high-speed and impedance-controlled nets by looking up component datasheets via AI. Classifies nets by speed tier (ultra-high/high/medium/low), detects RF/antenna feeds and other controlled-impedance nets, estimates max frequencies and rise times per interface, and recommends GND return via distances AND impedance-controlled routing: target ohms, the route.py/route_diff.py --impedance commands, and near-fab-floor width/spacing (~0.1 mm gap & clearance, impedance-derived width clamped to the floor) that override the board's Default net class for the run. Runs the KiCadRoutingTools plugin (needs it installed; see the pcb-design skill)."
---

# find-high-speed-nets (KiCadRoutingTools launcher)

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

Read `$KRT_ROOT/.claude/skills/find-high-speed-nets/SKILL.md` in full and follow it. Files it refers
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
