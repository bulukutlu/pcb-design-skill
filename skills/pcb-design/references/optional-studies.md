# Optional studies: offer them, do not assume them

These are studies the workflow can do but does not do by default, because they take
time, need extra tools or only matter for some boards. The user may not know they are
possible, so **offer the list**; do not wait to be asked and do not run one unasked.

## When and how to offer
- **At G0**, after the requirements table: show the table below as a multi-select
  question (group it if the question tool limits options), with one line per study and
  the rough effort. Pre-mark the ones the requirements already point to (see "Offer
  when") and say why.
- **Again at G8**, offering only studies that became relevant since (a marginal thermal
  estimate, a part with one source, a net that turned out to be fast).
- Record the answer in `docs/design-notes.md`: chosen, declined, and the date. Declined
  studies are listed in the design report as "not requested", so a reader knows they
  were not done.
- Each chosen study gets its own section in the design report, led by its figure.

## The list

| Study | What it answers | Offer when | Effort | Tool | Output |
|---|---|---|---|---|---|
| 3D thermal simulation | Temperatures across the board and parts, with real copper and airflow assumptions | Any part within 20 °C of its limit on the hand estimate; sealed enclosure; vacuum; no airflow | Hours | STEP export, Gmsh, Elmer | Temperature map image, hot-spot table |
| Alternate parts search | Is there a cheaper, better-stocked or second-source equivalent for each line? | Always worth offering; pre-mark for single-source or long-lead parts | 1 to 3 h with web access | Distributor searches from `scripts/bom_sources.py`, datasheet comparison | Table: line, current part, alternates, price and stock, what differs |
| Cost breakdown and optimisation | Cost per board at each quantity; which choices drive it (layers, vias, finish, assembly sides, part classes) | Budget is tight or quantity is large | 1 to 2 h | Fab and assembler quote pages | Cost table and chart; list of savings with their trade-offs |
| Material budget scan | Radiation length (X/X0) map of the board for detector modules: where the material is and how much | Tracking detectors, anything in a beam or in front of a calorimeter | Half a day | Stackup, copper coverage per layer, component masses; Python map | X/X0 map image, average and peak, contribution per material |
| Magnetic field compatibility | Will the board work and stay in place in a strong magnetic field? | Inside or near a magnet (detector solenoid, MRI, accelerator) | 2 to 4 h | Part-by-part review | Table of ferromagnetic or field-sensitive parts (ferrite inductors and beads, transformers, relays, nickel barriers and ENIG, steel stiffeners and shields, some connectors) with replacement or orientation; force and saturation notes |
| Radiation environment compatibility | Will the parts survive the dose and particle flux, and fail safely? | Detectors, accelerators, space, nuclear, medical beams | Half a day to days | Published test data, part-by-part review | Per part: total-dose and single-event data found or missing, latch-up protection, derating; materials (polyimide, halogen-free, connector plastics); what must be irradiation-tested |
| Vacuum and outgassing | Is everything allowed in vacuum? | Vacuum vessels, cryostats, space | 2 to 4 h | Outgassing databases, part review | Table of materials and parts with outgassing data; electrolytics, labels, flux and conformal coat flagged |
| Low-temperature / cryogenic operation | Do the parts and joints work when cold? | Cooled detectors, cryostats | Half a day | Datasheets, published cold data | Per part: characterised range, known cold behaviour (capacitance loss, regulator start-up), CTE and solder-joint risks |
| Full signal-integrity sweep | Eye diagrams and crosstalk for every fast link, post-layout | Multi-gigabit links, long or dense buses, tight margins | Hours to a day | KIBIS + ngspice, PyIBIS-AMI, openEMS for structures | Eye and crosstalk plots per link against thresholds |
| Full PDN analysis | Impedance of every rail with plane and via models; DC drop map | Low-voltage high-current rails, FPGAs, sensitive analogue | Half a day | ngspice / Python; Elmer for DC drop | Impedance plots against target, drop map |
| EMC pre-compliance plan and scan | Likely emission and immunity problems before a test house | Product for sale, long cables, switching converters near I/O | Half a day plus bench time | `emc-precompliance.md`, near-field probes, spectrum analyser | Risk list with layout evidence; measurement plan; plots if measured |
| Reliability and derating audit | Stress on every part against a derating policy; failure rate estimate | Long life, remote or inaccessible installation | Half a day | BOM, operating points from simulation | Stress table with margins; weakest parts; MTBF estimate with its assumptions |
| Failure mode and effects analysis | What happens when each part fails open or short? | Safety functions, interlocks, high voltage, expensive loads | A day | Schematic, simulation of key cases | FMEA table: failure, effect, detection, mitigation |
| Worst-case circuit analysis | Do all thresholds and gains hold over tolerance, temperature and ageing together? | Protection thresholds, precision analogue, interlocks | Half a day | ngspice Monte Carlo and corner runs | Distribution plots with limits |
| Mechanical and vibration check | Resonances, connector strain, heavy-part support | Vehicles, pumps nearby, transport, tall or heavy parts | Hours | STEP, simple FEM or hand estimate | Mounting and support recommendations, first resonance estimate |
| Creepage, clearance and partial-discharge review | Margin on every high-voltage gap, including under parts and inside layers | Above about 200 V, bias supplies, altitude | 2 to 4 h | `hv-safety.md`, DRC custom rules | Annotated layer images with the smallest gaps |
| Production test fixture design | A pogo-pin or bed-of-nails fixture and its program | More than a handful of boards | A day | Testpoint coordinates from the board | Fixture drawing, pin map, test sequence |
| Assembly and rework study | Can it be hand-soldered, reworked and probed? | Hand assembly, prototypes, repairs expected | 1 to 2 h | Placement, 3D view | Problem list: hidden pads, parts too close, heat-sinking pads |
| Second fab and assembler comparison | Does another supplier build it cheaper, faster or with better capability? | Lead time or cost matters | 1 to 2 h | Supplier capability and quote pages | Comparison table with rule differences |

Say plainly when a study depends on information the workflow cannot produce itself, for
example irradiation test data that does not exist for a part, or the field map of a
magnet. Then the output is the list of what is unknown and who could supply it.
