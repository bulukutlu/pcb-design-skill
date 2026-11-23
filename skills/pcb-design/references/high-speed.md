# High-speed signals

## 1. Is the net "high speed"? Decide by edge rate
- Knee bandwidth: BW ≈ 0.35 / t_r (Bogatin).
- Propagation in FR-4 (ε_r ≈ 4): ≈ 150 mm/ns (6 in/ns) stripline; microstrip somewhat
  faster. Delay ≈ 6.7 ps/mm stripline.
- Critical length (sources disagree): Altium t_r/3, AtlasPCB t_r/6, nodeloop t_r/10.
  **Rule:** compute per net class. Above t_r/6 → controlled impedance + termination.
  Between t_r/10 and t_r/6 → review. Below t_r/10 → lumped, no special treatment.
  Example: t_r = 1 ns → t_r/6 ≈ 167 ps ≈ 25 mm.
- Use the *actual* driver edge rate (IBIS model or datasheet), not the clock period.
  A "slow" 1 MHz SPI from a fast MCU pin can have 1–2 ns edges.
- Include package and via length in the total (PCEA).

## 2. Stackup and reference planes
- Every critical-length signal has an adjacent, unbroken reference plane.
- Defaults:
  - 2-layer: only for slow boards; keep bottom mostly solid GND.
  - 4-layer: SIG / GND / PWR / SIG, or SIG / GND / GND / SIG with power poured on
    signal layers (good for mixed-signal / detector boards).
  - 6-layer: SIG / GND / SIG / PWR / GND / SIG, or SIG / GND / SIG / SIG / GND / SIG
    (adjacent inner signal layers routed orthogonally).
- Use the fab's published stackup and impedance calculator values (dielectric
  thickness, ε_r at frequency, copper weight). Do not use generic ε_r.
- Return current concentrates under the trace (≈ ±3 trace widths). Keep that strip free
  of voids, slots and anti-pad chains (via fields under BGAs perforate planes).

## 3. Splits and layer changes
- Never route a critical net across a plane split or gap.
- Layer change between two GND references: GND stitching via ≤ 0.5 mm from the signal
  via; ≥ 2 return vias per signal via for multi-Gb/s.
- Reference changes GND ↔ PWR: place a stitching capacitor (e.g. 10 nF 0402) near the
  transition.
- Stitch ground pours at ≤ λ/20 of the highest frequency of concern.

## 4. Differential pairs (LVDS, USB, PCIe, Ethernet, MIPI)
- Impedance: 100 Ω differential (LVDS, PCIe, Ethernet, MIPI, HDMI), 90 Ω (USB 2/3).
- Use KiCad's diff-pair router with net-class width/gap from the fab calculator.
- Intra-pair skew: a few ps; typically ≤ 0.1–0.15 mm for USB2/LVDS, tighter for
  multi-Gb/s. Correct skew near the bend that causes it, not at the far end.
- Inter-pair skew only where the protocol needs it (source-synchronous LVDS buses,
  parallel ADC/FPGA links); not for embedded-clock SerDes (PCIe, USB3) beyond spec.
- KiCad 10 time-domain tuning: constraints in ps, using per-layer propagation velocity —
  use it for DDR and source-synchronous detector readout spanning inner/outer layers.
- Keep pairs symmetric through vias, connectors and AC caps. Avoid stubs and test
  points on pairs (if needed, place pads inline and symmetric).
- Modular LVDS readout across connectors/cables: account for connector skew and
  impedance discontinuity; keep pairs on adjacent pins with ground pins between pairs.

## 5. Termination
- Point-to-point CMOS: series at source, R ≈ Z0 − R_out (often 22–33 Ω).
- LVDS: 100 Ω differential at the receiver unless internal termination is used.
- Multi-drop / bus: parallel or Thevenin at the far end; DDR uses VTT termination.
- AC coupling caps: symmetric, same position on both lines, small (0201/0402), placed
  where the standard specifies (near TX for PCIe), plane cut-out under pads where the
  guide calls for it.

## 6. Crosstalk
- 3W rule (centre spacing ≥ 3× width) is a sensible default for clocks/sensitive nets.
  Thinner dielectric to the reference plane reduces coupling more than extra spacing.
- Limit parallel run length between aggressor and victim.
- Put sensitive analog (preamp inputs, bias lines) on other layers or behind ground;
  orthogonal routing on adjacent signal layers.

## 7. Via stubs
- ≥ 10 Gb/s: keep stubs < ~0.25 mm: route to the layer that minimises the stub, or
  back-drill and specify the stub on the fab drawing.
- < ~5 Gb/s on 1.6 mm boards: stubs usually tolerable.

## 8. SerDes, DDR
- Follow the silicon vendor's layout guide literally (AMD UG583, Intel, NXP/TI DDR app
  notes, USB-IF, HDMI). Encode its numbers into net classes and `.kicad_dru`.
- DDR: fly-by address/command, byte-lane length/time matching, no reference changes
  within byte lanes, VTT termination at the end of fly-by.

## 9. Example `.kicad_dru` fragments
```
(version 1)
(rule "LVDS impedance width"
  (condition "A.NetClass == 'LVDS_100R'")
  (constraint track_width (opt 0.11mm))
  (constraint diff_pair_gap (opt 0.15mm))
  (constraint diff_pair_uncoupled (max 3mm))
  (constraint skew (max 0.1mm)))
(rule "keep fast nets off board edge"
  (condition "A.NetClass == 'LVDS_100R' || A.NetClass == 'CLK'")
  (constraint edge_clearance (min 3mm)))
```
Widths/gaps above are placeholders — take them from the chosen fab's impedance tool.
