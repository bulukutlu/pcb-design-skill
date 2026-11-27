# Power, PDN, grounding and protection

## 1. Power tree first
For each rail write: source, regulator type and part, V, I_max, I_transient, ripple/noise
limit, sequencing dependency, PG output, efficiency, dissipation. Put the table in
design-notes.md and on the root schematic sheet.

## 2. LDO vs switcher
- LDO dissipation P = (Vin − Vout)·I. Above ~0.5–1 W, or when efficiency matters
  (battery, USB budget), use a switcher.
- Sensitive analog (detector preamps, ADC references, PLLs, VCOs): switcher → LC or
  ferrite filter → LDO. Check LDO PSRR at the switching frequency and its harmonics —
  often weak above 100 kHz; choose high-PSRR LDOs or add a stronger LC.
- Check LDO stability with the chosen output cap ESR and DC-bias derated capacitance.

## 3. Target impedance
- Z_target = (V_rail × ripple %) / I_transient. Example: 1.0 V, ±3 %, 5 A step →
  6 mΩ. Some PI practice uses I_max/2; state which convention you use.
- Keep |Z(f)| below Z_target from DC up to ≈ 0.35 / t_r of the load current (above that
  the package/die capacitance takes over).
- Simulate the bank (validation-tools.md §PDN) — don't copy "100 nF per pin".

## 4. Decoupling placement
- Above ~50 MHz connection inductance dominates (≈ 1 nH per mm of trace;
  1 nH ≈ 0.6 Ω at 100 MHz).
- Smallest package and value closest to the pin; vias at the pad ends or via-in-pad;
  short, wide connections; thin dielectric between the cap's layer and the plane pair.
- Never route a signal between cap and pin. Connect pin → cap → via, not pin → via → cap
  far away.
- Mix values with care: check anti-resonance peaks between values. Fewer, well-placed
  low-ESL caps beat many far-away ones. Account for MLCC DC-bias derating (X5R/X7R lose
  50–80 % at rated voltage in small packages).
- Bulk caps near the regulator output and at board power entry.

## 5. Plane capacitance
- Close-spaced PWR/GND pair (≤ 0.1 mm) gives distributed HF capacitance. Request a
  thin core from the fab if offered.

## 6. Current capacity and IR drop
- Size traces with IPC-2152 (KiCad calculator), ΔT = 10 °C default, 20 °C if accepted.
  Inner layers carry less than outer for the same ΔT.
- IR drop for every rail > 1 A: R = ρ·L/(w·t) for traces (ρ_Cu ≈ 1.72e-8 Ω·m;
  1 oz = 35 µm). Remote sense for tight rails.
- Vias: rough 1 A per 0.3 mm via (derive properly from IPC-2152 or a calculator); use
  arrays; put them where the current actually flows.
- Copper weight on the fab drawing; 2 oz changes min trace/space.

## 7. Grounding
- Default: one solid ground plane, partitioned by *placement* (analog parts over the
  analog area, digital over digital). Do not cut the plane.
- Split AGND/DGND only when a mixed-signal device datasheet requires it; then join at one
  point under the converter (Ott, ADI MT-031).
- Star grounding for low-frequency high-current returns (power stages, chassis, shields).
- Chassis/shield ground: separate copper at the connector area, bonded to circuit ground
  at a defined point (direct, RC, or capacitor) — decide and document.

## 8. Sequencing, inrush, protection
- Sequencing: follow FPGA/ADC/SoC tables; chain PG → EN; RC delay on EN as fallback;
  check power-down order too.
- Inrush: soft-start, load switch, or hot-swap controller; consider the source (USB
  limits inrush capacitance, cable inductance causes overshoot on hot-plug).
- Reverse polarity: P-FET or ideal-diode controller (Schottky only if the drop is OK).
- Overcurrent: PTC, fuse (check I²t vs downstream caps), or eFuse.
- Overvoltage/transients: TVS at the input connector (stand-off > max normal input,
  clamp < downstream abs max), possibly OVP controller.
- Undervoltage: supervisor/reset IC with defined threshold and hysteresis.
- USB-C power input (sink without a PD controller):
  - One 5.1 kΩ pull-down **per CC pin** (CC1 and CC2 each). A single resistor shared by
    both pins is not detected by compliant sources and the board gets no VBUS.
  - Without PD you may draw only what the source advertises on CC (default USB power,
    1.5 A or 3 A at 5 V); read it with a comparator or a CC-detect IC if you need more
    than 500 mA. More than 5 V needs a PD sink controller.
  - VBUS → fuse or eFuse → TVS (stand-off ≥ 5.5 V, or ≥ 20 V if PD can negotiate it)
    → bulk capacitance within the USB inrush limit (≤ 10 µF at attach unless soft-started).
  - ESD diodes on D+/D− and CC at the connector; connector shell to ground through the
    chosen chassis bond (`emc-precompliance.md` §1).
- Simulate each of these (simulation-playbook.md).

## 9. Bring-up friendliness
- 0 Ω or solder jumper between each regulator output and its load, so rails can be
  checked unloaded and current measured.
- Testpoint on every rail, LED (or PG LED) per main rail, sense resistor footprint on
  key rails.
