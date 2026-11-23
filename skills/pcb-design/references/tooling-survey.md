# Tooling survey (researched Nov 2026 — versions move fast)

## 1. KiCad 10
- 10.0.0 released 20 Mar 2026; current patch 10.0.8 (30 Oct 2026).
- New and useful for this workflow: Design Variants, hop-over arcs, jumper support,
  schematic grouping, graphical DRC rule editor, time-domain track tuning, PCB Design
  Blocks, inner-layer zones/keep-outs, native pin/gate swap, lasso select,
  barcodes/QR, 3D PDF, Allegro/PADS/gEDA importers, larger libraries (STEP models).
- **No built-in full-board autorouter**; "Attempt Finish Selected (Autoroute)",
  Shift+F, finishes selected connections only.

## 2. Automation interfaces
| Interface | Use | Notes |
|---|---|---|
| `kicad-cli` | ERC, DRC, exports (gerber, drill, pos, BOM, netlist, STEP, PDF, SVG), render, jobsets | Headless; first choice |
| IPC API (`kicad-python`, `kipy`) | Live edits in a running PCB editor | Enable: Preferences → Plugins → Enable KiCad API. Schematic access and headless api-server planned for KiCad 11 |
| SWIG `pcbnew` | Legacy action plugins | Deprecated since 9.0, removal planned for 11.0 — no new code |
| S-expression editing (kicad-skip, kicad-sch-api) | Schematic generation/editing | KiCad closed or reload after; keep formatting valid |

## 3. Routing
| Option | Notes |
|---|---|
| **KiCadRoutingTools** (drandyhaas/KiCadRoutingTools), project choice | PCM plugin, MIT, v0.23.7 (Nov 2026). Rust grid router with a Python CLI: constrained placement (annealing, locks, edge seating, zones), QFN/BGA fan-out, differential pairs, impedance-derived widths, power-net widths, planes, length matching, rip-up, failure diagnosis, and its own Claude Code skills. Headless. Needs numpy, scipy, shapely, Pillow in a Python of its own (`install.sh`). Must be run with `--escalation board --no-fix-drc-settings` or it shrinks features below the board's rules. |
| Autorouter plugin (hulryung/kicad-autorouter), earlier choice | PCM plugin, MIT, v0.5.8 (18 Nov 2026), testing release. Grid router + Freerouting engine; reads `.kicad_dru` incl. HV isolation; wall-clock cap; optional AI assistant. SWIG action plugin → GUI only; will need an IPC port for KiCad 11. On macOS disable App Nap (3–5× slowdown otherwise). |
| Freerouting 2.5.0 (fallback) | IPC mode for KiCad 10 (separate process, no UI freeze), DSN/SES fallback; needs Java 25 currently; own MCP server |
| Quilter, DeepPCB, Cherry Blossom, ProtoFlow | Commercial cloud; vendor benchmarks only |

## 4. Companion tools
| Tool | Purpose |
|---|---|
| KiBot (1.9.x) | Output generation + CI from one YAML (gerbers, BOM, PDFs, STEP, iBoM, renders, DRC/ERC) |
| KiKit | Panelisation, fab presets (JLC etc.), fab packages |
| Interactive HTML BOM | Assembly/bring-up aid |
| kicad-jlcpcb-tools / Fabrication Toolkit | JLC parts lookup, CPL/BOM formats |
| KiCost | Price/availability from distributors |
| KiRi / kicad-diff | Visual diffs between git revisions (review) |
| KiCad StepUp (FreeCAD) | Mechanical co-design |
| easyeda2kicad, SnapEDA, Ultra Librarian | Part imports — always verify vs datasheet |
| SKiDL, atopile, circuit-synth, tscircuit | Code-first circuits (netlists; still need a readable schematic) |
| gerbv / KiCad GerbView | Gerber check |
| Docker `ghcr.io/inti-cmnb/kicad10_auto` | CI image with KiCad 10, KiBot, KiKit (pins a patch version) |

## 5. Simulation / validation
ngspice (embedded + CLI), KIBIS, PyBERT, PyIBIS-AMI, openEMS, gerber2ems,
kicad-si-simulation-wrapper, Elmer FEM + Gmsh, Saturn PCB Toolkit (Windows, free
calculators), KiCad calculator.

## 6. Agent / MCP landscape
| Project | Notes |
|---|---|
| mixelpixx KiCAD-MCP-Server → Konnect-EDA | Rust KiCad 10 plugin, ~228 tools over IPC + kicad-cli, bundled Claude/Codex skills |
| oaslananka kicad-mcp-pro | "Human-gated release", ships a design-review SKILL.md; `kicad-mcp-pro setup --agent claude-code`; JLCPCB walkthrough (Oct 2026) |
| Seeed-Studio kicad-mcp-server | Analysis, pin tracing |
| blwfish kicad-mcp | Aimed at non-EEs; recommends subagents |
| greg3001 kicad-claude-mcp | ~105 tools, direct file edits |
| Akhil-Chaturvedi KiCad-EDA-MCP | Cascading quality gates |
| Flux copilot, Siemens Fuse | Commercial |

Ideas taken into this skill: quality gates with checkpoints, human approval before
release, IPC for undo-aware edits, review checklists.
Known failure modes: SWIG dependence, file edits leaving KiCad state stale,
netlist-only schematics, poor agent routing quality (KiCad forum).

## 7. Recommended minimal stack for this pipeline
KiCad 10.0.x + kicad-cli, ngspice, KiCadRoutingTools (+ Freerouting fallback), KiBot,
KiKit, Interactive HTML BOM, kicad-python, one KiCad MCP server (Konnect-EDA or
kicad-mcp-pro), Python venv with numpy/matplotlib/PySpice, gerbv. Add openEMS,
gerber2ems, Elmer+Gmsh, PyIBIS-AMI when the board needs those checks.
