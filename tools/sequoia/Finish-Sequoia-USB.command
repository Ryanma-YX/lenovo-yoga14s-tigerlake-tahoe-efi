#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ $EUID -eq 0 ]] || exec sudo /bin/bash "$0" "$@"
[[ "$(uname -m)" == x86_64 && "$(sw_vers -productVersion)" == 15.8.1 && "$(sw_vers -buildVersion)" == 24H32 ]] || { echo 'Expected Sequoia 15.8.1 / 24H32.'; exit 1; }
WORK=/Users/Shared/Sequoia-Finish-20261026
mkdir -p "$WORK"
exec > >(tee -a "$WORK/finish.log") 2>&1
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/disk-guard.json" external-media
PKG="$HERE/Payloads/WhateverXe-Graphics-0.2.0.pkg"
[[ "$(/usr/bin/shasum -a 256 "$PKG" | /usr/bin/awk '{print $1}')" == a70cca1fa5f085923be40ed346875c7a042bb002f5b87f57f0d2ef0ee35e6e4a ]] || exit 1
/usr/sbin/installer -pkg "$PKG" -target /
/bin/bash "$HERE/Set-SSD-USB-Profile.command" accelerated
echo 'Approve system extensions if requested. Restart through the SSK OpenCore to test acceleration.'
echo 'Booting OpenCore on the SanDisk USB keeps noaccel enabled for recovery.'
