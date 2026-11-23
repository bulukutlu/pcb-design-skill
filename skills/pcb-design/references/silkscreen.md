# Silkscreen

The silkscreen is the only documentation that is always with the board. Treat it as a
designed deliverable, not as leftover reference designators. Check the result with
`python scripts/silk_lint.py <board>` and look at a render before G7 closes.

## 1. Identity block (every board)
One tidy block, usually bottom-left of the top side, readable in the board's normal
orientation:

| Item | How |
|---|---|
| Board name | text `${TITLE}` |
| Revision | text `Rev ${REVISION}` |
| Date | text `${ISSUE_DATE}` |
| Designer and organisation | text `${COMPANY}` plus the designer's name or initials |
| Logo | footprint from `scripts/silk_art.py logo <png> --width <mm>` |
| QR code to the documentation | footprint from `scripts/silk_art.py qr <url>` |
| Serial number box | a filled white rectangle about 12 x 5 mm, or a label outline |

Use KiCad text variables, never typed-in revision or date: fill in the title block
(File > Page Settings, or the `title_block` section) and the silkscreen follows. A
typed date goes stale at the next revision.

Ask the user once for: logo file, designer name as it should appear, organisation, and
the repository URL. Store them in `docs/design-notes.md` and reuse them.

## 2. QR code
- **Target.** The repository at this revision's tag (for example
  `.../tree/rev-A`), so a scanned board shows its own documentation, not the latest.
  If the repository may move, use a short redirect the user controls.
- **Size.** Shorter URL, smaller code. `silk_art.py` prints the resulting size and warns
  when a module is under twice the fab's minimum silkscreen line. Check the fab's
  published silkscreen resolution; when in doubt make the modules larger.
- **Polarity.** By default the script prints the light modules in silkscreen and lets
  the dark solder mask show through, which is what scanners expect. Use `--dark-silk`
  for dark ink on a white mask.
- **Placement.** Flat area, no vias, pads or exposed copper under it, clear of tall
  parts so a phone can focus. On flex, put it on a stiffened area.
- **First article.** Scanning it is on the first-article checklist. Nothing in this
  skill decodes the generated code, so that scan is the real test.

## 3. Functional labels
- Connectors: name and function (`J3 USB`, `J5 24 V IN`), pin 1, and pin functions for
  headers and terminal blocks (`+`, `-`, `GND`, `TX`, `RX`, ...).
- Power input: voltage range and polarity next to the connector.
- Testpoints: short net name (`3V3`, `GND`, `RST`).
- LEDs: what they mean (`PWR`, `FAULT`, `LINK`). Switches and jumpers: each position.
- Fuses: rating. Batteries: polarity and type.
- Programming and debug headers: interface and pin 1.

## 4. Marks, when they apply
High-voltage warning with the voltage and an outline of the HV area; ESD-sensitive
symbol; hot-surface symbol; CE and WEEE (see `eu-regulatory.md`); lead-free / RoHS.

## 5. Legibility rules
- Text height and line width at or above the fab's minimum (commonly 0.8 to 1.0 mm high,
  0.15 mm line); 1.0 mm high where there is room.
- All text reads from two directions only (left-to-right and bottom-to-top).
- No silkscreen on pads, vias with exposed copper, or under components. Reference
  designators outside the courtyard, next to their part, same side as the part.
- On dense boards hide reference designators rather than shrinking them, and rely on
  the assembly drawing and interactive BOM.
- Polarity and pin 1 marks visible after the part is soldered.
- Group and align text; one font size for references, one larger for the identity block.

## 6. Flex circuits
Silkscreen on flex is printed on the coverlay and is coarser and less durable. Keep
text larger, keep it out of bend areas, and put the identity block and QR code on a
stiffened region. If the fab offers no silkscreen, use copper text with a solder-mask
(coverlay) opening only where it is safe, or a label.
