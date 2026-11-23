# Sources (annotated)

## Books
- Henry Ott, *Electromagnetic Compatibility Engineering* (Wiley 2009) — grounding, decoupling, mixed-signal partitioning; critique of split grounds and the 20H rule.
- Eric Bogatin, *Signal and Power Integrity – Simplified* (3rd ed.) — rules of thumb; https://www.colorado.edu/faculty/bogatin/rules-thumb ; "The Critical Length of a Transmission Line" https://www.polarinstruments.com/support/cits/Critical_length.pdf
- Howard Johnson & Martin Graham, *High-Speed Digital Design: A Handbook of Black Magic*; signalconsulting.com
- Lee Ritchey, *Right the First Time* vols 1–2 — stackups, planes, decoupling myths.
- Mark Montrose, *Printed Circuit Board Design Techniques for EMC Compliance*.
- Keith Armstrong, *EMC Design Techniques for PCBs* (Cherry Clough / EMC Standards).
- Ralph Morrison, *Grounding and Shielding*.
- Würth Elektronik, *Trilogy of Magnetics*.
- Todd Hubing, LearnEMC (Clemson) tutorials — board-edge radiation, split planes.

## Talks / blogs
- Rick Hartley — return paths and stackups talks.
- Phil's Lab (YouTube) — KiCad mixed-signal/SMPS designs. Robert Feranec / Fedevel.
- Altium critical length: https://resources.altium.com/p/key-elements-high-speed-pcb-design
- Sierra Circuits decoupling: https://www.protoexpress.com/blog/decoupling-capacitor-placement-guidelines-pcb-design/
- PCEA High-Speed Constraint Values: https://pcea.net/wp-content/uploads/2024/05/High-Speed-Constraint-Values-v3a-Pfeil.pdf
- 100nF buck layout: https://100nf.com/articles/buck-converter-layout/
- AtlasPCB SI / PDN / creepage guides (vendor blog — secondary).
- nodeloop high-speed cheat sheet: https://nodeloop.org/guides/high-speed-pcb-routing-cheat-sheet/

## Application notes
- TI SLVA494A buck layout: https://www.ti.com/lit/an/slva494a/slva494a.pdf
- TI SLUP432 buck basics: https://www.ti.com/lit/ml/slup432/slup432.pdf
- TI SLVAFJ3 4-switch buck-boost: https://www.ti.com/lit/pdf/slvafj3
- TI SLUA808 charger layout: https://www.ti.com/lit/an/slua808/slua808.pdf
- TI SLUP419/421 clearance & creepage: https://www.ti.com/lit/pdf/slup419 , https://www.ti.com/lit/ml/slup421/slup421.pdf
- ADI MT-031 grounding, MT-101 decoupling.
- AMD/Xilinx UG583, Intel PCB guidelines, USB-IF and HDMI layout guides, MCU hardware design guides (ST AN, NXP, Microchip, Espressif, RP2040).
- NI pollution degree: https://www.ni.com/en/support/documentation/supplemental/22/pollution-degree-rating-for-electrical-equipment.html

## Standards
IPC-2221B, IPC-2152, IPC-7351, IPC-A-610, IPC-2581, IPC-D-356, IPC-9252; IEC 60664-1, IEC/EN 62368-1, IEC/EN 61010-1; EN 55032/55035, EN 61000-3-2/-3-3, EN 61000-4-x, EN 18031-1/-2/-3; IEEE 315, IEC 60617.

## Schematic style
- Graham Sutherland: https://blog.poly.nomial.co.uk/2025-08-10-creating-high-quality-electronics-schematics.html
- Gregor Gross: https://medium.com/@gregorgross/style-guide-for-schematics-if-you-like-your-schematics-to-be-understood-easily-7ed3452346cc
- PCBWay: https://www.pcbway.com/blog/PCB_Design_Tutorial/How_to_make_clear_and_well_organized_schematics.html
- LCSC: https://www.lcsc.com/blog/5-best-practices-for-creating-professional-schematic-drawings/

## Fab / DFM / DFT
- JLCPCB rules: https://jlcpcb.com/blog/pcb-design-rules-best-practices , https://jlcpcb.com/blog/pcb-routing-rules-best-practices
- Capability comparison: https://www.nextpcb.com/blog/pcb-capabilities-comparison-jlcpcb-vs-pcbway-vs-nextpcb
- Eurocircuits, Aisler, Multi-CB, OSH Park, Würth capability pages.
- Testpoints: https://www.pcbcart.com/article/content/test-point-design-ict-fp.html , https://www.queenems.com/blog/pcb-design-for-test-dft-guide/

## Tools
- KiCad 10: https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ ; docs https://docs.kicad.org/10.0/
- SWIG deprecation: https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html
- kicad-python: https://pypi.org/project/kicad-python/
- Autorouter plugin: https://github.com/hulryung/kicad-autorouter
- Freerouting 2.5.0: https://github.com/freerouting/freerouting/releases/tag/v2.5.0
- KiBot: https://kibot.readthedocs.io ; kicad_auto: https://github.com/INTI-CMNB/kicad_auto
- MCP: https://github.com/mixelpixx/KiCAD-MCP-Server , https://github.com/mixelpixx/Konnect , https://github.com/oaslananka/kicad-mcp-pro , https://github.com/Seeed-Studio/kicad-mcp-server , https://github.com/blwfish/kicad-mcp , https://github.com/greg3001/kicad-claude-mcp , https://github.com/Akhil-Chaturvedi/KiCad-EDA-MCP
- PyBERT https://github.com/capn-freako/PyBERT ; PyAMI https://github.com/capn-freako/PyAMI
- openEMS https://docs.openems.de ; gerber2ems https://github.com/antmicro/gerber2ems ; kicad-si-simulation-wrapper https://github.com/antmicro/kicad-si-simulation-wrapper
- Elmer FEM https://github.com/ElmerCSC/elmerfem
- KIBIS example: https://github.com/johonkanen/kicad_ibis_simulation

## EU regulation
- CRA summary: https://digital-strategy.ec.europa.eu/en/policies/cra-summary
- RED/EN 18031: https://www.schutzwerk.com/en/compliance/red/ , https://www.tegmensoft.com.tr/en/guides/en-18031-red
- EUR-Lex texts: 2014/35/EU, 2014/30/EU, 2014/53/EU, 2011/65/EU, 2012/19/EU, 2023/988, 2024/2847, 2022/2380, 2023/1542, 2024/1781.
