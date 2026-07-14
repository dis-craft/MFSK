#!/usr/bin/env bash
set -euo pipefail

unset GTK_PATH
unset GTK_EXE_PREFIX
unset GTK_MODULES
unset QT_ACCESSIBILITY
unset GTK_IM_MODULE_FILE
unset LD_LIBRARY_PATH

exec python3 "$(dirname "$0")/receiver_gui.py" "$@"