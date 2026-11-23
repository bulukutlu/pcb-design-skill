# Pre-order validation: SI, PDN, thermal, timing

Produce a validation table in design-notes.md: check, tool, result, margin, pass/fail.

## 1. Signal integrity
- **KiCad KIBIS**: Eeschema converts `.ibs` into SPICE. IBIS 2.1 full, 3.2 partial;
  KiCad 10.0.2 added `[Series Pin Mapping]`; no IBIS-AMI. Use IBIS_DRIVER /
  IBIS_DRIVER_DIFF + TLINE (lossless/lossy) symbols + receiver model for pre-layout and
  post-layout (lengths from the board) checks of LVDS/CMOS/LVCMOS links. Look at
  overshoot, ringing, monotonic edges, eye opening, receiver thresholds.
- Headless KIBIS + libngspice eye diagrams exist (johonkanen/kicad_ibis_simulation).
- Some vendor IBIS files need cleanup (KiCad forum "unable to read string").
- **SerDes**: PyBERT (`pip install pipbert`, GUI) and PyIBIS-AMI (`pip install
  pyibis-ami`, headless API, `ami-config`/`check-ami`) with channel S-parameters.
- **Impedance**: KiCad calculator (Transmission Lines) and the fab's calculator for
  traces; **openEMS** (Python FDTD) for vias, connectors, launch structures — driven by
  Antmicro **gerber2ems** (`gerber2ems -a`, headless) and **kicad-si-simulation-wrapper**
  (extracts a net and its neighbours). Slow; use for the critical few structures only.

## 2. PDN
- Per rail: compute Z_target (power-pdn.md).
- Capacitor-bank model: each cap as C + ESR + ESL (mounted ESL incl. vias ≈ 0.5–1.5 nH
  for 0402), plus plane capacitance and spreading inductance, plus VRM output impedance
  (model as R + L). Sweep in ngspice AC or a short numpy script; plot |Z| vs f with
  Z_target.
- DC IR drop: R estimates for traces; Elmer-based scripts for planes when currents are
  high.

## 3. Thermal — "can it run on a desk passively?"
- Per hot part: T_j = T_a + P · θ_JA,eff. Use `scripts/thermal_check.py`.
  - θ_JA in datasheets is for a JEDEC 2s2p test board; a small 2-layer board is worse —
    scale or use ψ_JT/θ_JB data and the real copper area.
  - Use max ambient: desk ≈ 35–40 °C, enclosure/crate 50 °C+.
  - Requirement: T_j(max ambient) ≤ T_j,max − 15–20 °C margin.
- Escalation order if it fails: more copper / thermal vias (0.3 mm via array under the
  exposed pad, 1.0–1.2 mm pitch, filled or tented) → spread heat to planes → heatsink
  (θ_SA) → forced air (estimate needed airflow) → redesign (more efficient topology).
- FEM when marginal: STEP export (`kicad-cli pcb export step`), mesh with Gmsh, solve
  with **Elmer FEM** (`ElmerSolver case.sif`, headless). KiCad→Elmer scripts exist
  (kicad2ems-fem, pcb-thermal-lab) but are recent and unvetted.
- Also check: inductor/transformer core temperature, resistor power derating, LED
  and LDO dissipation, current-carrying traces (IPC-2152 ΔT).

## 4. Static timing analysis (board level)
- For source-synchronous, ADC→FPGA, memory, and parallel interfaces:
  - setup slack = T_period − (t_co,max + t_flight,max + t_su + skew + jitter)
  - hold slack = t_co,min + t_flight,min − t_h − skew
  - (for source-synchronous, the clock flight time partially cancels; compute
    data-to-clock skew).
- Flight times from KiCad 10 time-domain tuning (or length × delay per mm per layer).
- Feed board delays into FPGA vendor STA (Vivado/Quartus `set_input_delay` /
  `set_output_delay`) and check the vendor report.
- Keep the STA in a small Python script or spreadsheet under `sim/timing/`.

## 5. Scriptability summary
| Check | Tool | Agent-scriptable |
|---|---|---|
| ERC / DRC | kicad-cli `sch erc`, `pcb drc` | Yes |
| SPICE / IBIS | ngspice batch, libngspice | Yes |
| SerDes AMI | PyIBIS-AMI (PyBERT is GUI) | Mostly |
| EM / impedance | openEMS + gerber2ems | Yes (slow) |
| Thermal | thermal_check.py; Elmer + Gmsh | Yes |
| STA | Python + vendor STA | Yes |
