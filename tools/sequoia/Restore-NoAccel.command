#!/bin/bash
# Restore the prepared bootable noaccel profile; no driver uninstall or disk erase.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
WORK=/Users/Shared/Sequoia-Restore-20261026
mkdir -p "$WORK"
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/guard.json" resized-recovery
/usr/sbin/diskutil mount "$(field esp "$WORK/guard.json")"
/usr/sbin/diskutil info -plist "$(field esp "$WORK/guard.json")" > "$WORK/esp.plist"
MOUNT=$(field MountPoint "$WORK/esp.plist")
[[ "$MOUNT" == /Volumes/* ]] || exit 1
PROFILE="$HERE/EFI-profiles/config-noaccel.plist"
EXPECTED=$(field bootstrapConfigSha256 "$HERE/efi-manifest.json")
[[ "$(shasum -a 256 "$PROFILE" | awk '{print $1}')" == "$EXPECTED" ]] || exit 1
CONFIG="$MOUNT/EFI/OC/config.plist"
CURRENT=$(shasum -a 256 "$CONFIG" | awk '{print $1}')
ACCEL=$(field acceleratedConfigSha256 "$HERE/efi-manifest.json")
[[ "$CURRENT" == "$EXPECTED" || "$CURRENT" == "$ACCEL" ]] || { echo 'Current EFI differs from both prepared profiles; refusing overwrite.'; exit 1; }
/bin/cp "$CONFIG" "$WORK/config-before-restore.plist"
/bin/cp "$PROFILE" "$CONFIG.sequoia-next"
/usr/bin/plutil -lint "$CONFIG.sequoia-next"
/bin/mv "$CONFIG.sequoia-next" "$CONFIG"
/bin/sync
echo 'Prepared noaccel profile restored. Restart required; no claim of Metal repair.'
