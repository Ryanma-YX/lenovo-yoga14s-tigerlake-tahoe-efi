#!/bin/bash
# Run from the prepared USB EFI in Tahoe. Only the approved USB media volume
# is erased. No SSK resize or boot configuration update occurs here.
set -euo pipefail
export LC_ALL=C
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 26.* ]] || { echo 'Run from the existing Tahoe.'; exit 1; }
WORK=/Users/Shared/Sequoia-USB-Preparation-20261026
mkdir -p "$WORK"
exec > >(tee -a "$WORK/prepare.log") 2>&1
trap 'echo "USB preparation stopped. Keep the error/log; do not guess disk identifiers."' ERR
/usr/bin/caffeinate -dims -w $$ &
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
check() { [[ "$(/usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}')" == "$2" ]]; }
guard() { /usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$1" external-media; }
guard "$WORK/initial.json"
USB_ESP=$(field usbEsp "$WORK/initial.json")
MEDIA=$(field usbMedia "$WORK/initial.json")
/usr/sbin/diskutil mount "$USB_ESP"
/usr/sbin/diskutil info -plist "$USB_ESP" > "$WORK/usb-esp.plist"
USB_BOOT=$(field MountPoint "$WORK/usb-esp.plist")
[[ "$USB_BOOT" == /Volumes/* && "$HERE" == "$USB_BOOT/Sequoia-USB" ]] || { echo 'Run the script from the identified USB EFI.'; exit 1; }
check "$HERE/Payloads/WhateverXe-Graphics-0.2.0.pkg" a70cca1fa5f085923be40ed346875c7a042bb002f5b87f57f0d2ef0ee35e6e4a
META="$HERE/installer-verified.json"
[[ "$(field version "$META")" == 15.8.1 && "$(field build "$META")" == 24H32 && "$(field integrityDataV1.chunks "$META")" == 1494 ]] || exit 1
PKG_SHA=$(field sha256 "$META")
APP='/Applications/Install macOS Sequoia.app'
# The full pkg is read from the USB NTFS data volume, then expanded onto Tahoe.
# After expansion no required payload remains on the volume being erased.
/usr/sbin/diskutil mount "$MEDIA"
/usr/sbin/diskutil info -plist "$MEDIA" > "$WORK/usb-source.plist"
SOURCE=$(field MountPoint "$WORK/usb-source.plist")
[[ "$SOURCE" == /Volumes/* && "$SOURCE" != "$USB_BOOT" ]] || exit 1
PKG="$SOURCE/InstallAssistant.pkg"
if [[ -f "$PKG" ]]; then
  check "$PKG" "$PKG_SHA" || { echo 'USB installer package checksum mismatch.'; exit 1; }
  /usr/sbin/pkgutil --check-signature "$PKG" | tee "$WORK/apple-package-signature.txt"
  /usr/sbin/installer -pkg "$PKG" -target /
else
  # Re-entry after createinstallmedia erased the staging pkg requires the
  # locally recorded successful install; do not silently accept an unrelated app.
  [[ -f "$WORK/app-verified.json" ]] || { echo 'Staged package missing; no prior verified local app.'; exit 1; }
  [[ "$(field packageSha256 "$WORK/app-verified.json")" == "$PKG_SHA" ]] || exit 1
fi
[[ -x "$APP/Contents/Resources/createinstallmedia" && -f "$APP/Contents/SharedSupport/SharedSupport.dmg" ]] || exit 1
/usr/bin/codesign --verify --deep --strict "$APP"
"$APP/Contents/Resources/createinstallmedia" --help > "$WORK/createinstallmedia-help.txt" 2>&1 || true
/usr/bin/grep -q -- '--volume' "$WORK/createinstallmedia-help.txt"
printf '{"packageSha256":"%s"}\n' "$PKG_SHA" > "$WORK/app-verified.json"
guard "$WORK/before-erase.json"
[[ "$(field usbMedia "$WORK/before-erase.json")" == "$MEDIA" && "$(field usbEsp "$WORK/before-erase.json")" == "$USB_ESP" ]] || exit 1
echo 'Erasing ONLY the approved separate SanDisk USB media partition.'
# Work in a local directory, not on the volume createinstallmedia will erase.
cd "$WORK"
/usr/sbin/diskutil eraseVolume JHFS+ SEQ-INSTALL "$MEDIA"
guard "$WORK/formatted.json"
[[ "$(field usbMedia "$WORK/formatted.json")" == "$MEDIA" ]] || exit 1
/usr/sbin/diskutil info -plist "$MEDIA" > "$WORK/media.plist"
MOUNT=$(field MountPoint "$WORK/media.plist")
[[ "$MOUNT" == /Volumes/* && "$MOUNT" != "$USB_BOOT" ]] || exit 1
"$APP/Contents/Resources/createinstallmedia" --volume "$MOUNT" --nointeraction
guard "$WORK/media-created.json"
/usr/sbin/diskutil info -plist "$MEDIA" > "$WORK/media-ready.plist"
MOUNT=$(field MountPoint "$WORK/media-ready.plist")
[[ "$MOUNT" == /Volumes/* && "$MOUNT" != "$USB_BOOT" ]] || exit 1
/usr/bin/ditto "$HERE" "$MOUNT/Sequoia-Setup"
/bin/sync
echo 'EXTERNAL_USB_MEDIA_READY: boot the SanDisk USB OpenCore, then Install macOS Sequoia.'
echo 'SSK partitions and its live EFI have not been changed by this script.'
echo 'Use Show-Install-Target.command before erasing ONLY the old Tahoe system volume group.'
