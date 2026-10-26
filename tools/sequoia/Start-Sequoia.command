#!/bin/bash
# Can be launched from the Windows NTFS preparation folder or the SSD ESP.
# Mounts only the identified external ESP, then runs preparation independently of
# Terminal/WindowServer so closing a window does not abandon a live resize.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 26.* ]] || { echo 'Start from the existing Tahoe.'; exit 1; }
WORK=/Users/Shared/Sequoia-Preparation-20261026
mkdir -p "$WORK"
[[ ! -e "$WORK/prepare.pid" ]] || { echo 'A preparation was already started; inspect its log before retrying.'; exit 1; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/launcher-guard.json" initial
ESP=$(/usr/bin/plutil -extract esp raw -o - "$WORK/launcher-guard.json")
/usr/sbin/diskutil mount "$ESP"
/usr/sbin/diskutil info -plist "$ESP" > "$WORK/launcher-esp.plist"
MOUNT=$(/usr/bin/plutil -extract MountPoint raw -o - "$WORK/launcher-esp.plist")
[[ "$MOUNT" == /Volumes/* && -f "$MOUNT/Sequoia-Prep/backup-approved.json" ]] || exit 1
/usr/bin/nohup /bin/bash "$MOUNT/Sequoia-Prep/Prepare-Installer.command" > "$WORK/launcher.log" 2>&1 < /dev/null &
echo "$!" > "$WORK/prepare.pid"
disown
echo "Preparation started. Log: $WORK/launcher.log"
echo "Watch with: tail -f '$WORK/launcher.log'"
echo 'Do not reboot/unplug until the log ends with MEDIA_READY.'
