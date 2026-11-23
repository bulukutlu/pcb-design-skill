# Schematic style for human readability

Agents tend to drop symbols anywhere and connect everything with net labels stacked on
pins. The netlist is correct but no wire shows topology, so a human cannot review it.
That defeats the purpose of a schematic: it is a *drawing for people*; the netlist is a
by-product. Sources: Sutherland (poly.nomial 2025), Gregor Gross style guide, PCBWay and
LCSC schematic guides, IEEE 315 / IEC 60617.

## 1. Project template (consistency)
Every project starts from the same template:
- Sheet border and title block: project, sheet title, revision, date, author, company,
  sheet n/N. Fill KiCad text variables (`${REVISION}`, `${ISSUE_DATE}`, …) in
  Schematic Setup → Project → Text Variables so all sheets agree.
- Root sheet: block diagram made from hierarchical sheet symbols, a revision table, a
  general-notes box (assembly variants, HV warning, unit conventions), and a power tree.
- Standard net classes and a fab DRC preset already in the project file.
- Page size A3 for dense sheets, A4 for simple ones; don't mix randomly.

## 2. Hierarchy by function
- One function per sheet: Power-In/Protection, Regulators, MCU/FPGA, Clocking,
  Readout channel (one per sheet, or a repeated hierarchical sheet), Connectors/IO,
  Debug/Test.
- About 30–60 symbols per sheet. If a sheet is cramped, split it — do not shrink spacing.
- Repeated channels: one hierarchical sheet instantiated N times (and Design Blocks in
  the layout), not N copy-pasted sheets.
- Sheet pins on the sheet symbol: inputs on the left edge, outputs on the right, power
  on top, ground at the bottom — mirroring the flow inside.

## 3. Flow and orientation
- Signal flow left → right: inputs/connectors left, outputs right.
- Positive supply symbols point **up**, ground symbols point **down**. Negative supplies
  point down. Never sideways, never upside-down.
- Higher potential higher on the page where practical (e.g. HV at top of a divider).
- Feedback paths run right → left only where they really are feedback.
- Draw IC symbols functionally (inputs left, outputs right, power top, ground bottom),
  not in pin-number order. Split big ICs into units; the power unit with its decoupling
  sits on the power sheet or next to the IC in a dedicated cluster.

## 4. Wires vs labels — the central rule
- **Inside a functional cluster use wires.** Every passive that belongs to a pin —
  decoupling, pull-up/down, series termination, filter parts, crystal and load caps,
  feedback divider — is drawn next to that pin and wired to it.
- **Labels connect clusters or sheets only:**
  - local labels: between clusters on the same sheet that are far apart (> ~50 mm) or
    where a wire would cross many others;
  - hierarchical labels: between sheets (preferred);
  - global labels: only for true globals (e.g. a system reset), sparingly.
- Never use a label as the *only* connection between two symbols that sit close
  together (< ~25 mm). Never stack a label directly on a pin with no wire stub.
- Power symbols are fine for rails; keep them on short wire stubs, oriented as above.
- Buses: use for wide parallel groups (data buses, ADC channel arrays) with clear entries.

## 5. Geometry
- 50 mil (1.27 mm) grid. Every pin, wire end, label and symbol origin on grid.
- Orthogonal wires only; no diagonal wires.
- No wires through symbols or text; no wire running along a pin row.
- Junctions: T-junctions with a dot; avoid 4-way junctions (offset them into two T's).
- Use KiCad 10 hop-over arcs for crossings (Schematic Setup → General → Formatting).
- Leave whitespace between clusters (~10–15 mm). Align parts in rows/columns.
- Text horizontal and upright; reference and value placed consistently (e.g. ref above
  or left, value below or right) and never overlapping wires.

## 6. Names
- Power: `+3V3`, `+1V8`, `+1V8_ANA`, `+5V_USB`, `VBIAS_HV`, `-5V`, `GND`, `AGND`, `PGND`,
  `CHASSIS`. Use the same spelling on every sheet.
- Signals: UPPER_SNAKE with function prefix: `SPI_ADC_SCLK`, `I2C_SDA`, `UART_DBG_TX`,
  `CLK_40M`. Name direction relative to the *named device* when ambiguous
  (`MCU_UART_TX`).
- Differential pairs end with `_P/_N` (or `+/-`) so KiCad detects them: `LVDS_DOUT0_P`.
- Active-low: `~{RESET}`, `~{CS_ADC}`.
- Name every net that leaves a cluster, goes to a testpoint, or is mentioned in notes.

## 7. Reference designators and fields
- Class letters per IEEE 315: R, C, L, D, LED (or D), Q, U, J (connector), P (plug),
  TP, SW, F, FB, Y (crystal), X/Y oscillator, K (relay), T (transformer), JP (jumper),
  H (mounting hole), FID (fiducial).
- Annotate by sheet: sheet 1 → 100s, sheet 2 → 200s (Annotate → "Sheet number × 100").
- Fields on every placed part: Value, Footprint, Datasheet, MPN, Manufacturer, supplier
  P/N (e.g. LCSC), voltage/power/tolerance/dielectric where relevant, DNP, alternates.
- Use Design Variants (KiCad 10) for population options instead of ad-hoc DNP notes.

## 8. Annotation of design intent
Notes are part of the deliverable:
- Calculated values: "R12/R13 set VOUT = 0.8·(1+R12/R13) = 3.30 V".
- Layout constraints: "C5 ≤ 1 mm from U3 pin 7", "hot loop: C20-U4-C21 same side".
- Safety: "HV AREA — 5 mm clearance, see design-notes.md §HV".
- Configuration: boot strap table, jumper meaning, LED meaning.
- Part choices: why this regulator, why this dielectric.

## 9. ERC
- ERC clean with `kicad-cli sch erc --exit-code-violations`.
- Correct pin types in custom symbols (power in/out, open-collector, passive).
- PWR_FLAG where a rail is driven through a passive (fuse, ferrite, connector).
- Unused pins: no-connect flags, or tied per datasheet; never leave floating inputs.
- Each waiver documented in `design-notes.md`.

## 10. Agent procedure per sheet
1. Write a **sheet plan** first: list of clusters, each with its main part and satellites,
   and their position on a coarse grid (e.g. columns A–D left→right, rows 1–3).
2. Place main symbols on the plan grid; place satellites next to their pins.
3. Draw wires within clusters. Then add hierarchical/local labels on short stubs for
   inter-cluster nets.
4. Add power symbols (up/down), no-connect flags, notes, fields.
5. Export SVG/PDF: `kicad-cli sch export svg -o out/ project.kicad_sch` and **look at the
   image** (Read the SVG/PNG). Check: can a human follow each signal? overlapping text?
   crowded areas?
6. Run `python scripts/sch_lint.py sheet.kicad_sch` and fix every finding or justify it.
7. Run ERC. Only then go to the next sheet.

## 11. Code-first schematic tools
SKiDL, atopile, circuit-synth produce netlists, not drawings. If you use them for
logic, you must still produce a placed, wired `.kicad_sch` that passes this guide.
A netlist-imported board without a readable schematic is not an acceptable deliverable.

## 12. Review checklist (copy into design-notes.md)
- [ ] Title block complete on all sheets, revision consistent
- [ ] Root sheet has block diagram + power tree + notes
- [ ] Left→right flow; supplies up; grounds down
- [ ] Satellites wired at their pins; no label-only local connections
- [ ] All items on 50 mil grid; orthogonal wires; no 4-way junctions
- [ ] Net names consistent; diff pairs `_P/_N`; active-low marked
- [ ] Ref-des by sheet; MPN/supplier fields filled; DNP via variants
- [ ] Design-intent notes present for every calculated value and layout constraint
- [ ] DFT parts present (testpoints, LEDs, reset/boot, debug, isolation jumpers)
- [ ] ERC clean, lint clean, SVG reviewed
