#!/bin/bash
# Recovery-local InstallAssistant launch, following corpnewt/UnPlugged's
# pkgutil --expand-full + SharedSupport symlink approach. No disk erasure.
set -euo pipefail
export LC_ALL=C
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || { echo 'Run this from Recovery Terminal as root.'; exit 1; }
PLAN="$HERE/disk-plan.plist"
source "$HERE/recovery_disk_guard.sh"
if [[ ${1:-} == --show-target ]]; then
    /usr/sbin/diskutil apfs list "$TARGET_CONTAINER"
    exit 0
fi
[[ -d /System/Installation/CDIS ]] || fail 'This launcher requires Recovery'
for tool in /usr/sbin/pkgutil /usr/bin/codesign /usr/bin/hdiutil /sbin/md5; do
    [[ -x "$tool" ]] || fail "Recovery lacks $tool"
done
# Resolve the destination only inside the guarded container, never by name alone.
i=0; matches=0; TARGET_VOLUME=''
while id=$(field "$GUARD_WORK/apfs.plist" "Containers:$i:ContainerReference"); do
    if [[ "$id" == "$TARGET_CONTAINER" ]]; then
        j=0
        while volume=$(field "$GUARD_WORK/apfs.plist" "Containers:$i:Volumes:$j:DeviceIdentifier"); do
            if [[ "$(field "$GUARD_WORK/apfs.plist" "Containers:$i:Volumes:$j:Name")" == Sequoia ]]; then
                ! field "$GUARD_WORK/apfs.plist" "Containers:$i:Volumes:$j:Roles:0" >/dev/null || fail 'Sequoia must be a freshly erased APFS volume with no role'
                TARGET_VOLUME=$volume; matches=$((matches+1))
            fi
            j=$((j+1))
        done
    fi
    i=$((i+1))
done
[[ $matches -eq 1 ]] || fail "First use Disk Utility to erase ONLY the old system volume group in $TARGET_CONTAINER, naming the fresh APFS volume Sequoia; then rerun this command"
[[ "$TARGET_VOLUME" =~ ^disk[0-9]+s[0-9]+$ ]] || fail 'invalid target volume'
/usr/sbin/diskutil mount "$TARGET_VOLUME"
info "$TARGET_VOLUME" "$GUARD_WORK/destination.plist"
DEST=$(field "$GUARD_WORK/destination.plist" MountPoint)
[[ "$DEST" == /Volumes/* && "$(field "$GUARD_WORK/destination.plist" APFSContainerReference)" == "$TARGET_CONTAINER" ]] || fail 'destination mount mismatch'
[[ ! -e "$DEST/System" && ! -e "$DEST/Users" ]] || fail 'destination contains an existing system or user data'
FREE=$(/bin/df -k "$DEST" | /usr/bin/awk 'END {print $4}')
[[ "$FREE" =~ ^[0-9]+$ && $FREE -ge 62914560 ]] || fail 'need 60 GiB free on destination'
/usr/sbin/diskutil mount "$USB_MEDIA"
info "$USB_MEDIA" "$GUARD_WORK/media.plist"
MEDIA=$(field "$GUARD_WORK/media.plist" MountPoint)
[[ "$MEDIA" == /Volumes/* ]] || fail 'USB data partition has no mount point'
PKG="$MEDIA/InstallAssistant.pkg"
[[ -f "$PKG" && "$(/usr/bin/stat -f %z "$PKG")" == "$(field "$HERE/installer-verified.plist" bytes)" ]] || fail 'complete local package missing'
echo 'Checking the local USB copy against the source transfer checksum...'
[[ "$(/sbin/md5 -q "$PKG")" == "$(field "$HERE/installer-verified.plist" transferMd5)" ]] || fail 'USB package transfer checksum mismatch'
STAGE=$(mktemp -d "$DEST/macOS-Installer-XXXXXXXX")
exec > >(/usr/bin/tee -a "$STAGE/recovery-install.log") 2>&1
echo 'Checking native Apple package signature...'
/usr/sbin/pkgutil --check-signature "$PKG" > "$STAGE/package-signature.txt" 2>&1 || fail 'native package signature check failed'
/bin/cat "$STAGE/package-signature.txt"
/usr/bin/grep -q 'Apple' "$STAGE/package-signature.txt" || fail 'Apple signer missing'
echo 'Extracting the matching installer app. Keep both external devices connected.'
/usr/sbin/pkgutil --expand-full "$PKG" "$STAGE/Expanded"
APP=$(/usr/bin/find "$STAGE/Expanded" -type d -name 'Install macOS Sequoia.app' -prune -print)
[[ -n "$APP" && "$APP" != *$'\n'* ]] || fail 'matching installer app missing or ambiguous'
[[ -x "$APP/Contents/MacOS/InstallAssistant" ]] || fail 'matching Sequoia app was not extracted'
/bin/mv "$APP" "$STAGE/Install macOS Sequoia.app"
APP="$STAGE/Install macOS Sequoia.app"
# Verify the extracted code before adding the data-volume link, as UnPlugged does.
/usr/bin/codesign --verify --deep --strict "$APP"
/bin/mkdir -p "$APP/Contents/SharedSupport"
[[ ! -e "$APP/Contents/SharedSupport/SharedSupport.dmg" ]] || fail 'unexpected embedded SharedSupport; inspect before continuing'
/bin/ln -s "$PKG" "$APP/Contents/SharedSupport/SharedSupport.dmg"
echo "Launching Sequoia installer. Select ONLY Sequoia in $TARGET_CONTAINER."
echo "Log: $STAGE/recovery-install.log"
"$APP/Contents/MacOS/InstallAssistant" >> "$STAGE/InstallAssistant.log" 2>&1 &
echo 'Installer launched; continue in its window. Installation and Metal validation remain pending.'
