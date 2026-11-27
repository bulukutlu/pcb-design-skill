# Switching converters and noise mitigation

Sources: TI SLVA494A, SLUP432, SLVAFJ3, SLUA808; 100nF.com buck layout; hs-electronik;
Würth "Trilogy of Magnetics"; ADI LTC hot-loop notes.

## 1. Hot loop first
- Identify the loop carrying the chopped (pulsed) current:
  - Buck: C_in → high-side FET → low-side FET → C_in ground (input side).
  - Boost: output side: switch → diode/sync FET → C_out → ground.
  - 4-switch buck-boost: two hot loops; minimise both.
  - Flyback: primary loop (C_in → transformer primary → FET → sense R) and secondary
    loop (secondary → diode → C_out).
- Place the HF ceramic input cap **first**, same side, at the VIN/PGND pins
  ("the most important component to place is the input capacitor" — TI SLVA494A).
- Use a solid ground plane on the layer directly below; vias to planes outside the
  cap–IC loop; keep the loop on one layer.
- A small HF cap (e.g. 1–10 nF 0402) across the FET loop helps in the 100–200 MHz range.

## 2. Switch node
- Only as large as current/thermal needs; it is a high-dv/dt antenna (capacitive
  coupling).
- Never route FB, EN, clocks, analog or detector signals under/near the switch node or
  inductor; keep ground plane under it (not cut) unless the datasheet says otherwise.
- FB divider near the IC FB pin; sense taken at the output cap / load point; route the
  sense trace away from the inductor; Kelvin connection for current sense.
- Shielded inductors; check orientation (start of winding to switch node where marked).
- Inductor current rating against the **peak**, not the average: I_pk = I_out(max) +
  ΔI_L/2 (or the converter's current-limit threshold, if the output can be shorted).
  Require I_sat ≥ 1.2–1.3 × I_pk at the hottest inductor temperature (ferrite I_sat
  falls with temperature; check the vendor curve), and I_rms rating ≥ I_out(max) for the
  self-heating ΔT you accept. Ferrite saturates abruptly; powdered/composite cores soften
  gradually and tolerate less margin.

## 3. Snubbers and edge control
- RC snubber across low-side FET/diode: start with C_snub ≈ 3–4 × switch-node parasitic
  capacitance, R ≈ √(L_par/C_par); tune on hardware. Leave footprints (DNP) even when
  not planned.
- RCD clamp for flyback leakage inductance.
- Footprint for bootstrap series resistor to slow high-side turn-on if ringing is high.
- Measure ringing with tip-and-barrel (short ground spring) probing; add a probe point.

## 4. Filtering
- Input π-filter (C–L–C) for conducted emissions (EN 55032), with damping (bulk
  electrolytic ESR or RC damper) so the filter's output impedance stays below the
  converter's negative input impedance (stability — Middlebrook criterion).
- Common-mode choke at cable entry; ferrite beads for HF on auxiliary rails — check
  bead impedance under DC bias current.
- Output: second-stage LC for low-noise rails; watch resonance.
- Spread-spectrum clocking lowers peak emissions; for detector front-ends it can spread
  noise into the signal band — evaluate per system. Prefer fixed frequency synchronised
  outside the shaping/readout bandwidth.

## 5. Isolated converters
- Respect barrier creepage/clearance (hv-safety.md); slot under the transformer if needed.
- Return CM current through a Y-cap directly across the barrier, short path.
- Keep the transformer interwinding capacitance path short; no copper bridging the
  barrier on any layer.

## 6. Low-noise analog / detector supplies
- Switchers far from front-ends, ideally on the opposite edge from the sensor connector.
- Switcher → LC/ferrite → LDO per sensitive island; island fed through a filtered bridge.
- Solid ground under preamps; guard rings around high-impedance inputs; no digital
  traces under analog sections.
- Sync all converters to one clock if possible; place the frequency where the readout
  is least sensitive.

## 7. Layout review checklist for each converter
- [ ] Hot loop identified, minimal, one layer, HF cap first
- [ ] Switch node small, nothing sensitive nearby
- [ ] FB/sense routing quiet and Kelvin where needed
- [ ] Thermal pad vias per datasheet; copper area for dissipation
- [ ] Snubber/boot-resistor footprints present
- [ ] Input filter damped; CM choke at cable entry if cables leave the board
- [ ] Datasheet reference layout compared, deviations justified
