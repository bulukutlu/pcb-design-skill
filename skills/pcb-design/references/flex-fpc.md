# Flex and rigid-flex circuits (FPC)

Read this whenever the board, or part of it, is flexible. Numbers marked *typical* vary
by fab and material: confirm them with the chosen fab's flex capability page and record
the source, as for any other rule.

## 1. Ask first
Static (bent once at installation) or dynamic (flexes in use)? Bend radius and angle?
Total thickness at the connector? Which side are the contacts on at each end? Stiffener
material and position? These decide the stackup and cannot be fixed later.

## 2. Stackup and bending
- Minimum bend radius, *typical*: about 6 to 10 times the flex thickness for one or two
  layers bent once; 20 times or more, and rolled-annealed copper, for dynamic flexing.
- In the bend area: no vias, no pads, no stiffener edges, no changes of trace width.
  Traces cross the bend at right angles, evenly spaced.
- Two-layer flex: offset traces on the two sides so they do not stack on top of each
  other (stacked traces act as a beam and crack).
- Use hatched copper instead of solid pours where the circuit must bend; solid copper
  stiffens it and cracks.
- Curved or 45 degree corners with teardrops at every pad and via; no right angles.
- Coverlay openings are coarser than solder mask: give pads larger openings and anchor
  pads with spurs or oversized lands so they do not lift.

## 3. Outline
- Chamfer or radius every concave corner. Where a flap meets the cable body, a 1 x 1 mm
  45 degree chamfer relieves a tear-prone stress concentration and costs nothing in
  clearance, since it adds material.
- Add tear stops (copper or drilled relief) at slits and inside corners.
- Keep copper back from the edge; see the edge-clearance note below.

## 4. ZIF / FFC contact fingers
Constraints measured on a 0.5 mm pitch ZIF finger design (0.2 mm trace, 0.2 mm
clearance, 18 um copper). Most follow from the pad pitch and recur on any similar flex.
- **Vias cap at 0.35 / 0.15 mm.** At 0.5 mm pitch a 0.45 mm via leaves 0.175 mm to its
  neighbour against a 0.2 mm rule; 0.35 mm gives 0.225 mm. This applies on pads, between
  trunk lanes and beside parallel drops alike. Vias on pads must be staggered (alternate
  x or y) or adjacent ones collide.
- **45 degree fan-outs do not fit at 0.5 mm pitch.** Parallel 45 degree lines 0.5 mm apart
  have only 0.354 mm perpendicular separation, 0.154 mm after the trace width: short by
  0.046 mm, and moving vias does not fix it. Use straight drops (0.3 mm clear); the
  resulting staircase of vias is correct.
- **Zones cannot reach into a pad row.** At 0.5 mm pitch the copper between foreign pads
  is entirely consumed by clearance and the fill produces nothing. Bound each zone to
  its own net's pad group instead of flooding across.
- **Zones need `connect_pads yes`.** Default thermal relief cannot form a spoke on a
  0.25 mm pad (0.3 mm default bridge), so zones silently connect nothing.
- **Zones honour `min_copper_edge_clearance`; pads do not.** A 0.5 mm rule pulls the fill
  off the board edge and strands the outermost fingers while pads only warn. On flex,
  fingers sit about 0.125 mm from the edge, so the rule must come down (0.3 mm works if
  the outline gives pins 0.5 mm to the flap sides).
- **Contact areas want discrete fingers.** Pull top-layer pours back to the pad midline
  so the outer half of each pad stays separated.
- Total thickness at the fingers must match the connector (*typical* 0.3 mm for common
  0.5 mm pitch ZIF parts); the stiffener makes up the difference.
- Finger plating: ENIG or hard gold as the connector maker specifies.

## 5. Stiffeners
- **The stiffener goes on the face opposite the contacts.** Contacts on F.Cu means the
  stiffener is drawn on B.Adhes. Rename only that layer's user-facing name to
  `B.Stiffener`; the canonical `B.Adhes` must stay, and it exports as a gerber.
- Size it from the flap tip to 1 to 2 mm past the fingers' inner edge.
- Under components and connectors on flex, add a stiffener (FR4 or polyimide; steel for
  thin, flat support) and state material and thickness in the fab drawing.
- A stiffener edge is a stress line: keep vias and pads away from it and never place it
  in a bend.

## 6. Checks specific to flex
- Run DRC with `--refill-zones` and check every finger is connected; stranded fingers
  from the edge-clearance rule do not always show as errors.
- Mating check (`verification.md` §3) for both ends: contact side and pin order. A flex
  with contacts on the same side at both ends reverses the pin order.
- Fab drawing: stackup with materials and thicknesses, stiffener map, bend lines and
  radius, finger plating, coverlay openings, and whether silkscreen is wanted.
- 3D check: export STEP and confirm the bend fits the assembly; KiCad shows the flex
  flat, so state bend positions on the mechanical drawing.
