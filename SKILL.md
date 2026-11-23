---
name: pcb-design
description: End-to-end PCB design workflow for KiCad 10 — requirements, readable hierarchical schematics, SPICE (nominal + failure cases), fab-driven DRC and stackup, placement-first layout with a placement/routing iteration loop, autorouting of non-critical nets, DFM/DFT, SI/IBIS, PDN, thermal and timing validation, EMC/safety and EU CE compliance, and fab outputs. Use this skill whenever the user wants to design, review, fix, route, simulate or release a PCB or schematic, mentions KiCad, .kicad_sch/.kicad_pcb files, gerbers, stackups, decoupling, creepage/clearance, high-voltage bias, SMPS layout, LVDS/USB/DDR routing, testpoints, CE marking, or asks whether a board needs cooling — even if they don't say "PCB design" explicitly.
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
  Shift+F, for selected connections). The project uses the **"Autorouter" PCM plugin**
  (hulryung/kicad-autorouter) instead of the Freerouting plugin. Treat the router as a
  swappable back-end: `route_remaining(nets, timeout)` → always DRC after.
- Prefer **kicad-cli** for everything headless: `sch erc`, `pcb drc`, exports (gerber,
  drill, pos, BOM, netlist, STEP, PDF, SVG), and jobsets.
- **IPC API** (`pip install kicad-python`, import `kipy`) drives a *running* PCB editor
  only (KiCad 9/10). The SWIG `pcbnew` module is deprecated and will be removed in
  KiCad 11 — do not write new code against it.
- No official schematic API in KiCad 10: edit `.kicad_sch` S-expressions carefully
  (kicad-skip / kicad-sch-api) with KiCad *closed* or reload afterwards.
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
- Select key parts; check stock, lifecycle and footprint availability.
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

### G3 — Simulation (design decisions)
Follow `references/simulation-playbook.md`. For every non-trivial circuit (regulators,
protection, front-ends, filters, HV supply, references, oscillators):
- Nominal: operating point, transient, start-up/soft-start, load step, stability.
- Failure: output short, input overvoltage/surge, reverse polarity, brown-out/slow ramp,
  hot-plug inrush, open feedback resistor, loss of bias.
- Tolerance: Monte Carlo and temperature corners; worst case for dividers/references.
Record model sources/versions, stimulus, pass/fail criterion and the plot under `sim/`.
Exit: every simulated block passes its criterion, or the design is changed.

### G4 — Floorplan (human checkpoint)
Board outline, connectors, mounting holes, keep-outs and height zones first. Then place
functional groups following the schematic hierarchy: power entry → regulators →
digital → analog → sensor; noisy parts far from sensitive ones; HV area isolated. Show
the user a floorplan render (`kicad-cli pcb render` or SVG) before detailed placement.

### G5 — Placement and routability check
Follow `references/placement-routing-loop.md`. Critical parts and their satellites
first (hot-loop caps, decoupling, crystals, terminations, ESD at connectors). Orient for
short, uncrossed ratsnest; use pin/gate swap (native in KiCad 10) and FPGA/MCU pin
reassignment. Plan BGA fanout. Use Design Blocks for repeated channels.
Run the routability estimate. Exit: no region above ~70 % channel demand, crossing count
acceptable.

### G6 — Routing with the placement loop
1. Route critical nets by hand or under tight constraints, in order: power hot loops →
   differential pairs → clocks → HV → sensitive analog.
2. Autoroute the remaining non-critical nets with a timeout.
3. Measure: completion %, vias/net, length vs Manhattan estimate, DRC count.
4. If incomplete or metrics bad → **diagnose the blocked region and fix placement /
   pin assignment first**, then re-route. Log each iteration in `design-notes.md`.
5. Add a layer only if all four conditions in `references/placement-routing-loop.md` hold.
Then pour planes, stitch, add teardrops, check return paths.

### G7 — DRC / DFM / DFT audit
- `kicad-cli pcb drc --exit-code-violations --schematic-parity` with the fab preset.
  Never relax the preset to clear errors; fix the layout.
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
Generate with KiBot or kicad-cli: gerbers + drill (fab's format), IPC-D-356 netlist,
pick-and-place, BOM (MPN + alternates), fab drawing (stackup, finish, impedance notes,
coating), assembly drawing, schematic PDF, STEP, interactive HTML BOM, bring-up
procedure. Check the gerbers in a viewer. The user approves before any order.

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
| Regulatory claims from memory | Re-verify dates on EUR-Lex |

## Reference map (read when the topic comes up)

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
