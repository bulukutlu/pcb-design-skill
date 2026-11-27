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
   - Radio modules and chip antennas: antenna at a board edge (corner for most chip
     antennas), oriented as in the module datasheet, with the vendor's keep-out free of
     copper, traces, vias and parts **on every layer**, and nothing tall or metal
     (connectors, batteries, enclosure screws, shields) beside it. Copy the vendor's
     reference layout and ground-plane size; the antenna is tuned to it. A module whose
     antenna overhangs the edge must overhang, not sit over copper.
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
6. Everything else → the router (`/plan-pcb-routing`).

## 4. Autorouting (KiCadRoutingTools, drandyhaas/KiCadRoutingTools)
- Install it from KiCad's Plugin and Content Manager ("KiCad Routing Tools"), then run
  this repository's `install.sh` once. It has a command line, so an agent with shell
  access can run it headless; nothing needs the KiCad GUI.
- Drive it through the sub-skills, not bare commands: `/plan-pcb-placement` for
  placement, `/plan-pcb-routing` for the ordered plan (pours → fan-out → differential
  pairs → impedance nets → remaining nets → return vias), `/diagnose-routing-failures`
  when nets stay open, `/review-routed-board` for sign-off.
- **Rule policy.** Always pass `--escalation board --no-fix-drc-settings`. By default
  the router makes tracks, vias and clearances smaller than the board's own minimums to
  reach 100 % and rewrites the output project's DRC settings to match. On a 6-layer,
  250-net test board the defaults gave 250/250 nets with 270 DRC errors against the
  original rules; with the two options, 244/250 and 0 errors.
- **Lock** all manually routed tracks first. It does not rip existing copper unless told
  to (`--rip-existing-nets`), and never rips KiCad-locked copper.
- Work on a copy of the board with its `.kicad_pro` and `.kicad_sch`; never `--overwrite`.
- Vias in pads are allowed unless `--same-net-pad-clearance` is set. Ask the user.
- After it runs, always: `kicad-cli pcb drc --refill-zones --schematic-parity` against
  the original `.kicad_pro`, and the metrics below. Its own "N/N routed" summary is not
  the verdict.
- Do not replace or wrap it with a custom global planner. One was tested (negotiated
  crossing-minimising plan fed into its plan hook): 241/250 against 244/250 without.

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
