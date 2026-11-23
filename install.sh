#!/bin/sh
# Thin wrapper: all logic is in install.py (works on macOS, Linux and, via "python install.py", Windows).
exec python3 "$(dirname "$0")/install.py" "$@"
