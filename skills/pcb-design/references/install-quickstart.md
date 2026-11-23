# Quick start: install the toolchain

Check versions after install: `kicad-cli version`, `ngspice --version`, `kibot --version`,
`kikit --version`, `python -c "import kipy; print(kipy.__version__)"`.

## Fast path
From a clone of this repository:
```bash
./install.sh            # installs the skills, finds KiCadRoutingTools, builds its Python environment
./install.sh --check    # reports what is present and what is missing, changes nothing
```
`install.sh` needs only `python3` (3.9 or newer) and network access to PyPI. It does
not install KiCad or the KiCadRoutingTools plugin; it tells you if they are missing.
What it sets up, and how to do each step by hand, is in the repository `README.md`.

## Key pitfall: three Pythons
- KiCad's bundled Python runs SWIG action plugins. Do not pip-install into it by hand;
  PCM handles plugin dependencies (IPC plugins get their own venv automatically). On
  macOS it ships **without numpy**, so KiCadRoutingTools' command-line tools do not run
  under it.
- The router's Python: a venv holding numpy, scipy, shapely and Pillow
  (`requirements.txt`), created by `install.sh` at
  `~/.local/share/kicad-routing-tools/venv`. The sub-skills put it first on `PATH`.
- Your own Python (venv/pipx) runs kicad-python (IPC), KiBot, KiKit, PyIBIS-AMI,
  gerber2ems, scripts (`requirements-tools.txt`).
- The IPC API needs KiCad running with Preferences → Plugins → "Enable KiCad API" on.

## Linux (Ubuntu / Debian)
```bash
# KiCad 10 (includes kicad-cli, libngspice, libraries)
sudo add-apt-repository ppa:kicad/kicad-10.0-releases && sudo apt update
sudo apt install kicad
# Simulation, viewers, Java (Freerouting fallback needs Java 25 — Adoptium if missing)
sudo apt install ngspice gerbv gmsh pipx python3-venv
# Output / panelisation tools (system Python via pipx)
pipx install kibot --system-site-packages --pip-args="--no-compile"
pipx install kikit
# Python venv for agent scripts
python3 -m venv ~/venvs/pcb && source ~/venvs/pcb/bin/activate
pip install kicad-python numpy matplotlib PySpice pyibis-ami
pip install pipbert        # PyBERT (GUI), optional
# Elmer FEM (thermal)
sudo apt-add-repository ppa:elmer-csc-ubuntu/elmer-csc-ppa && sudo apt install elmerfem-csc
# openEMS (EM/impedance), optional
git clone --recursive https://github.com/thliebig/openEMS-Project.git
cd openEMS-Project && ./update_openEMS.sh ~/opt/openEMS --python
pip install git+https://github.com/antmicro/gerber2ems.git
```

## macOS
```bash
brew install --cask kicad
brew install ngspice gmsh gerbv pipx
pipx install kibot && pipx install kikit
python3 -m venv ~/venvs/pcb && source ~/venvs/pcb/bin/activate
pip install kicad-python numpy matplotlib PySpice pyibis-ami
```
- KiCad's Python: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/...`
- Elmer: no official binaries — Homebrew tap or build from source. openEMS: build with
  Homebrew deps (`install_deps.sh`).
- Disable App Nap for KiCad during long autoroutes:
  `defaults write org.kicad.kicad NSAppSleepDisabled -bool YES` (bundle id may differ;
  check with `osascript -e 'id of app "KiCad"'`).

## Windows
- `winget install KiCad.KiCad` (or installer from kicad.org). KiCad Python:
  `C:\Program Files\KiCad\10.0\bin\python.exe` (SWIG plugins only).
- System Python 3.11+ for kicad-python and scripts; ngspice from ngspice.sourceforge.io
  (KiCad already embeds the shared library).
- KiBot works best via WSL2 or Docker.
- Elmer installer (set `ELMER_HOME`); openEMS prebuilt zip (set `OPENEMS_INSTALL_PATH`).

## KiCad plugins (Plugin and Content Manager, inside KiCad)
- **KiCad Routing Tools** (drandyhaas/KiCadRoutingTools) — project router and placer.
  Install it here, then run `install.sh`. Without PCM: `git clone` the repository,
  run `python3 build_router.py` in it (downloads the prebuilt router for your OS), and
  pass its path with `./install.sh --krt /path/to/KiCadRoutingTools`.
- Freerouting (fallback), Interactive HTML BOM, KiKit (GUI part), Fabrication Toolkit or
  kicad-jlcpcb-tools, teardrops are native in KiCad 10.

## Claude Code integration
- `./install.sh` copies every folder under `skills/` into `~/.claude/skills/`
  (user-wide). For one project only, copy them into `<project>/.claude/skills/` and run
  `./install.sh --env-only`.
- Add a KiCad MCP server, e.g.:
  `pipx install kicad-mcp-pro && kicad-mcp-pro setup --agent claude-code`
  or follow Konnect-EDA's README; generic form: `claude mcp add <name> -- <launch cmd>`.
- Allow Claude Code to run `kicad-cli`, `ngspice`, `kibot`, `kikit`, `python` in the
  project (permissions in `.claude/settings.json`).

## Docker / CI
`docker run --rm -v $PWD:/work -w /work ghcr.io/inti-cmnb/kicad10_auto:latest kibot -c fab.kibot.yaml`
(the image pins a KiCad patch version; match it to your desktop version).

## Smoke test
```bash
kicad-cli sch erc --exit-code-violations myboard.kicad_sch
kicad-cli pcb drc --exit-code-violations --format json -o drc.json myboard.kicad_pcb
python ~/.claude/skills/pcb-design/scripts/drc_summary.py drc.json
python ~/.claude/skills/pcb-design/scripts/sch_lint.py myboard.kicad_sch
echo "v1 1 0 1; r1 1 0 1k; .op; .end" > /tmp/t.cir && ngspice -b /tmp/t.cir
```
