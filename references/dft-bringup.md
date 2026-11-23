# Design for test and bring-up

Testability is designed into the schematic at G2, not added at the end.

## 1. Testpoints
- ICT (bed-of-nails): 1.0 mm pads (0.9 mm min), 1.27–2.54 mm centre spacing, one side
  (bottom preferred), one per net for full ICT coverage, ≥ 1–2 mm from tall parts.
- Flying probe: down to ≈ 0.5 mm pads; can use vias/pads on both sides.
- Bench bring-up: loop/hook testpoints (e.g. Keystone 5000-series) for GND and main
  rails so a scope ground clip can attach.
- Always testpoint: every power rail + GND, reset, clocks, PG signals, key data/bias
  nodes, HV monitor (through divider), preamp outputs, threshold DAC outputs.
- High-speed pairs: avoid stubs; if needed, inline pads symmetric on both lines, or a
  connector/test coupon instead.
- Label every testpoint on silkscreen with its net name (short form).

## 2. Visibility
- LEDs: power-good per main rail (or one per rail group), MCU heartbeat/user LED, link
  status, HV-ON, fault. Size resistors for ~1–2 mA (bright enough with modern LEDs).
- DNP-able LED footprints if power budget is tight.

## 3. Isolation and measurement
- 0 Ω links or solder jumpers (KiCad 10 jumper support) between regulator outputs and
  loads, and between sub-blocks.
- Current-sense resistor footprints (or 0 Ω placeholders) on key rails; Kelvin pads.
- Option footprints (DNP) for filters, snubbers, terminations, pull resistors that may
  need tuning.

## 4. MCU / FPGA / SoC
- Reset button (with RC/supervisor) and, when relevant, a power-cycle method.
- Boot options: strap resistors + button/jumper for each boot mode (STM32 BOOT0,
  ESP32 IO0/EN, RP2040 BOOTSEL, i.MX boot pins, FPGA mode pins). Document the strap
  table on the schematic.
- At least two programming paths: SWD/JTAG header (Tag-Connect TC2030 or 1.27 mm
  10-pin Cortex) **and** USB DFU/UART bootloader.
- UART debug console header (3.3 V TTL, with GND).
- JTAG chain access for boundary scan on BGA boards; FPGA config flash programming
  path.
- Spare GPIOs to a header/testpoints for debug signals.

## 5. Production / functional test hooks
- Unique ID/serial: QR/barcode on silkscreen (KiCad 10) or label area.
- Self-test firmware plan: rails via ADC, loopbacks on interfaces.
- Programming fixture compatibility: pogo-pin pads on a grid.

## 6. Bring-up procedure (generate `bringup.md` at G9)
1. Visual inspection (orientation, bridges, missing parts).
2. Rail-to-GND resistance on every rail (record expected values).
3. First power-up with a current-limited bench supply, loads isolated via jumpers.
4. Check each rail voltage, ripple, sequencing (scope on PG/EN).
5. Close jumpers block by block; record currents.
6. Clocks present and correct frequency.
7. Program MCU/FPGA; heartbeat LED.
8. Interface loopbacks / functional tests.
9. HV stage last, with current limit, after LV stages work.
10. Thermal check (IR camera or thermocouple) at max load after 30 min.
