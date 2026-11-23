# High voltage, creepage, clearance, isolation (incl. detector bias)

Important distinction: **IPC-2221B is a design (functional) standard, not a safety
standard.** For anything touching mains or user-accessible circuits, work from the
end-product safety standard: EN/IEC 62368-1 (ICT/AV) or EN/IEC 61010-1 (lab and
measurement equipment), with IEC 60664-1 insulation coordination behind them.

## 1. Functional clearance: IPC-2221B Table 6-1 (DC or AC peak between conductors)
| Voltage | B1 internal | B2 external uncoated (≤3050 m) | B4 external, permanent polymer coating |
|---|---|---|---|
| 0–15 V | 0.05 mm | 0.1 mm | 0.05 mm |
| 16–30 V | 0.05 mm | 0.1 mm | 0.05 mm |
| 31–50 V | 0.1 mm | 0.6 mm | 0.13 mm |
| 51–100 V | 0.1 mm | 0.6 mm | 0.13 mm |
| 101–150 V | 0.2 mm | 0.6 mm | 0.4 mm |
| 151–170 V | 0.2 mm | 1.25 mm | 0.4 mm |
| 171–250 V | 0.2 mm | 1.25 mm | 0.4 mm |
| 251–300 V | 0.2 mm | 1.25 mm | 0.4 mm |
| 301–500 V | 0.25 mm | 2.5 mm | 0.8 mm |
| > 500 V | +0.0025 mm/V | +0.005 mm/V | +0.00305 mm/V |

- Example: uncoated external 1000 V → 2.5 + 500 × 0.005 = **5.0 mm**.
- Solder mask does **not** count as B4 coating.
- One JLCPCB blog lists B2 151–300 V as 0.25 mm — conflicts with all other sources;
  use 1.25 mm. Confirm against a purchased IPC-2221B copy before relying on edge cases.
- Add margin (×1.2–1.5) for fab tolerance and contamination in real labs.

## 2. Safety creepage / clearance: IEC 60664-1 basis
Inputs to record in design-notes.md for each barrier: working voltage (RMS and peak),
overvoltage category (OVC I–IV), pollution degree (PD), material group (CTI),
insulation class (functional / basic / supplementary / reinforced), altitude.
- Material group by CTI: I ≥ 600, II 400–600, IIIa 175–400, IIIb 100–175.
  Standard FR-4 ≈ IIIa; if CTI unspecified, assume IIIb.
- Pollution degree: PD1 sealed/coated, PD2 normal indoor lab (occasional
  condensation), PD3 industrial / conductive pollution.
- Indicative creepage PD2, group IIIa (equipment column, AtlasPCB transcription):
  ≤ 50 V 0.6 mm (≈1.2 mm for IIIb), 250 V 2.5 mm, 400 V 4.0 mm, 600 V 6.3 mm,
  1000 V 10 mm. Printed-wiring-material columns allow less (e.g. 1.4 mm for 300 V basic
  on PCB at PD2 per NI). **Use the end-product standard's tables for final values.**
- Reinforced/double insulation → double the basic values.
- Clearance above 2000 m: multiply by altitude factor (e.g. 1.48 at 5000 m).
- Creepage is never less than clearance.

## 3. Slots and cutouts
- A slot interrupts a creepage path only if wider than X: 0.25 mm (PD1), **1.0 mm
  (PD2)**, 1.5 mm (PD3). Draw slots on Edge.Cuts (milled), not silkscreen.
- Slots under optocouplers, isolators, transformers, relays where the body spacing is
  less than the required creepage on the board.

## 4. KiCad implementation
- HV net class (e.g. `HV`) with its own clearance; custom rules:
```
(version 1)
(rule "HV to anything, outer layers"
  (layer outer)
  (condition "A.NetClass == 'HV' && B.NetClass != 'HV'")
  (constraint clearance (min 5.0mm)))
(rule "HV to anything, inner layers"
  (layer inner)
  (condition "A.NetClass == 'HV' && B.NetClass != 'HV'")
  (constraint clearance (min 1.5mm)))
(rule "HV creepage across isolation barrier"
  (condition "A.NetClass == 'HV' && B.NetClass != 'HV'")
  (constraint creepage (min 6.0mm)))
(rule "HV edge clearance"
  (condition "A.NetClass == 'HV'")
  (constraint edge_clearance (min 3.0mm)))
```
  Values are examples — compute from §1/§2 for the real voltage. KiCad 9+ supports a
  `creepage` constraint; verify DRC reports it.
- Rule areas / keep-outs to stop pours from flooding the HV region.
- Remove pour around HV routes; keep HV on one layer where possible; avoid HV vias next
  to low-voltage vias in inner layers.

## 5. Detector bias supplies (silicon sensors 100s V, SiPM/MCP/PMT up to kV)
- HV-rated parts: check every capacitor/resistor voltage rating (and resistor
  *element* voltage rating); use series strings for dividers and ladders; HV caps with
  derating ≥ 1.5–2×.
- Current limiting at the HV output (series resistor or controller limit); simulate a
  short (simulation-playbook.md).
- Bleeder resistor so HV decays below 60 V DC within a defined time (state the time;
  ≤ 1–5 s is a common target) after power-off; verify RC.
- Filter (RC) close to the sensor; guard ring at bias-return potential around
  high-impedance nodes and sensor inputs; clean surfaces (no flux residue — leakage).
- HV monitor through a high-ratio divider to a testpoint/ADC; LED "HV ON" indicator.
- Silkscreen: HV warning symbol and voltage; outline the HV area.
- Conformal coat if relying on B4 values; specify the coating on the fab/assembly drawing.
- HV connectors (SHV, LEMO HV, etc.) with proper ratings; no SMA/BNC for HV.

## 6. Isolation barriers and Y-caps
- Y-capacitors across a barrier must be Y-rated (Y1 for reinforced). Their leakage
  counts toward touch-current limits.
- Isolators/optos: package creepage must meet the requirement; extend with slots.
- No copper on any layer bridging the barrier; check inner layers and pours.

## 7. Lab safety context
- Inside CERN, CERN's HSE electrical-safety rules apply; contact the local HSE unit for
  HV equipment. Lab instruments in general: design to EN 61010-1.
