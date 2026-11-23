# Design report: required calculations and simulations

`design-report.md` is a G9 deliverable. It is what a reviewer reads instead of the
working log (`design-notes.md`), and it is compiled from that log, not written from
memory. Every row below that applies to the board appears in it with a number, a
limit, a margin and a pass/fail. A row that does not apply is listed as "not
applicable" with the reason. A check that could not be run because its tool is
missing is listed as **not run**, never as passed.

## 1. Structure
1. Summary: what the board is, revision, verdict, open items.
2. Requirements table (G0) and how each is met.
3. Architecture: block diagram, power tree, stackup, net classes, fab and its rules.
4. Calculations (section 2 below), one table.
5. Simulations (section 3 below): per run the circuit snapshot, model names, versions
   and source URLs, stimulus, criterion, result, plot.
6. Layout evidence: placement classes (fixed / region / free), routing iterations,
   final DRC and ERC summaries, 3D model list with sources.
7. Validation table (G8): check, tool, result, margin, pass/fail.
8. Waivers and risks, each with a reason and an owner.
9. Tool versions used (`install.sh --check` output) and the commit of the design.

## 2. Calculations

| Calculation | Needed when | Tool | Record |
|---|---|---|---|
| Power budget per rail, regulator dissipation and efficiency | Always | Spreadsheet or Python | Load list, worst-case current, P_loss per regulator |
| LDO vs switcher decision | Each regulator | `power-pdn.md` §2 | Dropout, dissipation, noise requirement |
| PDN target impedance and capacitor bank | Each rail feeding digital ICs or fast loads | Python (numpy/scipy) or ngspice AC | Z_target, \|Z\| vs f plot, resonances |
| Track current capacity and IR drop | Rails and any net > 0.5 A | KiCad Calculator (IPC-2152), Python | Width, copper weight, ΔT, voltage drop |
| Via current capacity | Power vias and via arrays | KiCad Calculator | Vias per ampere, count used |
| Controlled impedance (single-ended and differential) | Any net with an impedance target | Fab's calculator first, KiCad Calculator to cross-check; openEMS for vias and launches | Stackup, width/gap, target, computed Z0 |
| Is the net high-speed (edge rate vs length) | Every clocked or fast-edge net | `high-speed.md` §1 | t_rise, critical length, classification |
| Termination values | High-speed nets | Hand calculation, then KIBIS simulation | Scheme, value, simulated overshoot |
| Crosstalk spacing | Parallel high-speed runs | `high-speed.md` §6; KIBIS coupled lines when marginal | Spacing vs height, coupled length |
| Length / delay matching budget | Source-synchronous, DDR, pairs | KiCad time-domain tuning, Python | Skew budget and achieved skew |
| Board-level static timing | ADC↔FPGA, memory, parallel buses | Python script under `sim/timing/`, vendor STA | Setup and hold slack |
| Clearance and creepage | > 30 V anywhere, mains, bias supplies | `hv-safety.md` tables, `.kicad_dru` rule | Working voltage, pollution degree, required vs actual |
| Junction temperatures and cooling decision | Every part dissipating > ~0.25 W | `scripts/thermal_check.py`; Elmer + Gmsh when marginal | P, θ_JA used and why, T_j at max ambient, margin |
| Inductor and capacitor stress (SMPS) | Each converter | Datasheet equations, ngspice | Ripple current, saturation margin, RMS cap current, DC-bias derating |
| Hot-loop area and switch-node review | Each converter | `smps-emi.md` §7 checklist | Loop description, measures taken |
| Protection sizing (fuse I²t, TVS clamp, inrush) | Every power input and external interface | Datasheet curves, ngspice | Let-through vs downstream absolute maximum |
| Resistor power and voltage derating | Dividers, shunts, bleeders, HV strings | Hand calculation | P vs rating, V vs rating |
| Tolerance stack (dividers, references, thresholds) | Anything setting a voltage or threshold | ngspice Monte Carlo or worst-case arithmetic | Min / typ / max |
| Test coverage | Always | `dft-bringup.md` §1 | Testpoint per rail and key net; what is not reachable |

## 3. Simulations

| Simulation | Needed when | Tool | Pass criterion (set before running) |
|---|---|---|---|
| Operating point | Every simulated block | ngspice | Bias and power per part within ratings |
| Start-up, soft-start, sequencing | Regulators, multi-rail systems | ngspice transient | No overshoot beyond load absolute maximum; correct order |
| Load step | Regulators | ngspice transient | Deviation within ripple budget |
| Loop stability | Switchers and LDOs with external compensation | ngspice AC (Middlebrook) or vendor average model | Phase margin ≥ 45°, gain margin ≥ 6 dB |
| Filter response, PSRR, noise | Filters, front-ends, references | ngspice AC and `.noise` | Meets the bandwidth / noise requirement |
| Failure cases: output short, input overvoltage, reverse polarity, brown-out, hot-plug, open feedback, loss of a rail | Every power block and protected interface | ngspice transient | No part beyond absolute maximum; recovers or fails safe |
| Monte Carlo and temperature corners | Anything with a tolerance-sensitive output | ngspice (`agauss`, `.temp`) | Spec met across ≥ 100 runs and the temperature range |
| Signal integrity, pre- and post-layout | LVDS, fast CMOS, clocks, any net flagged high-speed | KiCad KIBIS + ngspice with vendor IBIS | Overshoot, ringing, monotonic edges, eye opening vs receiver thresholds |
| SerDes channel | Multi-gigabit links | PyIBIS-AMI (headless), PyBERT (GUI) | Eye at target BER |
| EM structure (via, connector launch, antenna feed) | Only the critical few | openEMS + gerber2ems | Return loss / impedance within target |
| Thermal FEM | When the hand estimate has < 20 °C margin | Elmer + Gmsh from the STEP export | T_j and board hot spots at max ambient |

## 4. Tools and how they are installed
`install.sh` sets up the Python side (ngspice bindings, numpy/scipy/matplotlib,
PyIBIS-AMI, kicad-python) in its own environment and reports the rest;
`install.sh --system-tools` also installs ngspice, Gmsh and gerbv where a package
manager allows it without administrator rights. Elmer and openEMS have no simple
package on every system; `install-quickstart.md` has the commands. The environment's
location is in `~/.config/pcb-design/krt.env` as `PCB_TOOLS_BIN`; put it first on
`PATH` before running any script from this skill.

If a tool is missing, say which checks cannot be run and ask the user whether to
install it. Do not substitute a rougher method silently and do not skip the row.
