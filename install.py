#!/usr/bin/env python3
"""Install the pcb-design skills for Claude Code and set up what they depend on.

    python3 install.py            install skills + router environment
    python3 install.py --check    report what is present / missing; change nothing
    python3 install.py --zip      build dist/pcb-design.zip (a Claude plugin upload)

Needs only Python 3.9+ and, for the router environment, network access to PyPI.
It never installs KiCad or the KiCadRoutingTools plugin and never touches KiCad's
bundled Python; it tells you what is missing and how to get it.
"""
import argparse
import filecmp
import glob
import os
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
PLUGIN_ID = 'com_github_drandyhaas_kicadroutingtools'
ENV_FILE = os.path.join(HOME, '.config', 'pcb-design', 'krt.env')
DEFAULT_VENV = os.path.join(HOME, '.local', 'share', 'kicad-routing-tools', 'venv')
DEFAULT_DEST = os.path.join(HOME, '.claude', 'skills')
WIN = os.name == 'nt'

OK, WARN, MISS = 'ok     ', 'warn   ', 'MISSING'


def say(tag, what, detail=''):
    print('  [%s] %s%s' % (tag, what, ('  ' + detail) if detail else ''))


def version_key(path):
    out = []
    for part in os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))).split('.'):
        out.append(int(part) if part.isdigit() else -1)
    return out


def is_krt(path):
    return bool(path) and os.path.isfile(os.path.join(path, 'py_router', 'route.py'))


def find_krt(explicit=None):
    """KiCadRoutingTools root: --krt, $KRT_ROOT, a previous install, then KiCad's
    Plugin and Content Manager folders (newest KiCad version first)."""
    for cand in (explicit, os.environ.get('KRT_ROOT'), read_env().get('KRT_ROOT')):
        if cand and is_krt(os.path.expanduser(cand)):
            return os.path.abspath(os.path.expanduser(cand))
    roots = [
        os.path.join(HOME, 'Documents', 'KiCad'),                              # macOS, Windows
        os.path.join(HOME, 'OneDrive', 'Documents', 'KiCad'),                  # Windows + OneDrive
        os.path.join(HOME, '.local', 'share', 'kicad'),                        # Linux
        os.path.join(HOME, '.var', 'app', 'org.kicad.KiCad', 'data', 'kicad'),  # Linux flatpak
    ]
    found = []
    for r in roots:
        found += [p for p in glob.glob(os.path.join(r, '*', '3rdparty', 'plugins', PLUGIN_ID)) if is_krt(p)]
    found.sort(key=version_key, reverse=True)
    return found[0] if found else None


def read_env():
    env = {}
    if os.path.isfile(ENV_FILE):
        for line in open(ENV_FILE, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def venv_bin(venv):
    return os.path.join(venv, 'Scripts' if WIN else 'bin')


def venv_python(venv):
    return os.path.join(venv_bin(venv), 'python.exe' if WIN else 'python3')


def probe(python, krt):
    """-> (missing packages, router library message or '')"""
    code = ("import importlib.util, sys\n"
            "miss=[m for m in ('numpy','scipy','shapely','PIL') if importlib.util.find_spec(m) is None]\n"
            "print('MISSING=' + ','.join(miss))\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "try:\n"
            "    import grid_router; print('ROUTER=' + str(getattr(grid_router, '__version__', 'ok')))\n"
            "except Exception as e:\n"
            "    print('ROUTER_ERR=' + type(e).__name__ + ': ' + str(e)[:120])\n")
    try:
        out = subprocess.run([python, '-c', code, os.path.join(krt or '', 'rust_router')],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception as e:      # noqa: BLE001
        return ['numpy', 'scipy', 'shapely', 'PIL'], 'could not run %s (%s)' % (python, e)
    info = dict(l.split('=', 1) for l in out.splitlines() if '=' in l)
    if 'MISSING' not in info:       # the probe itself failed: assume nothing is there
        return ['numpy', 'scipy', 'shapely', 'PIL'], 'error: probe produced no output'
    missing = [m for m in info.get('MISSING', '').split(',') if m]
    return missing, info.get('ROUTER') or ('error: ' + info.get('ROUTER_ERR', 'no output'))


def find_tool(name, extra=()):
    path = shutil.which(name)
    if path:
        return path
    for p in extra:
        if os.path.isfile(p):
            return p
    return None


def check(args):
    """Print a status report. Returns True when everything required is in place."""
    good = True
    print('pcb-design status')
    krt = find_krt(args.krt)
    if krt:
        ver = ''
        vf = os.path.join(krt, 'VERSION')
        if os.path.isfile(vf):
            ver = open(vf).read().strip()
        say(OK, 'KiCadRoutingTools %s' % ver, krt)
        if not os.path.isdir(os.path.join(krt, '.claude', 'skills', 'plan-pcb-routing')):
            say(WARN, 'that copy has no .claude/skills folder', 'the sub-skills need 0.23 or newer')
            good = False
    else:
        good = False
        say(MISS, 'KiCadRoutingTools',
            'KiCad > Plugin and Content Manager > "KiCad Routing Tools", or clone '
            'github.com/drandyhaas/KiCadRoutingTools, run build_router.py there, and pass --krt PATH')
    venv = args.venv or read_env().get('KRT_VENV') or DEFAULT_VENV
    py = venv_python(venv)
    if os.path.isfile(py):
        missing, router = probe(py, krt)
        if missing:
            good = False
            say(MISS, 'router Python packages: ' + ', '.join(missing), 'run install.py')
        else:
            say(OK, 'router Python environment', venv)
        if krt:
            if router.startswith('error'):
                good = False
                say(MISS, 'router library (grid_router)', router + '; run build_router.py in the plugin folder')
            else:
                say(OK, 'router library ' + router)
    else:
        good = False
        say(MISS, 'router Python environment', 'run install.py (creates %s)' % venv)
    env = read_env()
    if env.get('KRT_ROOT') and is_krt(env['KRT_ROOT']) and os.path.isdir(env.get('KRT_BIN', '')):
        say(OK, 'settings file', ENV_FILE)
    else:
        good = False
        say(MISS, 'settings file', ENV_FILE + ' (run install.py)')
    for name in sorted(os.listdir(os.path.join(HERE, 'skills'))):
        src = os.path.join(HERE, 'skills', name, 'SKILL.md')
        dst = os.path.join(args.dest, name, 'SKILL.md')
        if not os.path.isfile(src) or name in args.skip:
            continue
        if not os.path.isfile(dst):
            good = False
            say(MISS, 'skill ' + name, 'not in ' + args.dest)
        elif filecmp.cmp(src, dst, shallow=False):
            say(OK, 'skill ' + name)
        else:
            say(WARN, 'skill ' + name, 'installed copy differs from this repository (install.py --force updates it)')
    cli = find_tool('kicad-cli', ('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
                                  r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'))
    if cli:
        try:
            v = subprocess.run([cli, 'version'], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:       # noqa: BLE001
            v = '?'
        say(OK, 'kicad-cli ' + v, cli if not shutil.which('kicad-cli') else '')
        if not shutil.which('kicad-cli'):
            say(WARN, 'kicad-cli is not on PATH', 'add its folder to PATH so the skills can call it')
    else:
        good = False
        say(MISS, 'kicad-cli', 'install KiCad 10 (kicad.org); see skills/pcb-design/references/install-quickstart.md')
    print('optional tools (see skills/pcb-design/references/install-quickstart.md):')
    for tool in ('ngspice', 'kibot', 'kikit', 'gerbv'):
        say(OK if shutil.which(tool) else '-      ', tool)
    return good


def make_env(args):
    krt = find_krt(args.krt)
    venv = args.venv or DEFAULT_VENV
    py = venv_python(venv)
    if not os.path.isfile(py):
        print('creating Python environment at %s' % venv)
        os.makedirs(os.path.dirname(venv), exist_ok=True)
        subprocess.check_call([sys.executable, '-m', 'venv', venv])
    reqs = ['-r', os.path.join(HERE, 'requirements.txt')]
    if krt and os.path.isfile(os.path.join(krt, 'requirements.txt')):
        reqs += ['-r', os.path.join(krt, 'requirements.txt')]      # the plugin's own floors win
    missing, _ = probe(py, krt)
    if missing or args.force:
        print('installing router packages (numpy, scipy, shapely, Pillow) from PyPI')
        subprocess.check_call([py, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check'] + reqs)
    if not krt:
        print('KiCadRoutingTools not found: the environment is ready, but the sub-skills stay '
              'disabled until the plugin is installed and install.py is run again.')
        return
    ver = ''
    if os.path.isfile(os.path.join(krt, 'VERSION')):
        ver = open(os.path.join(krt, 'VERSION')).read().strip()
    os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write('# written by pcb-design install.py on %s; read by the sub-skill launchers\n'
                % time.strftime('%Y-%m-%d'))
        f.write('KRT_ROOT=%s\nKRT_BIN=%s\nKRT_VENV=%s\nKRT_VERSION=%s\n' % (krt, venv_bin(venv), venv, ver))
    print('wrote %s' % ENV_FILE)


def install_skills(args):
    os.makedirs(args.dest, exist_ok=True)
    backup = os.path.join(HOME, '.config', 'pcb-design', 'backup', time.strftime('%Y%m%d-%H%M%S'))
    for name in sorted(os.listdir(os.path.join(HERE, 'skills'))):
        src = os.path.join(HERE, 'skills', name)
        if not os.path.isfile(os.path.join(src, 'SKILL.md')) or name in args.skip:
            continue
        dst = os.path.join(args.dest, name)
        if os.path.isdir(dst):
            same = not filecmp.dircmp(src, dst, ignore=['__pycache__', '.DS_Store']).diff_files \
                and not filecmp.dircmp(src, dst, ignore=['__pycache__', '.DS_Store']).left_only
            if same:
                continue
            if not args.force:
                print('  kept existing %s (differs; --force replaces it, keeping a backup)' % dst)
                continue
            os.makedirs(backup, exist_ok=True)
            shutil.move(dst, os.path.join(backup, name))
            print('  backed up old %s to %s' % (name, backup))
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
        print('  installed %s' % dst)


def make_zip():
    out = os.path.join(HERE, 'dist', 'pcb-design.zip')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for top in ('.claude-plugin', 'skills'):
            for root, dirs, files in os.walk(os.path.join(HERE, top)):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for fn in files:
                    if fn == '.DS_Store' or fn.endswith('.pyc'):
                        continue
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, HERE))
    print('wrote %s' % out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='report status only; change nothing')
    ap.add_argument('--zip', action='store_true', help='build dist/pcb-design.zip for upload as a Claude plugin')
    ap.add_argument('--env-only', action='store_true', help='set up the router environment, do not copy skills')
    ap.add_argument('--skills-only', action='store_true', help='copy skills, do not touch the router environment')
    ap.add_argument('--force', action='store_true', help='replace installed skills that differ (old copy is backed up)')
    ap.add_argument('--skip', action='append', default=[], metavar='SKILL', help='do not install this skill (repeatable)')
    ap.add_argument('--krt', metavar='PATH', help='KiCadRoutingTools folder, if it is not in a standard KiCad plugin location')
    ap.add_argument('--venv', metavar='PATH', help='where the router Python environment lives (default %s)' % DEFAULT_VENV)
    ap.add_argument('--dest', metavar='DIR', default=DEFAULT_DEST, help='skills folder (default %s)' % DEFAULT_DEST)
    a = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit('Python 3.9 or newer is required (this is %d.%d)' % sys.version_info[:2])
    if a.zip:
        make_zip()
        return 0
    if a.check:
        return 0 if check(a) else 1
    if not a.env_only:
        print('installing skills into %s' % a.dest)
        install_skills(a)
    if not a.skills_only:
        make_env(a)
    print()
    return 0 if check(a) else 1


if __name__ == '__main__':
    sys.exit(main())
