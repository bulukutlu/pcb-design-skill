# pcb-design

Claude Code skills for designing a PCB in KiCad 10 the way a careful hardware
engineer would: requirements first, readable schematics, simulation of failure
cases, fab-driven design rules, constrained placement, routing that keeps the
board's rules, 3D models for every part, and a DRC-graded release.

Placement and routing are done by
[KiCadRoutingTools](https://github.com/drandyhaas/KiCadRoutingTools). This
repository adds the surrounding workflow and nine launchers that make
KiCadRoutingTools' own skills usable from any folder under this workflow's rules.

## What is in it

| Skill | What it does |
|---|---|
| `pcb-design` | The gated workflow G0 to G9, with references and helper scripts |
| `/plan-pcb-placement` | Place by function with fixed / region / free parts; optionally place and route |
| `/plan-pcb-routing` | Analyse a board and build the ordered routing plan; run it on approval |
| `/analyze-power-nets` | Power nets and track widths from datasheets |
| `/find-high-speed-nets` | Speed tiers, impedance-controlled nets, return-via spacing |
| `/identify-diff-pairs` | Differential pairs by pin function; impedance and gap per interface |
| `/recommend-stackup` | Stackup review against impedance targets and fab builds |
| `/recommend-plane-mappings` | Which net goes on which plane layer, and why |
| `/diagnose-routing-failures` | Root cause of nets that did not route |
| `/review-routed-board` | Post-route QA with a pass/fail verdict |

The nine sub-skills are thin launchers. The real instructions ship inside the
KiCadRoutingTools plugin and are read from there, so they follow the plugin's
version. Each launcher adds four rules: work on a copy of the board, keep the
board's design rules (`--escalation board --no-fix-drc-settings`), ask before
putting vias in pads, and grade every result with KiCad's own DRC against the
original project file.

## Install

```bash
git clone <this repository> pcb-design
```

```bash
cd pcb-design && ./install.sh
```

On Windows run `python install.py` instead. The installer:

1. copies every folder under `skills/` into `~/.claude/skills/`;
2. finds KiCadRoutingTools in KiCad's plugin folder;
3. creates a Python environment for the router at
   `~/.local/share/kicad-routing-tools/venv` and installs `requirements.txt` into it;
4. creates a second environment for the calculation and simulation tools at
   `~/.local/share/pcb-design/venv` and installs `requirements-tools.txt` into it;
5. writes `~/.config/pcb-design/krt.env`, which tells the skills where the plugin
   and both environments are;
6. prints a status report.

It does not install KiCad or the KiCadRoutingTools plugin, does not touch KiCad's
bundled Python or your system Python, and never uses `sudo`. Run it again after
updating KiCad or the plugin.

```bash
./install.sh --system-tools
```

`--system-tools` additionally installs ngspice, Gmsh and gerbv. With Homebrew it
runs `brew install` for the ones that are missing; on systems where that would need
administrator rights it prints the command for you to run.

```bash
./install.sh --check
```

`--check` prints the same report and changes nothing. Other options: `--force`
(replace installed skills that differ; the old copy is backed up under
`~/.config/pcb-design/backup/`), `--skip SKILL`, `--krt PATH`, `--venv PATH`,
`--dest DIR`, `--env-only`, `--skills-only`, `--no-tools`, `--with-cad`,
`--tools-venv PATH`, `--zip`.

## Dependencies

| Needed | Why | If it is missing |
|---|---|---|
| Python 3.9+ | Runs the installer and the router's tools | python.org, `brew install python`, or your package manager |
| KiCad 10 with `kicad-cli` | ERC, DRC, exports | kicad.org. On macOS `kicad-cli` is in `/Applications/KiCad/KiCad.app/Contents/MacOS/`; add that folder to `PATH` |
| KiCadRoutingTools 0.23 or newer | Placement and routing | In KiCad: Plugin and Content Manager, install "KiCad Routing Tools", then run `./install.sh` again |
| numpy, scipy, shapely, Pillow | KiCadRoutingTools' Python packages | `./install.sh` installs them into the router environment |

KiCadRoutingTools without the Plugin and Content Manager:

```bash
git clone https://github.com/drandyhaas/KiCadRoutingTools.git && cd KiCadRoutingTools && python3 build_router.py
```

```bash
./install.sh --krt /path/to/KiCadRoutingTools
```

`build_router.py` downloads the prebuilt router for your operating system, or
builds it with Rust if no prebuilt one matches.

The router environment by hand, if you prefer not to run the installer:

```bash
python3 -m venv ~/.local/share/kicad-routing-tools/venv
```

```bash
~/.local/share/kicad-routing-tools/venv/bin/pip install -r requirements.txt
```

Then create `~/.config/pcb-design/krt.env` with two lines, `KRT_ROOT=` (the
KiCadRoutingTools folder) and `KRT_BIN=` (the environment's `bin` folder, `Scripts`
on Windows).

Why a separate environment: KiCad's bundled Python is meant for KiCad's own plugins
and, on macOS, ships without numpy, so KiCadRoutingTools' command-line tools do not
run under it.

### Calculation and simulation tools

The workflow ends with a design report
([design-report.md](skills/pcb-design/references/design-report.md)) that lists every
required calculation and simulation with its tool. A check whose tool is missing is
reported as not run, so install what your board needs:

| Tool | Used for | Installed by |
|---|---|---|
| numpy, scipy, matplotlib | PDN impedance, timing, tolerance scripts, plots | `./install.sh` |
| PySpice | Driving ngspice from Python | `./install.sh` |
| pyibis-ami | SerDes IBIS-AMI models | `./install.sh` |
| kicad-python | KiCad IPC API | `./install.sh` |
| ngspice | SPICE: nominal, failure cases, Monte Carlo, PDN sweeps | `./install.sh --system-tools`, or `brew install ngspice` / `sudo apt install ngspice` |
| Gmsh | Meshing for thermal FEM | `./install.sh --system-tools`, or `brew install gmsh` / `sudo apt install gmsh` |
| gerbv | Checking gerbers before ordering | `./install.sh --system-tools`, or `brew install gerbv` / `sudo apt install gerbv` |
| CadQuery | Recreating a 3D STEP model from a datasheet drawing | `./install.sh --with-cad` (several hundred MB) |
| Elmer | Thermal FEM solver, only when the hand estimate is marginal | By hand, see below |
| openEMS + gerber2ems | EM simulation of vias and launches | By hand, see below |
| KiBot, KiKit | Fab outputs, panelisation | By hand, see below |

KiCad's own Calculator and its embedded ngspice (with KIBIS for IBIS models) come
with KiCad. Per-OS commands for the by-hand tools are in
[install-quickstart.md](skills/pcb-design/references/install-quickstart.md).

## Use

Start Claude Code in your KiCad project and ask for what you need, or call a
sub-skill with the absolute path of a board:

```
/plan-pcb-routing /absolute/path/to/board.kicad_pcb
```

The skills copy the board to a work folder before changing anything. A board of a
few hundred nets takes 10 to 20 minutes to route.

## As a Claude plugin

The repository is also a plugin (`.claude-plugin/plugin.json` plus `skills/`).

```bash
./install.sh --zip
```

That writes `dist/pcb-design.zip` for upload. Skills installed that way cannot run
an installer, so each machine still needs the router environment once:

```bash
./install.sh --env-only
```

Use one method per machine. Installing both ways gives you every skill twice.

## What was measured

One real 6-layer board, 434 footprints, 250 signal nets stripped and re-routed on a
copy, graded by KiCad DRC against the original project rules. Plain routing step
only, one run each.

| Run | Nets routed | DRC errors | Unconnected |
|---|---|---|---|
| Hand layout | 250/250 | 0 | 0 |
| KiCadRoutingTools, stock defaults | 250/250 | 270 | 0 |
| KiCadRoutingTools, `--escalation board --no-fix-drc-settings` | 244/250 | 0 | 6 |

The defaults reach 100 % by making tracks, vias and clearances smaller than the
board allows. That is why the launchers always pass the two options and report open
nets instead.

## Not verified

- The installer was tested on macOS (Apple silicon) with Homebrew only. The Linux
  and Windows plugin locations in `install.py` are from KiCad's documentation, not
  from a run, and the `apt` / `dnf` commands it prints were not executed.
- The sub-skills were checked to load and to start KiCadRoutingTools' tools. None
  has been run through a complete placement or routing job under these launchers.
- The launchers were written against KiCadRoutingTools 0.23.7.

## Credits

Placement, routing and the instructions the nine sub-skills load are from
[KiCadRoutingTools](https://github.com/drandyhaas/KiCadRoutingTools) by Andy Haas
and contributors (MIT). This repository does not copy that code or those
instructions; it points at the installed plugin.
