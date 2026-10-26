#!/bin/bash
# Run from Sequoia-Prep on the SSK ESP while booted into the current Tahoe.
# The only partition operation is a live shrink of the identified Tahoe store,
# creating a temporary HFS installer inside its original region. No erase of Tahoe.
set -euo pipefail
export LC_ALL=C
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
if [[ $EUID -ne 0 ]]; then
  echo 'Administrator access is required for the approved installer preparation.'
  exec sudo /bin/bash "$0" "$@"
fi
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 26.* ]] || { echo 'Run this preparation from the current x86_64 Tahoe.' >&2; exit 1; }
WORK=/Users/Shared/Sequoia-Preparation-20261026
mkdir -p "$WORK"
exec > >(tee -a "$WORK/prepare.log") 2>&1
trap 'echo "Preparation stopped. Inspect the error above; do not erase or guess disk identifiers."' ERR
/usr/bin/caffeinate -dims -w $$ &
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
check_sha256() { [[ "$(/usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}')" == "$2" ]]; }
PLAN="$HERE/disk-plan.json"
[[ "$(field status "$HERE/backup-approved.json")" == metadata-only && "$(field userRequestedNoTahoeBackup "$HERE/backup-approved.json")" == true ]] || { echo 'User-selected EFI/GPT backup policy is missing.'; exit 1; }
check_sha256 "$PLAN" "$(field planSha256 "$HERE/backup-approved.json")" || { echo 'Disk plan hash differs from the backed-up source.'; exit 1; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$PLAN" "$WORK/initial.json" initial
TARGET=$(field targetStore "$WORK/initial.json")
NEW_SIZE=$(field resizedTargetBytes "$WORK/initial.json")
ESP=$(field esp "$WORK/initial.json")
/usr/sbin/diskutil mount "$ESP"
/usr/sbin/diskutil info -plist "$ESP" > "$WORK/esp-initial.plist"
ESP_INITIAL=$(field MountPoint "$WORK/esp-initial.plist")
[[ "$ESP_INITIAL" == /Volumes/* && "$HERE" == "$ESP_INITIAL/Sequoia-Prep" ]] || { echo 'Run the staged preparation on the identified external ESP.'; exit 1; }
GRAPHICS_RELATIVE=$(field graphicsRelativePathFromEsp "$HERE/payload-sources.json")
[[ "$GRAPHICS_RELATIVE" != /* && "$GRAPHICS_RELATIVE" != *..* ]] || exit 1
GRAPHICS="$HERE/../$GRAPHICS_RELATIVE"
check_sha256 "$GRAPHICS" a70cca1fa5f085923be40ed346875c7a042bb002f5b87f57f0d2ef0ee35e6e4a || { echo 'Original SSD Graphics package is missing or differs; no resize performed.'; exit 1; }
META="$HERE/installer-verified.json"
[[ "$(field version "$META")" == 15.8.1 && "$(field build "$META")" == 24H32 ]] || exit 1
[[ "$(field integrityDataV1.chunks "$META")" == 1494 && "$(field integrityDataV1.manifestChecksumVerified "$META")" == true ]] || { echo 'Complete Apple chunk verification is missing.'; exit 1; }
PKG_SHA=$(field sha256 "$META")
PKG=''
# A read-only NTFS mount can expose the Windows preparation directory. No NTFS
# write driver is installed or used. If it is unavailable, use the same Apple URL.
for candidate in /Volumes/*/LocalMCP-Test/Sequoia-Preparation-20261026/Downloads/InstallAssistant.pkg; do
  if [[ -f "$candidate" ]]; then
    if check_sha256 "$candidate" "$PKG_SHA"; then PKG="$candidate"; break; fi
  fi
done
if [[ -z "$PKG" ]]; then
  PKG="$WORK/InstallAssistant.pkg"
  if [[ ! -f "$PKG" ]] || ! check_sha256 "$PKG" "$PKG_SHA"; then
    URL=$(field package.URL "$HERE/installer-selected.json")
    [[ "$URL" == https://swcdn.apple.com/*/InstallAssistant.pkg ]] || exit 1
    echo 'Windows NTFS package not available; fetching the pinned full package over current Tahoe Wi-Fi.'
    /usr/bin/curl --fail --location --retry 4 --continue-at - --output "$PKG.partial" "$URL"
    check_sha256 "$PKG.partial" "$PKG_SHA" || { echo 'Installer hash mismatch.'; exit 1; }
    /bin/mv "$PKG.partial" "$PKG"
  fi
fi
/usr/sbin/pkgutil --check-signature "$PKG" | tee "$WORK/apple-package-signature.txt"
echo 'Installing the Apple InstallAssistant application into the current Tahoe /Applications.'
/usr/sbin/installer -pkg "$PKG" -target /
APP='/Applications/Install macOS Sequoia.app'
[[ -x "$APP/Contents/Resources/createinstallmedia" && -f "$APP/Contents/SharedSupport/SharedSupport.dmg" ]] || { echo 'Complete installer app not found.'; exit 1; }
/usr/bin/codesign --verify --deep --strict "$APP"
# Reject an unusable older createinstallmedia executable before any resize.
"$APP/Contents/Resources/createinstallmedia" --help > "$WORK/createinstallmedia-help.txt" 2>&1 || true
/usr/bin/grep -q -- '--volume' "$WORK/createinstallmedia-help.txt" || { echo 'createinstallmedia did not report the expected interface.'; exit 1; }
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$PLAN" "$WORK/before-resize.json" initial
/usr/sbin/diskutil apfs resizeContainer "$TARGET" limits -plist > "$WORK/resize-limits.plist"
echo 'Creating the temporary installer ONLY inside the approved former Tahoe region.'
/usr/sbin/diskutil apfs resizeContainer "$TARGET" "${NEW_SIZE}B" JHFS+ SEQ-INSTALL 0
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$PLAN" "$WORK/resized.json" resized
INSTALLER=$(field installerDevice "$WORK/resized.json")
/usr/sbin/diskutil mount "$INSTALLER"
/usr/sbin/diskutil info -plist "$INSTALLER" > "$WORK/installer-info.plist"
MOUNT=$(field MountPoint "$WORK/installer-info.plist")
[[ "$MOUNT" == /Volumes/* && -d "$MOUNT" ]] || exit 1
"$APP/Contents/Resources/createinstallmedia" --volume "$MOUNT" --nointeraction
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$PLAN" "$WORK/media-created.json" resized
/usr/sbin/diskutil info -plist "$INSTALLER" > "$WORK/installer-ready.plist"
MOUNT=$(field MountPoint "$WORK/installer-ready.plist")
[[ "$MOUNT" == /Volumes/* && -d "$MOUNT" ]] || exit 1
/usr/bin/ditto "$HERE" "$MOUNT/Sequoia-Setup"
/bin/mkdir -p "$MOUNT/Sequoia-Setup/Payloads"
/bin/cp "$GRAPHICS" "$MOUNT/Sequoia-Setup/Payloads/WhateverXe-Graphics-0.2.0.pkg"
/bin/cp "$WORK/media-created.json" "$MOUNT/Sequoia-Setup/media-created.json"
/usr/sbin/diskutil mount "$ESP"
/usr/sbin/diskutil info -plist "$ESP" > "$WORK/esp-info.plist"
ESP_MOUNT=$(field MountPoint "$WORK/esp-info.plist")
[[ "$ESP_MOUNT" == /Volumes/* ]] || exit 1
CONFIG="$ESP_MOUNT/EFI/OC/config.plist"
check_sha256 "$CONFIG" "$(field sourceConfigSha256 "$HERE/efi-manifest.json")" || { echo 'Live EFI config changed since backup; no EFI update performed.'; exit 1; }
[[ ! -e "$ESP_MOUNT/EFI/OC/Kexts/AirportItlwm-Sequoia.kext" ]] || { echo 'Sequoia Wi-Fi kext already exists; inspect before retry.'; exit 1; }
# Same-volume rename avoids keeping two large copies on the small ESP. A copy
# already exists on the complete installer and in the Windows private package.
/bin/mv "$HERE/EFI/OC/Kexts/AirportItlwm-Sequoia.kext" "$ESP_MOUNT/EFI/OC/Kexts/AirportItlwm-Sequoia.kext"
/bin/cp "$CONFIG" "$ESP_MOUNT/EFI/OC/config-before-sequoia.plist"
/bin/cp "$HERE/EFI/OC/config.plist" "$CONFIG.sequoia-next"
/usr/bin/plutil -lint "$CONFIG.sequoia-next"
/bin/mv "$CONFIG.sequoia-next" "$CONFIG"
check_sha256 "$CONFIG" "$(field bootstrapConfigSha256 "$HERE/efi-manifest.json")"
/bin/sync
echo 'MEDIA_READY: restart through the existing OpenCore and choose Install macOS Sequoia.'
echo 'Tahoe has NOT been erased. Use INSTALL-STEPS.md on the installer for the approved clean installation.'
echo 'Native installation and Metal validation are still pending. No automatic reboot requested.'
