# Placement, routability and the routing loop

Why this file exists: agents tend to fix a placement once, then fight congestion by
adding vias, layers or shrinking rules. Experienced designers spend most of the layout
time on placement — routing quality follows placement quality. Even AI-routing vendors
state that placement is the hardest part to automate. So placement must stay *open*
until routing proves it works.

## 1. Order of placement
1. **Mechanical constraints** — board outline (Edge.Cuts), mounting holes (H), connectors
   at their fixed positions, keep-outs, height zones, enclosure features. Lock them.
2. **Floorplan by function** — one region per schematic sheet/block. Order along the
   board: power entry → protection → regulators → digital → analog → sensor/front-end.
   Keep switchers far from (and on the opposite edge to) sensitive inputs. HV area
   isolated, ideally in a corner with a slot/keep-out boundary.
3. **Critical parts and their satellites**:
   - SMPS: input HF cap, switch/IC, inductor, output caps — hot loop first.
   - Decoupling at IC pins (smallest value closest), crystals ≤ 5 mm from pins.
   - Termination resistors at the receiver (parallel) or driver (series).
   - ESD/TVS directly at the connector.
   - AC-coupling caps where the interface guide says.
4. **Orientation pass** — rotate/mirror ICs and connectors so ratsnest lines are short
   and do not cross. Change connector pinouts (if you own both ends), swap gates/pins
   (KiCad 10 pin/gate swap), reassign FPGA/MCU pins (update the schematic).
5. **BGA/fine-pitch fanout plan** — dogbone vs via-in-pad, escape layers, before final
   placement of neighbours.
6. **Repeated channels** — Design Blocks / multi-channel replication so all channels are
   identical (matters for matched analog performance).
7. **DFT/DFM items** — testpoints reachable from one side, fiducials, LEDs visible,
   buttons and connectors accessible, labels readable.

## 2. Routability estimate (before routing)
Do this numerically, not by feel:
- **Ratsnest crossings**: count crossings per region (script with the IPC API or
  estimate from the board file). Many crossings in one region → reorient or regroup.
- **Channel capacity**: for each channel between obstacles,
  `tracks_per_layer = floor((channel_width − clearance) / (track_width + clearance))`;
  multiply by usable routing layers. Compare with the number of nets that must pass.
- **Flag any channel above ~70 % demand.** Fix placement there before routing.
- **Pin density sanity**: total pins / board area. Rough guide for 0.15/0.15 mm rules:
  2 signal layers handle simple boards; dense BGA (≥ 0.8 mm pitch, many I/O) usually
  needs 4–6 layers for escape *and* reference planes. Use this only as a first guess.

## 3. Routing order
1. Power hot loops and high-current paths (wide copper, pours, via arrays).
2. Differential pairs (KiCad diff-pair router, with net-class widths/gaps from the fab
   impedance calculator), then length/time tuning.
3. Clocks and other critical single-ended nets (reference plane continuous, away from
   edges).
4. HV nets (HV net class, custom clearance rule).
5. Sensitive analog (guarding, away from digital and switch nodes).
6. Everything else → autorouter.

## 4. Autorouting (Autorouter plugin, hulryung/kicad-autorouter)
- Install from KiCad's Plugin and Content Manager; it supports KiCad 9/10, reads net
  classes and `.kicad_dru` custom rules (including HV isolation from v0.5.7), and has a
  wall-clock limit (v0.5.8). It is a testing-grade release — review its output.
- **Lock** all manually routed tracks before running it, so it cannot rip them up.
- Give it only the non-critical remainder and a timeout.
- It uses the SWIG action-plugin API, so it runs inside the KiCad GUI. An agent with only
  shell access must ask the user to run it, or use the IPC/MCP route, or Freerouting
  2.5's IPC mode as fallback.
- After it runs, always: `kicad-cli pcb drc` and the metrics below.

## 5. The loop (mandatory)
```
iteration = 0
loop:
    route critical nets (manual / constrained)
    autoroute remainder (timeout)
    metrics = completion %, unrouted count, vias per net, total length / Manhattan,
              DRC violations, return-path issues (plane crossings)
    if completion == 100% and metrics within thresholds: break
    diagnose: which region, which nets block, why (crossing, wrong side, pin order)
    FIX PLACEMENT FIRST:
        rotate / mirror / move parts, move to other side,
        swap pins/gates, change connector pinout, reassign MCU/FPGA pins,
        move vias out of channels, regroup clusters
    rip up affected non-critical routes; iteration += 1
    log iteration in design-notes.md (what blocked, what changed, new metrics)
```
Suggested thresholds (tune per board): completion 100 %; avg vias/net ≤ 2 for
non-critical nets; routed length ≤ 1.5× Manhattan; zero DRC errors; no critical net
crossing a plane split.

## 6. When adding a layer is justified
Add a layer only when **all** hold, and write the reasoning in design-notes.md:
1. At least two placement iterations were tried and logged, and they failed.
2. The channel-capacity estimate shows demand > capacity even with best placement.
3. The extra layer also helps SI/EMC (e.g. another reference plane, stripline for fast
   nets) — or there is no other way to escape a BGA.
4. The cost/lead-time impact was checked on the fab price table and accepted by the user.
Never shrink below the fab preset or go to finer, more expensive rules to "make it route"
without the same justification.

## 7. Finishing
- Pour planes; check islands and thin necks; stitch ground pours (≤ λ/20 of highest
  frequency of concern), stitch along edges.
- GND stitching via next to each signal via that changes reference layer.
- Teardrops (native in KiCad 10) on small pads/vias.
- Silkscreen: ref-des readable, not on pads, polarity marks, pin 1, board name/rev/date,
  HV warning, QR/barcode (KiCad 10) for serial/rev if useful.
- Final DRC with schematic parity.
