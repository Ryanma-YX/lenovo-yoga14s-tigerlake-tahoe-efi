#!/bin/bash
# Installs the matching Graphics package and enables acceleration only after
# verifying the actual Sequoia root and the expected bootstrap EFI.
set -euo pipefail
export LC_ALL=C
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 15.8.1 && "$(sw_vers -buildVersion)" == 24H32 ]] || { echo 'Expected Sequoia 15.8.1 / 24H32.'; exit 1; }
WORK=/Users/Shared/Sequoia-Finish-20261026
mkdir -p "$WORK"
exec > >(tee -a "$WORK/finish.log") 2>&1
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
check() { [[ "$(shasum -a 256 "$1" | awk '{print $1}')" == "$2" ]]; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/disk-guard.json" resized
ESP=$(field esp "$WORK/disk-guard.json")
PKG="$HERE/Payloads/WhateverXe-Graphics-0.2.0.pkg"
check "$PKG" a70cca1fa5f085923be40ed346875c7a042bb002f5b87f57f0d2ef0ee35e6e4a || { echo 'Graphics package hash mismatch.'; exit 1; }
/usr/sbin/installer -pkg "$PKG" -target /
/usr/sbin/diskutil mount "$ESP"
/usr/sbin/diskutil info -plist "$ESP" > "$WORK/esp-info.plist"
MOUNT=$(field MountPoint "$WORK/esp-info.plist")
[[ "$MOUNT" == /Volumes/* ]] || exit 1
CONFIG="$MOUNT/EFI/OC/config.plist"
check "$CONFIG" "$(field bootstrapConfigSha256 "$HERE/efi-manifest.json")" || { echo 'EFI changed; Graphics installed but boot arguments not modified.'; exit 1; }
check "$HERE/EFI-profiles/config-accelerated.plist" "$(field acceleratedConfigSha256 "$HERE/efi-manifest.json")" || exit 1
/bin/cp "$CONFIG" "$MOUNT/EFI/OC/config-before-sequoia-acceleration.plist"
/bin/cp "$HERE/EFI-profiles/config-accelerated.plist" "$CONFIG.sequoia-next"
/usr/bin/plutil -lint "$CONFIG.sequoia-next"
/bin/mv "$CONFIG.sequoia-next" "$CONFIG"
/bin/sync
echo 'Graphics package installed; -wex-noaccel removed from the verified EFI profile.'
echo 'If macOS requests approval for system extensions, allow them in Privacy & Security before restarting.'
echo 'Restart, then test Metal and login stability. Installation alone is not acceleration validation.'
echo 'The temporary installer is retained as a recovery route.'
