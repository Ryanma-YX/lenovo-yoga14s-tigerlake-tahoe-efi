#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 26.* ]] || exit 1
WORK=/Users/Shared/Sequoia-USB-Preparation-20261026
mkdir -p "$WORK"
if [[ -f "$WORK/prepare.pid" ]]; then
  PID=$(cat "$WORK/prepare.pid")
  [[ "$PID" =~ ^[0-9]+$ ]] || exit 1
  if kill -0 "$PID" 2>/dev/null; then echo 'Existing PID is active; inspect the log before retrying.'; exit 1; fi
fi
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/launcher-guard.json" external-media
/usr/bin/nohup /bin/bash "$HERE/Prepare-USB.command" > "$WORK/launcher.log" 2>&1 < /dev/null &
echo "$!" > "$WORK/prepare.pid"
disown
echo "USB preparation started. Watch: tail -f '$WORK/launcher.log'"
echo 'Wait for EXTERNAL_USB_MEDIA_READY before rebooting or unplugging.'
