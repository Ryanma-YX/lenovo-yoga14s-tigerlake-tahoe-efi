#!/bin/bash
# Install a verified profile plus Sequoia Wi-Fi on the approved SSK ESP.
# USB EFI remains a noaccel recovery path.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
PROFILE=${1:-noaccel}
[[ "$PROFILE" == noaccel || "$PROFILE" == accelerated ]] || exit 1
WORK=/Users/Shared/Sequoia-SSD-Profile-20261026
mkdir -p "$WORK"
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
hash() { /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/guard.json" external-recovery
/usr/sbin/diskutil mount "$(field esp "$WORK/guard.json")"
/usr/sbin/diskutil info -plist "$(field esp "$WORK/guard.json")" > "$WORK/esp.plist"
MOUNT=$(field MountPoint "$WORK/esp.plist")
[[ "$MOUNT" == /Volumes/* ]] || exit 1
CONFIG="$MOUNT/EFI/OC/config.plist"
CURRENT=$(hash "$CONFIG")
META="$HERE/efi-manifest.json"
[[ "$CURRENT" == "$(field sourceConfigSha256 "$META")" || "$CURRENT" == "$(field bootstrapConfigSha256 "$META")" || "$CURRENT" == "$(field acceleratedConfigSha256 "$META")" ]] || { echo 'SSK EFI config changed; refusing overwrite.'; exit 1; }
SELECTED="$HERE/EFI-profiles/config-$PROFILE.plist"
KEY=bootstrapConfigSha256
[[ "$PROFILE" != accelerated ]] || KEY=acceleratedConfigSha256
[[ "$(hash "$SELECTED")" == "$(field "$KEY" "$META")" ]] || exit 1
WIFI='AirportItlwm-Sequoia.kext'
SOURCE="$HERE/EFI/OC/Kexts/$WIFI"
[[ "$(hash "$SOURCE/Contents/MacOS/AirportItlwm")" == ec4c1fc83c0618be39b930fde1bf21fa3c467cf53490fa580245967869d45b0a && "$(hash "$SOURCE/Contents/Info.plist")" == 4628e59d1c4883d2d90bc39fe1aff60f59c9533a5f32597bc97cbca87b6f14ff ]] || exit 1
DEST="$MOUNT/EFI/OC/Kexts/$WIFI"
if [[ ! -e "$DEST" ]]; then /usr/bin/ditto "$SOURCE" "$DEST"; fi
[[ "$(hash "$DEST/Contents/MacOS/AirportItlwm")" == ec4c1fc83c0618be39b930fde1bf21fa3c467cf53490fa580245967869d45b0a && "$(hash "$DEST/Contents/Info.plist")" == 4628e59d1c4883d2d90bc39fe1aff60f59c9533a5f32597bc97cbca87b6f14ff ]] || exit 1
/bin/cp "$CONFIG" "$WORK/config-before-$PROFILE.plist"
/bin/cp "$SELECTED" "$CONFIG.sequoia-next"
/usr/bin/plutil -lint "$CONFIG.sequoia-next"
/bin/mv "$CONFIG.sequoia-next" "$CONFIG"
/bin/sync
echo "SSK EFI profile set to $PROFILE. USB EFI remains available for noaccel recovery."
