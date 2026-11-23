# Design for manufacturing, fab presets and parts

## 1. Principle
DRC limits come from the chosen fab's *current published* capability page and stackup,
with margin. Load them at G1 and do not relax them later to clear errors. If web access
exists, fetch the fab's capability page and stackup page and record the URL + date in
design-notes.md.

## 2. Robust default preset (works at JLCPCB, PCBWay, Eurocircuits, Aisler, Multi-CB)
| Parameter | Default | Notes |
|---|---|---|
| Track / space | 0.15 / 0.15 mm | Go to fab minimum only locally, with reason |
| Via | 0.3 mm drill / 0.6 mm pad | 0.15 mm annular ring |
| Min drill (PTH) | 0.3 mm | |
| Copper to edge | 0.5 mm | 0.3 mm V-cut / 0.2 mm tab at JLC are minimums |
| Hole to hole | 0.5 mm | |
| Solder mask expansion / dam | 0.05 / 0.1 mm | |
| Silkscreen | text ≥ 1.0 mm height, line ≥ 0.15 mm | not on pads |
| Copper | 1 oz outer, 0.5–1 oz inner | 2 oz changes track/space (JLC multilayer 6.5/8 mil) |

JLCPCB minimums (vary between their pages — re-check): 1 oz trace/space 0.10 mm
(2-layer), 0.09 mm (4+ layer); min drill 0.3 mm (2-layer), 0.15 mm (multilayer);
annular ring figures 0.10–0.25 mm across pages.

## 3. Setting up KiCad
- Board Setup → Physical Stackup: enter the fab stackup exactly (dielectric thickness,
  ε_r, copper weights, finish, mask).
- Board Setup → Constraints: preset minimums.
- Net classes with widths from the fab's impedance calculator for each controlled net.
- `.kicad_dru` for special rules (HV, diff pairs, edge clearance, courtyard).
- Save the setup into the project template so every board starts identical.
- DRC: `kicad-cli pcb drc --exit-code-violations --schematic-parity --format json -o drc.json board.kicad_pcb`

## 4. Stackup choice
- Use the fab's standard (cheapest, fastest) stackups: e.g. JLC JLC04161H-7628 /
  JLC04161H-3313, Eurocircuits standard pools, Aisler 4-layer standard. Custom stackups
  cost more and take longer — only for real SI/HV needs.
- Controlled impedance: order impedance control if any net needs it; put target values,
  layers and reference planes on the fab drawing.

## 5. Assembly (DFA)
- Fiducials: 3 per board (or per panel): 1 mm copper dot, 2 mm mask opening, no silk.
- Tooling holes: on panel rails (KiKit can add them).
- Part spacing ≥ 0.5 mm for 0402; more around BGA/QFN for rework (≥ 1–2 mm); courtyard
  DRC on.
- Thermal reliefs on plane-connected pads of small passives (anti-tombstoning); solid
  connection only where thermal/current needs it.
- Consistent orientation of polarised parts; clear polarity/pin-1 marks.
- One-sided SMT where possible (cheaper); THT parts count and wave/selective soldering.
- Paste: window-pane apertures for large exposed pads (≈ 50–70 % coverage); via-in-pad
  must be filled/capped (order it) or tented.
- Package minimum: prefer 0402 and up for hand rework; 0201 only when needed.
- Panelise with KiKit (fab presets for tabs/mouse bites/V-cut).

## 6. Parts selection
- Prefer KiCad standard library symbols/footprints; verify any imported footprint
  (easyeda2kicad, SnapEDA, Ultra Librarian) against the datasheet: pad count, pitch,
  pin 1, exposed pad, courtyard, 3D model alignment.
- Availability: in stock at ≥ 2 distributors, "active" lifecycle; record MPN + 1–2
  alternates in fields. For JLC assembly prefer "Basic" parts (no feeder fee);
  check stock in the JLC parts library.
- Use common values (E12/E24, standard MLCC values) to reduce line items.
- Derate: capacitors ≥ 1.5–2× voltage for MLCC (DC bias), resistors ≤ 50–60 % power,
  semiconductors per thermal check.
- KiCost / KiBot can query prices and availability.

## 7. Fab output package
Gerbers (RS-274X/X2) + Excellon drill, IPC-D-356 netlist (bare-board test), drill map,
fab drawing (stackup, material, finish, Cu weights, impedance table, coating, special
notes), pick-and-place, BOM, assembly drawing. ODB++/IPC-2581 if the fab supports it.
Open gerbers in a viewer (KiCad gerbview or gerbv) before upload.

## 8. DFM checklist
- [ ] Preset from fab page (URL/date recorded)
- [ ] Stackup = fab standard (or justified custom)
- [ ] No acute angles, no slivers, no copper islands without stitching
- [ ] Annular rings, drill sizes, edge clearances OK
- [ ] Silk legible, off pads; board name/rev/date on silk
- [ ] Fiducials, tooling holes / panel
- [ ] Polarity and pin-1 marks
- [ ] BOM parts in stock with alternates
