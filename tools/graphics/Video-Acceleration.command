#!/bin/bash
# Experimental whole-bundle isolation; retain Metal/3D and all EFI settings.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
MODE=${1:-status}
case "$MODE" in status|disable|restore) ;; *) echo 'Use: status | disable | restore'; exit 1;; esac
[[ "$(/usr/bin/uname -s)" == Darwin && "$(/usr/bin/uname -m)" == x86_64 ]] || { echo 'Run on this Intel macOS installation.'; exit 1; }
SOURCE=/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle
STATE='/Library/Application Support/WhateverXe-Video-Test-20261026'
SAVED="$STATE/AppleIntelTGLGraphicsVADriver.bundle"
MTL=/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver
MANIFEST="$HERE/va-files.sha256"
verify() {
    [[ -d "$1" && ! -L "$1" ]] || return 1
    # Windows CRLF must not become part of the filenames checked by shasum.
    (cd -- "$1" && /usr/bin/tr -d '\r' < "$MANIFEST" | /usr/bin/shasum -a 256 -c -)
}
if [[ "$MODE" == status ]]; then
    /usr/bin/sw_vers
    if [[ -d "$SOURCE" && ! -e "$SAVED" ]]; then
        echo 'VA bundle is in its normal location. Hardware video acceleration is available to clients.'
    elif [[ ! -e "$SOURCE" && -d "$SAVED" ]]; then
        echo 'VA bundle is isolated. Restart after a change; existing processes can retain the old plugin.'
    else
        echo 'Unexpected VA bundle state. Do not overwrite either location.'
    fi
    [[ ! -f "$MTL" ]] || echo 'Metal 3D plugin is present.'
    exit 0
fi
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$MODE"
VERSION=$(/usr/bin/sw_vers -productVersion)
[[ "$VERSION" == 15.8 || "$VERSION" == 15.8.* ]] || { echo "Expected supported Sequoia 15.8.x; found $VERSION. No change made."; exit 1; }
[[ -f "$MANIFEST" && -f "$MTL" ]] || { echo 'Required manifest or Metal plugin missing. No change made.'; exit 1; }
[[ ! -L "$STATE" && ! -L "$SOURCE" && ! -L "$SAVED" ]] || { echo 'Unexpected symlink; stopping.'; exit 1; }
MTL_BEFORE=$(/usr/bin/shasum -a 256 "$MTL" | /usr/bin/awk '{print $1}')
if [[ "$MODE" == disable ]]; then
    if [[ ! -e "$SOURCE" && -d "$SAVED" ]]; then
        verify "$SAVED"
        echo 'VA bundle is already isolated. No further change made.'
        exit 0
    fi
    [[ -d "$SOURCE" && ! -e "$SAVED" ]] || { echo 'Source missing or backup already exists. No change made.'; exit 1; }
    verify "$SOURCE" || { echo 'Installed VA bundle differs from the prepared Sequoia payload. No change made.'; exit 1; }
    /bin/mkdir -p "$STATE"
    /bin/chmod 755 "$STATE"
    /usr/bin/sw_vers > "$STATE/system-before.txt"
    /usr/sbin/sysctl kern.bootargs > "$STATE/bootargs-before.txt"
    /bin/mv "$SOURCE" "$SAVED"
    if ! verify "$SAVED"; then
        /bin/mv "$SAVED" "$SOURCE"
        echo 'Verification failed; bundle returned to original location.'
        exit 1
    fi
    echo 'Complete VA bundle moved outside GPUBundles. Restart before testing.'
    echo 'This isolates hardware video decode AND encode; it does not disable Metal 3D.'
else
    if [[ -d "$SOURCE" && ! -e "$SAVED" ]]; then
        verify "$SOURCE"
        echo 'VA bundle is already restored. No further change made.'
        exit 0
    fi
    [[ ! -e "$SOURCE" && -d "$SAVED" ]] || { echo 'Backup missing or destination occupied. No change made.'; exit 1; }
    verify "$SAVED" || { echo 'Backup verification failed. No change made.'; exit 1; }
    /bin/mv "$SAVED" "$SOURCE"
    if ! verify "$SOURCE"; then
        /bin/mv "$SOURCE" "$SAVED"
        echo 'Verification failed; bundle returned to isolated location.'
        exit 1
    fi
    echo 'Original signed VA bundle restored. Restart to make the restoration effective.'
fi
MTL_AFTER=$(/usr/bin/shasum -a 256 "$MTL" | /usr/bin/awk '{print $1}')
[[ "$MTL_BEFORE" == "$MTL_AFTER" ]] || { echo 'Metal binary changed unexpectedly; inspect before continuing.'; exit 1; }
/bin/sync
echo 'Metal plugin, kernel extensions, EFI and account settings were not modified.'
echo 'No reboot has been started automatically.'
