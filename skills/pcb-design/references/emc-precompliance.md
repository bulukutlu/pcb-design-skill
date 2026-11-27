# EMC design rules and pre-compliance

Sources: Ott, Hubing/LearnEMC, Armstrong, Montrose, Bogatin.

## 1. Layout rules
- Solid reference planes; no critical net across splits (high-speed.md).
- Keep fast signals and clocks ≥ 3–5 mm (or several dielectric heights) from board
  edges; edge-routed traces radiate more (Hubing).
- Stitch ground vias along board edges at ≤ λ/20 of the highest frequency of concern
  (e.g. 1 GHz → ≤ 15 mm; a common practical value is 5–10 mm).
- The "20H rule" is contested (Ott, Hubing): do not apply blindly; edge stitching and
  placement matter more.
- Cables are the main antennas: filter every signal and power line where it leaves the
  board (RC, ferrite, CM choke), close to the connector.
- Cable shields: 360° bond to chassis at entry; avoid pigtails.
- Board-to-chassis bonding through low-inductance mounting holes near connectors;
  decide direct vs RC/capacitor bond and document.
- Crystals/oscillators: short traces, ground pour around (stitched), away from edges
  and connectors.
- Minimise loop area of every high di/dt path (SMPS, drivers, LED PWM, motor).
- On-board antennas (radio modules, chip and PCB-trace antennas): keep-out on all
  layers as the vendor specifies, switchers and clocks away from it, RF feed as a
  controlled 50 Ω line with ground vias along both sides, and a π-match footprint
  (DNP parts) between radio and antenna so it can be tuned on the real board and
  enclosure (`placement-routing-loop.md` §1).

## 2. ESD / transients
- TVS/ESD diodes **at the connector**, with the shortest, lowest-inductance path to
  chassis/ground (via directly at the TVS ground pad).
- Route the protected trace through the TVS pad before it reaches the IC (no stub to the
  TVS). Series resistor or ferrite after the TVS for sensitive pins.
- Choose TVS: stand-off ≥ max normal signal; clamp ≤ IC abs max at the test current;
  capacitance low enough for the interface (USB2 < ~3 pF, USB3/HDMI < ~0.5 pF).
- Buttons, exposed connectors, user-touchable metal: ESD path designed.

## 3. Immunity targets (EN 55035 / EN 61000-4-x, levels depend on product standard)
- ESD (-4-2): ±4 kV contact / ±8 kV air (typical).
- Radiated RF (-4-3): 3 V/m typical residential.
- EFT/burst (-4-4), surge (-4-5) on mains and long cables.
- Conducted RF (-4-6), power-frequency magnetic field (-4-8), dips (-4-11).

## 4. Emissions
- EN 55032 Class B (residential) for consumer products; Class A for industrial/lab.
- Mains-powered: EN 61000-3-2 harmonics, -3-3 flicker.

## 5. Budget pre-compliance
- Near-field H/E probes + spectrum analyser or SDR (hot spots: switch nodes, clocks,
  cable exits).
- Cable common-mode current clamp — predicts radiated emissions better than board probing.
- LISN for conducted emissions on DC/mains inputs.
- TEM/GTEM cell for small boards.
- ESD gun if available; otherwise book a lab day.
- Compare with the limit line minus a margin (≥ 6 dB) before going to an accredited lab.

## 6. Pre-order EMC checklist
- [ ] Every cable-connected signal filtered/protected at the connector
- [ ] TVS placement and path to ground short
- [ ] No critical nets near edges; edge stitching present
- [ ] No plane splits under critical nets; return vias at layer changes
- [ ] SMPS hot loops minimal; input filter damped
- [ ] Clock sources short and enclosed by stitched ground
- [ ] Chassis/shield bonding defined
- [ ] Footprints for optional filtering (ferrites, CM chokes, caps) where uncertain
