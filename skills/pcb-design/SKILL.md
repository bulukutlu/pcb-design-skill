---
name: "pcb-design"
description: "End-to-end KiCad 10 PCB design workflow: readable schematics, SPICE incl. failure cases, fab-driven DRC, placement-first routing loop, DFM/DFT, SI/PDN/thermal checks, EMC and EU CE."
---

# PCB Design (KiCad 10)

This skill makes you work like a disciplined senior hardware designer, not a netlist
generator. The output must be **correct, readable by humans, manufacturable, testable,
and justified**. Every design decision gets a short written reason (a datasheet value,
a calculation, a simulation, or a standard). "Because it is common" is not a reason.

## Core principles

1. **Readable first-class output.** A schematic that is electrically correct but only
   connected by net labels is a failed deliverable. Humans must be able to review it.
   See `references/schematic-style.md`.
2. **Consistent and commonly available.** Start from templates (sheet border, title
   block, net classes, DRC preset). Prefer standard KiCad libraries and parts stocked at
   ≥2 distributors (or JLC "Basic" parts when JLC assembles). Use the chosen fab's
   *published* stackup and capabilities to set the DRC — never invent limits.
3. **Placement is the main lever.** When routing gets hard, go back and change
   placement, orientation or pin assignment. Adding layers or shrinking rules is the
   last resort and needs a written justification. See `references/placement-routing-loop.md`.
4. **Design for manufacturing and for test from the first sheet**, not as a final pass.
   Testpoints, LEDs, boot/reset options, rail-isolation jumpers are part of the schematic.
5. **Simulate what can fail.** Non-trivial circuits get SPICE runs for normal operation
   *and* failure scenarios (short, reverse polarity, overvoltage, brown-out, hot-plug,
   tolerances, temperature).
6. **Gate, don't stream.** Work through the gates below. Do not start a gate before the
   previous gate's exit criteria hold. Stop at the human checkpoints.
7. **Verify, don't recall.** Re-check fab capability pages, part availability, tool
   versions and EU regulatory dates at run time when you have web access; these change.

## Tooling facts (KiCad 10, late 2026)

- KiCad 10 has **no built-in full-board autorouter** (only "Attempt Finish Selected",
  Shift+F, for selected connections). The router and placer for this workflow are
  **KiCadRoutingTools** (drandyhaas, PCM plugin, v0.23.7 when this was written), driven
  through the sub-skills listed under "Sub-skills" below. It covers constrained
  placement, QFN/BGA fan-out, differential pairs, impedance-driven widths, power-net
  widths, planes, length matching, rip-up and failure diagnosis. Do not write a custom
  router or placer: one was built and tested against it (see "Measured baselines") and
  added nothing.
- **Router rule policy.** By default KiCadRoutingTools shrinks tracks, vias and
  clearances below the board's own minimums to reach 100 % and rewrites the output
  project's DRC settings to match. Always pass `--escalation board --no-fix-drc-settings`
  and grade the result with `kicad-cli pcb drc --refill-zones --schematic-parity` against
  the **original** `.kicad_pro`. The router's own "N/N routed" line is not the verdict.
  It also places vias in pads unless `--same-net-pad-clearance` is set; ask the user.
- Prefer **kicad-cli** for everything headless: `sch erc`, `pcb drc`, exports (gerber,
  drill, pos, BOM, netlist, STEP, PDF, SVG), and jobsets.
- **IPC API** (`pip install kicad-python`, import `kipy`) drives a *running* PCB editor
  only (KiCad 9/10). The SWIG `pcbnew` module is deprecated and will be removed in
  KiCad 11 — do not write new code against it.
- No official schematic API in KiCad 10: edit `.kicad_sch` S-expressions carefully
  (kicad-skip / kicad-sch-api) with KiCad *closed* or reload afterwards.
- **Calculation and simulation tools** (ngspice, PySpice, numpy/scipy/matplotlib,
  PyIBIS-AMI, kicad-python; optionally Gmsh, Elmer, openEMS) are set up by this
  repository's `install.sh`. The Python ones live in their own environment; its `bin`
  folder is `PCB_TOOLS_BIN` in `~/.config/pcb-design/krt.env`. At the start of G3 and
  G8 run `install.sh --check`, and if a tool a required check needs is missing, tell
  the user which checks that blocks before going on.
- Tool survey and alternatives: `references/tooling-survey.md`.
  Installation: `references/install-quickstart.md`.

## The gated workflow

Keep a `design-notes.md` in the project root. Each gate appends its decisions,
calculations, and results there. This is the design record a reviewer reads.

### G0 — Requirements
Collect before you draw anything. Ask the user for what is missing; do not guess
items that change the architecture.
- Function, interfaces, connectors, data rates/edge rates, analog performance (noise,
  bandwidth, resolution).
- Power: input range, source type (USB-PD, bench, battery, mains), rails, max currents,
  efficiency limits.
- Mechanical: outline, mounting, height limits, enclosure, connector positions.
- Environment: ambient range (desk 25–40 °C, crate 50 °C+), altitude, humidity /
  pollution degree, vibration, radiation if relevant.
- Highest voltage on the board and whether it is user-accessible (drives HV rules).
- Regulatory class: in-house lab instrument, R&D kit, or product placed on the EU
  market (drives `references/eu-regulatory.md`).
- Fab and assembler (e.g. JLCPCB, PCBWay, Eurocircuits, Aisler, Multi-CB), quantity,
  budget, lead time, who solders.
- Test / bring-up needs: programming method, debug access, production test.
Exit: a requirements table in `design-notes.md`, confirmed by the user.

### G1 — Architecture, fab and stackup
- Block diagram and power tree (each rail: source, regulator type, current, noise
  requirement, sequencing). Justify LDO vs switcher (`references/power-pdn.md`).
- Classify nets: high-speed (by edge rate, not clock — `references/high-speed.md`),
  high-current, HV, sensitive analog, noisy switching.
- Select fab + stackup from the fab's published options. Load its rules into Board
  Setup and a `.kicad_dru` (`references/dfm-fab.md`). Create net classes (Default,
  Power, HV, DiffPair-100R, USB-90R, …) with impedance-derived widths from the fab's
  calculator.
- Select key parts; check stock, lifecycle, footprint and 3D STEP model availability
  (see "3D models").
- Once a board file exists, cross-check these decisions with the datasheet-driven
  sub-skills: `/recommend-stackup`, `/analyze-power-nets` (power nets and widths),
  `/find-high-speed-nets` (speed tiers, impedance targets), `/identify-diff-pairs`
  (pairs by pin function, not by net name).
Exit: power tree, net-class table, stackup, DRC preset in the project.

### G2 — Schematic
Follow `references/schematic-style.md` strictly. Summary:
- Project template with title block and revision table; hierarchical sheets by function;
  root sheet shows the block diagram.
- Signal flow left→right; supplies up, ground down; IC symbols drawn functionally.
- **Wires inside a functional cluster; labels only between clusters/sheets.** Decoupling,
  pull-ups, filters are wired next to their pins.
- Net names, reference designators per sheet (sheet 2 → 2xx), MPN/LCSC/DNP fields,
  design-intent notes ("place C5 ≤1 mm from U3.7").
- Include DFT parts now (`references/dft-bringup.md`): testpoints, status LEDs, reset and
  boot buttons/straps, debug header, 0 Ω/jumper rail isolation, current shunt.
- After **each sheet**: export SVG (`kicad-cli sch export svg`), look at it, and run
  `python scripts/sch_lint.py <file.kicad_sch>`. Fix findings before the next sheet.
Exit: ERC clean (`kicad-cli sch erc --exit-code-violations`) with justified waivers only,
lint clean, sheet PDFs reviewed by the user (**human checkpoint**).

### 3D models (every external component)
Every component that does not come from the standard KiCad library needs a 3D STEP
model attached to its footprint before placement starts: connectors, modules,
heatsinks, inductors, switches, displays, anything with height or a mating face. The
enclosure fit, height zones and the STEP export in G9 depend on it. Look in this order
and stop at the first that works:
1. **Libraries already on the machine**: KiCad's 3D model library and the project's own
   `3dmodels/` folder.
2. **The manufacturer**: product page or CAD download for the exact MPN.
3. **Online**: distributor part pages and CAD libraries (SnapMagic/SnapEDA, Ultra
   Librarian, 3D ContentCentral, GrabCAD). Say which file from which source before
   downloading it. Treat every downloaded model as unverified until checked below.
4. **Recreate it by hand** when no model exists, which is common. Take the dimensions
   from the mechanical drawing in the datasheet (body outline, height, pin or lead
   positions, mating face, mounting features, keep-out) and model the part
   parametrically (CadQuery or FreeCAD), then export STEP. An accurate envelope with
   correct pins matters; cosmetic detail does not. Keep the script beside the model.

For every model, whatever its source:
- Check it against the datasheet drawing: overall length, width and height, pin 1
  position, pin pitch, and that it sits on the footprint pads with the right origin,
  rotation and Z offset. Units and scale errors (inch vs mm) are the usual failure.
- Store it in the project's `3dmodels/` folder and reference it as
  `${KIPRJMOD}/3dmodels/<part>.step`, so the project is self-contained.
- Record in `design-notes.md`: MPN, source (URL, or "recreated from datasheet <doc
  number> rev <x>, figure <n>"), and what was checked.
Exit: every footprint on the board has a model that loads; `kicad-cli pcb export step`
reports no missing models; recreated models are listed for the user to review.

### G3 — Simulation (design decisions)
Follow `references/simulation-playbook.md`. For every non-trivial circuit (regulators,
protection, front-ends, filters, HV supply, references, oscillators):
- Nominal: operating point, transient, start-up/soft-start, load step, stability.
- Failure: output short, input overvoltage/surge, reverse polarity, brown-out/slow ramp,
  hot-plug inrush, open feedback resistor, loss of bias.
- Tolerance: Monte Carlo and temperature corners; worst case for dividers/references.
Record model sources/versions, stimulus, pass/fail criterion and the plot under `sim/`.
The full list of required simulations and calculations is in
`references/design-report.md`; work through its tables, do not pick from memory.
Exit: every simulated block passes its criterion, or the design is changed.

### G4 — Floorplan (human checkpoint)
Board outline, connectors, mounting holes, keep-outs and height zones first. Then place
functional groups following the schematic hierarchy: power entry → regulators →
digital → analog → sensor; noisy parts far from sensitive ones; HV area isolated. Show
the user a floorplan render (`kicad-cli pcb render` or SVG) before detailed placement.

**Ask the user to classify every part before anything is moved**, and record it in
`design-notes.md`:

| Class | Meaning | How it is enforced |
|---|---|---|
| Fixed | Exact position and rotation are given by mechanics, cooling or connector alignment | Lock in KiCad, or `fixed_poses[]` in the placement intent |
| Region | Must be in a general area (e.g. "right edge"), exact coordinates free | `edge_connectors[]` (held to an edge, slides along it), zones, group `near`/`apart`/`edge` hints |
| Free | May go wherever routing is best | Left unlocked; the placer moves it |

Orientation gets the same three answers per part: fixed rotation, a facing or side
only, or free (quarter turns). Parts the user has not classified are **not** free by
default: ask.

### G5 — Placement and routability check
Follow `references/placement-routing-loop.md`. Critical parts and their satellites
first (hot-loop caps, decoupling, crystals, terminations, ESD at connectors). Orient for
short, uncrossed ratsnest; use pin/gate swap (native in KiCad 10) and FPGA/MCU pin
reassignment. Plan BGA fanout. Use Design Blocks for repeated channels.
Use `/plan-pcb-placement` for the placement itself (mode `place`): it groups parts by
function, seats the fixed and region parts from G4, anneals the free ones over several
seeds and keeps the seed that fast-routes best. Its cost is wirelength + crossings +
decoupling and crystal distance limits + group cohesion + fan-out room in front of
fine-pitch parts + congestion. Read its escape-lane and reachability reports: a
fine-pitch face that has fewer lanes than nets is a placement problem no router setting
fixes.
Run the routability estimate. Exit: no region above ~70 % channel demand, crossing count
acceptable, no escape-lane deficit.

### G6 — Routing with the placement loop
1. Route critical nets by hand or under tight constraints, in order: power hot loops →
   differential pairs → clocks → HV → sensitive analog.
2. Route the rest with `/plan-pcb-routing`. It produces an ordered, checked plan
   (pours → fan-out → differential pairs → impedance nets → one pass over all remaining
   nets → return vias) and runs it on approval. Run it on a copy of the board with the
   router rule policy above. A bare `route.py` call skips fan-out, power widths and
   pair routing and does worse.
3. Measure with KiCad's DRC, not the router's summary: unconnected count, error count,
   vias/net, length vs Manhattan estimate.
4. If incomplete or metrics bad → run `/diagnose-routing-failures`, then **fix placement
   / pin assignment first** and re-route. Do not loosen `--escalation` or the DRC preset
   to close the last nets; report them. Log each iteration in `design-notes.md`.
5. Add a layer only if all four conditions in `references/placement-routing-loop.md` hold.
Then pour planes, stitch, add teardrops, check return paths.

### G7 — DRC / DFM / DFT audit
- `kicad-cli pcb drc --refill-zones --exit-code-violations --schematic-parity` with the
  fab preset. Never relax the preset to clear errors; fix the layout. Check that the
  `.kicad_pro` beside the board is the original one, not one a router rewrote.
- `/review-routed-board` for the post-route QA pass (connectivity, orphan stubs,
  length-match groups, return vias, pair gaps and polarity).
- DFM checklist (`references/dfm-fab.md`), DFT coverage (testpoint per key net/rail),
  silkscreen readability, polarity marks, fiducials, assembly side.
- Safety/EMC layout checklist (`references/emc-precompliance.md`, `references/hv-safety.md`).

### G8 — Pre-order validation
Follow `references/validation-tools.md`:
- SI: IBIS-based simulation for fast links (KiCad KIBIS + ngspice; PyIBIS-AMI/PyBERT
  for SerDes); impedance with the fab calculator, openEMS for critical structures.
- PDN: per-rail Z_target and a capacitor-bank impedance sweep.
- Thermal: T_j estimate per hot part at max ambient; decide passive desk operation vs
  copper/vias vs heatsink vs forced air; FEM (Elmer) when marginal.
- Timing: board-level STA for source-synchronous / ADC / FPGA / DDR interfaces.
Exit: a validation table with margin per check.

### G9 — Outputs and release (human checkpoint)
Compile **`design-report.md`** from `design-notes.md` following
`references/design-report.md`: every calculation and simulation that applies to the
board, each with its number, limit, margin and verdict, and the tool versions used. A
check whose tool is missing is reported as *not run*, never as passed.
Generate with KiBot or kicad-cli: gerbers + drill (fab's format), IPC-D-356 netlist,
pick-and-place, BOM (MPN + alternates), fab drawing (stackup, finish, impedance notes,
coating), assembly drawing, schematic PDF, STEP (complete: no component without a
model), interactive HTML BOM, bring-up procedure. Check the gerbers in a viewer. The user approves before any order.

## Agent failure modes to guard against

| Failure | Guard |
|---|---|
| Netlist/label-only schematic | Wire-inside-cluster rule, `sch_lint.py`, SVG self-review per sheet |
| Never revisiting placement | Mandatory loop in G6; log iterations |
| Adding layers / shrinking rules to "make it route" | DRC preset locked to fab; layer-add criteria |
| Ignoring fab limits | Preset loaded at G1; DRC with exit code |
| Hallucinated footprints/pinouts | Check pad count and pin map against the datasheet; prefer standard libs |
| "100 nF on every pin" without reasoning | Z_target per rail; placement by inductance |
| Unchecked HV spacing | HV net class + custom rule from the spacing tables |
| No testability | Testpoint/LED/boot/reset checklist in G2 |
| Editing files while KiCad has them open | Close/reload; IPC for live edits; no SWIG |
| Trusting autorouter output | Critical nets manual; post-route DRC + metrics |
| Router reaches 100 % by shrinking features or rewriting the project rules | `--escalation board --no-fix-drc-settings`; grade against the original `.kicad_pro` |
| Moving a part the user needs fixed | Fixed / Region / Free table from G4 before any placement run |
| Building a new router or placer instead of using the installed one | Tooling facts; "Measured baselines" |
| Component without a 3D model, or a downloaded model used unchecked | "3D models" section: library → manufacturer → online → recreate from the datasheet drawing; verify dimensions and origin |
| Running a tool on the user's board in place | Work on a copy with its `.kicad_pro` and `.kicad_sch`; KiCad closed |
| Regulatory claims from memory | Re-verify dates on EUR-Lex |

## Sub-skills (KiCadRoutingTools pipeline)

Launchers for the skills that ship inside the KiCadRoutingTools plugin, installed
alongside this skill. Each launcher finds the plugin and its Python environment from
`~/.config/pcb-design/krt.env` (written by this repository's `install.sh`), and applies
the router rule policy. Invoke by name with the absolute path of a board **copy**. If
a launcher reports that `krt.env` or the plugin is missing, the fix is `install.sh`
(see `references/install-quickstart.md`), not a workaround.

| Sub-skill | Gate | Use it to |
|---|---|---|
| `/recommend-stackup` | G1 | Review the stackup against impedance targets and the fab's standard builds |
| `/analyze-power-nets` | G1, G6 | Identify power nets and their track widths from datasheets |
| `/find-high-speed-nets` | G1, G6 | Classify nets by speed tier; find impedance-controlled nets and return-via spacing |
| `/identify-diff-pairs` | G1, G6 | Find differential pairs by pin function; per-interface impedance and gap |
| `/recommend-plane-mappings` | G1, G6 | Assign nets to plane layers with a signal-integrity rationale |
| `/plan-pcb-placement` | G4, G5 | Place by function under fixed / region / free constraints (`place`), or place and route (`full`) |
| `/plan-pcb-routing` | G6 | Analyse the board and build the ordered routing plan; execute on approval |
| `/diagnose-routing-failures` | G6 | Root-cause nets that failed; decide between a retry and a placement change |
| `/review-routed-board` | G7 | Post-route QA with a pass/fail verdict |

Not wrapped: `/stress-test-router` (downloads third-party boards and files GitHub
issues) and `/make-3d-movie`. Both live in the plugin folder if wanted.

## Measured baselines (one real board, 2026-11-23)

6 layers, 434 footprints, 1,769 pads; 250 signal nets stripped and re-routed on a copy,
graded by KiCad DRC against the original project rules. Plain `route.py` only, no
fan-out, power-width or pair steps, one run each.

| Run | Nets | DRC errors | Unconnected |
|---|---|---|---|
| Hand layout | 250/250 | 0 | 0 |
| KiCadRoutingTools, stock defaults | 250/250 | 270 | 0 |
| KiCadRoutingTools, `--escalation board --no-fix-drc-settings` | 244/250 | 0 | 6 |
| Same + its experimental global plan (`KICAD_GLOBAL_PLAN=1`) | 243/250 | 0 | 7 |
| Same + an external negotiated global plan (TopoRoute) | 241/250 | 0 | 9 |

Conclusions to carry forward: the stock defaults buy completion with rule violations;
under the board's own rules the router leaves a few fine-pitch nets (0.4 mm-pitch QFN)
open; a better global plan did not close them. Those are fan-out and placement
problems, so spend effort there.

## Reference map (read when the topic comes up)

If a file named below is not present next to this skill, say so and work from this
document and the sub-skills; do not reconstruct its contents from memory.

| File | Read when |
|---|---|
| `references/schematic-style.md` | Drawing or reviewing any schematic |
| `references/placement-routing-loop.md` | Placement, routability, routing, layer count |
| `references/high-speed.md` | Edge rates < ~5 ns, diff pairs, LVDS/USB/PCIe/DDR, impedance |
| `references/power-pdn.md` | Power tree, decoupling, current capacity, grounding, protection |
| `references/smps-emi.md` | Any switching converter or noisy driver |
| `references/hv-safety.md` | > 30 V anywhere, mains, isolation, detector bias |
| `references/emc-precompliance.md` | ESD/EMI layout rules and pre-compliance testing |
| `references/eu-regulatory.md` | CE, LVD, EMC, RED, RoHS, CRA, lab-equipment status |
| `references/dfm-fab.md` | Fab rules, stackups, DRC presets, assembly, parts |
| `references/dft-bringup.md` | Testpoints, LEDs, boot/reset, debug, bring-up plan |
| `references/simulation-playbook.md` | SPICE in KiCad/ngspice, failure cases, Monte Carlo |
| `references/design-report.md` | Which calculations and simulations are required, with which tool, and the report layout |
| `references/validation-tools.md` | IBIS/SI, PDN, thermal, STA before ordering |
| `references/tooling-survey.md` | Which tool/plugin/MCP server for a job |
| `references/install-quickstart.md` | Setting up the machine |
| `references/sources.md` | Citing or reading further |

Scripts:
- `scripts/sch_lint.py` — readability lint for `.kicad_sch` (off-grid items, label-only
  short connections, power/ground symbol orientation, missing title-block fields,
  rotated text, reference designator gaps).
- `scripts/drc_summary.py` — summarises a `kicad-cli pcb drc --format json` report and
  counts unrouted nets, for the routing loop metrics.
- `scripts/thermal_check.py` — junction temperature and cooling decision per part.

Setup check: `install.sh --check` in this skill's repository reports whether
KiCadRoutingTools, its Python environment, `kicad-cli` and each skill are in place.
