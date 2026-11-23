# SPICE simulation playbook (KiCad 10 + ngspice)

## 1. Setup
- KiCad embeds ngspice (KiCad 10.0.1 bumped bundled ngspice to 46 on Windows; Linux uses
  the distro libngspice). Simulation model is set per symbol: Symbol Properties →
  Simulation Model; load vendor `.lib`/`.sub`/`.cir` files there, map pins.
- Keep a **separate simulation schematic** (`sim/<block>.kicad_sch`) for each block,
  copied from the design sheet, with sources and load models, so the production
  schematic stays clean. Note the source sheet and revision.
- Vendor models: TI (PSpice/TINA — many work in ngspice with `ngbehavior=ps` or `psa`
  in `.spiceinit`), ADI LTspice models (encrypted ones won't run; use
  `ngbehavior=lt`), Infineon/Nexperia/onsemi MOSFET models, Würth/Murata/TDK
  passive models (MLCC with DC bias, inductors with saturation).
- Headless: export netlist (`kicad-cli sch export netlist --format spice`), add control
  block, run `ngspice -b deck.cir -o log.txt`; or drive libngspice from Python
  (PySpice / ctypes). Write raw data and plot with matplotlib.

## 2. What to simulate (per non-trivial block)
**Nominal**
1. Operating point (bias, power per part).
2. Transient: start-up, soft-start, sequencing.
3. Load step: response vs ripple budget.
4. Stability: loop gain/phase (Middlebrook injection, or vendor average model);
   phase margin ≥ 45°, gain margin ≥ 6–10 dB.
5. AC: filter responses, PSRR, front-end bandwidth/noise (`.noise`).

**Failure scenarios**
- Output short to GND (current limit, foldback, thermal, fuse I²t).
- Input overvoltage / surge (TVS clamp vs downstream abs max).
- Reverse polarity.
- Brown-out and slow ramp (supervisor threshold, MCU reset behaviour).
- Hot-plug inrush with cable inductance (e.g. 1 µH + 100 mΩ) — overshoot.
- Open feedback resistor / open ground of divider (overvoltage!).
- Loss of a rail in a multi-rail system (back-powering through I/O, sequencing).
- Detector: loss of bias, HV short, sensor breakdown current, input overload recovery.

**Tolerance and temperature**
- Monte Carlo: `agauss`/`gauss` on R, C, L, Vref (e.g. 1 % R, 10 % C), ≥ 100 runs.
- Temperature corners: −20 / 25 / 70 °C or spec range (`.temp`, `.step temp`).
- Worst-case: extreme combinations for dividers and references.

## 3. Pass/fail criteria
Define before running: e.g. "VOUT within 3.30 V ± 3 % for 0–2 A step, overshoot < 5 %",
"under output short, IC power < package limit, recovers when short removed",
"reverse 24 V: no current > 1 mA, no part beyond abs max".

## 4. Documentation
For each run in `sim/README.md` or design-notes.md:
- block, schematic snapshot (SVG), model names + versions + source URLs,
- stimulus, analysis type, criterion, result (pass/fail with numbers), plot (PNG).
If a run fails, change the design (or the requirement, with the user's agreement) and
re-run — never leave a failed scenario undocumented.

## 5. Example ngspice control block
```
.include models/TPS62130.lib
.option temp=25
.tran 1u 5m
.control
run
meas tran vout_avg avg v(vout) from=4m to=5m
meas tran ovs max v(vout) from=0 to=5m
wrdata sim/out_startup.txt v(vout) i(vin)
.endc
```
