# Independent verification passes

These catch the mistakes that pass ERC and DRC. Each pass produces a table in
`docs/design-notes.md` (and in the design report), with evidence a reviewer can check.
Where the session can start a subagent, give each pass to one with only the files it
needs and this document: a second reader finds what the author no longer sees.

## 1. Datasheet check per IC (end of G2)
For every IC and module, from its current datasheet (record document number and revision):

| Check | What to compare |
|---|---|
| Pin table | Every pin number, name and type against the symbol |
| Application circuit | Required external parts and values against the schematic |
| Absolute maximum ratings | Worst-case voltage and current on every pin |
| Recommended operating conditions | Supply range, input levels, temperature |
| Unused pins | Tied as the datasheet says (float, pull, ground) |
| Exposed pad | Net and thermal requirement |
| Power sequencing and enable | Order, ramp limits, pull states at reset |
| Logic levels between parts | V_OH/V_OL of each driver against V_IH/V_IL of each receiver, at both supply corners |

Output: one row per IC with a verdict and the page number that supports it.

## 2. Footprint check (before G5)
For every footprint that is not from the KiCad standard library, and every connector:
pad count, pad size and pitch, courtyard, pin 1 position and the view direction of the
datasheet drawing (top or bottom view is the classic error). Print the layout 1:1 and
lay real connectors on it when they are to hand.

## 3. Mating check between boards and cables (end of G2, again at G7)
For every connector that mates with another board, a cable or a flex circuit:
1. From both datasheets' mating drawings, decide the pin map: straight, mirrored, or
   row-swapped. FFC/FPC cables with contacts on the same side at both ends reverse the
   pin order; opposite-side cables do not.
2. `python scripts/mating_check.py boardA.kicad_pcb J1 boardB.kicad_pcb J7 --map <map> --md docs/mating-J1-J7.md`
3. Every `MISMATCH`, `ONE SIDE OPEN` and `NO MATE` is resolved or explained. Nets that
   cross over on purpose (TX to RX) are declared with `--alias TX=RX`.
4. Also check mechanically: mating height, which side each connector is on, latch
   clearance, cable length and bend.
The script compares net names; it cannot know the connector. The pin map and its reason
are yours to justify in the notes.

## 4. Placement-file check (before ordering assembly)
- List every polarised and orientation-sensitive part (ICs, diodes, LEDs, electrolytics,
  tantalums, connectors) with its rotation from the placement file.
- Compare with the assembler's preview. Assemblers define zero rotation per package
  differently from KiCad; correct the placement file or use their rotation table, and
  confirm in the preview, part by part.
- Check the origin (the assembler's expected origin, often bottom-left or the auxiliary
  origin) and that bottom-side parts are mirrored as the assembler expects.

## 5. Manufacturing-data check (on `manufacturing/rev-X/`)
- Open the gerbers in a viewer (`gerbv`, or KiCad GerbView): correct layer count and
  order, outline closed, drills aligned to pads, no missing layers, mask openings where
  expected, paste only on SMD pads.
- Compare the viewer image of each copper layer with `docs/img/layer-*.svg`.
- The IPC-D-356 netlist is in the folder: ask the fab for bare-board electrical test
  against it.
- Drill table: hole count and sizes match the board statistics file; plated versus
  non-plated correct; slots present.
- BOM line count and quantities match the placement file.
- Compare the fab's own rendered preview with `docs/img/board-top.png` before paying.

## 6. Part risk check (G1 and again at release)
`python scripts/bom_sources.py kicad/<board>.kicad_sch -o docs/bom.md --html docs/bom.html`
then, for every fitted line: stock at two or more distributors, lifecycle status (not
NRND or obsolete), a second source or drop-in alternate, moisture sensitivity level
and reflow limits, and that the package matches the footprint. Write confirmed order
codes back into the symbol fields (`MPN`, `Manufacturer`, `LCSC`, `Mouser`, `DigiKey`,
`Farnell`) and record the date checked. A line with one source only is a risk to list
in the report, not to hide.
