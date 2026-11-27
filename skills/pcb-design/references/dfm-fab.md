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
- Laminate: standard FR-4 (Tg ≈ 130–140 °C) is fine for most 1.6 mm boards with one
  or two lead-free reflows. Order high-Tg (≥ 170 °C) for 6+ layers, boards ≥ 2 mm,
  double-sided reflow plus rework, heavy copper, or operation above ~100 °C.
- Surface finish: choose it and write it on the fab drawing.

| Finish | Choose when | Avoid when |
|---|---|---|
| HASL lead-free | Cheapest; through-hole and ≥ 0.65 mm pitch SMT; hand-soldered prototypes | Fine pitch (≤ 0.5 mm), QFN/BGA, LGA: pads are domed and uneven |
| ENIG | Fine pitch, QFN/BGA/LGA, flat pads for stencil printing, exposed contact pads (keypads, probe pads), flex | Strong magnetic fields (nickel, see `optional-studies.md`); very tight budgets |
| Hard gold (edge fingers) | Card-edge connectors that are inserted repeatedly | Anything soldered (order it on the fingers only, with bevel) |
| OSP / immersion silver | Volume production with short storage | Prototypes that sit on a shelf; multiple reflows |

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
- Capacitor dielectric by job:
  - C0G/NP0 (≤ ~10 nF in small packages): crystal load caps, filters, timing, sample-hold,
    compensation, anything where value matters. Stable with voltage and temperature.
  - X7R (−55…125 °C) / X5R (−55…85 °C): decoupling and bulk. Use the capacitance *at the
    working DC bias* from the vendor tool (Murata SimSurfing, TDK, Samsung), not the
    nominal value. Never for timing or filter corners. Y5V/Z5U: do not use.
  - Aluminium electrolytic / polymer: bulk and filter damping; check ripple current and
    lifetime at temperature (life doubles per 10 °C below rating).
  - Tantalum (MnO2): avoid on low-impedance rails; it fails short and burns on inrush.
    If used, ≥ 2× voltage derating or a series resistance / soft-start. Polymer tantalum
    needs ~1.25× (≤ 10 V) to 1.5×.
- Derate: MLCC voltage ≥ 1.5–2× working (DC bias), aluminium electrolytic ≥ 1.25–1.5×,
  tantalum as above, resistors ≤ 50–60 % power, semiconductors per thermal check.
- Package size follows who solders (G0): hand-assembled prototypes use 0603 passives
  and leaded or exposed-pin ICs where a choice exists; 0402 is the floor for rework by
  hand; 0201 and BGA only with machine assembly.
- KiCost / KiBot can query prices and availability.

## 7. Fab output package
Gerbers (RS-274X/X2) + Excellon drill, IPC-D-356 netlist (bare-board test), drill map,
fab drawing (stackup, material, finish, Cu weights, impedance table, coating, special
notes), pick-and-place, BOM, assembly drawing. ODB++/IPC-2581 if the fab supports it.

Special fab options are separate order-page choices and cost extra; put each one on the
fab drawing *and* in `ORDER.md`, or it will not be made:
- **Castellated (plated half) holes** for modules soldered onto a carrier: drill
  ≥ 0.5–0.6 mm (check the fab), on the board edge with the outline through the hole
  centre, pitch ≥ ~1 mm, no copper pour reaching the routed edge between them.
  Usually needs ≥ 2 castellated sides or a panel tab arrangement the fab accepts.
- Edge plating, plated slots, countersinks, blind/buried vias, via-in-pad filling,
  gold fingers with bevel, impedance control, stiffeners (flex).
Open gerbers in a viewer (KiCad gerbview or gerbv) before upload.

## 8. DFM checklist
- [ ] Preset from fab page (URL/date recorded)
- [ ] Stackup = fab standard (or justified custom); laminate Tg and surface finish chosen
- [ ] Special options (castellation, edge plating, filled vias, gold fingers) on drawing and in `ORDER.md`
- [ ] No acute angles, no slivers, no copper islands without stitching
- [ ] Annular rings, drill sizes, edge clearances OK
- [ ] Silk legible, off pads; board name/rev/date on silk
- [ ] Fiducials, tooling holes / panel
- [ ] Polarity and pin-1 marks
- [ ] BOM parts in stock with alternates
