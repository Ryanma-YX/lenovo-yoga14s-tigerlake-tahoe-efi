#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
WORK=$(mktemp -d /tmp/sequoia-usb-target.XXXXXX)
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/guard.json" external-recovery
field() { /usr/bin/plutil -extract "$1" raw -o - "$WORK/guard.json"; }
echo "Approved replacement container: $(field targetContainer)"
echo "Its physical store: $(field targetStore)"
echo "PROTECTED old data store (DO NOT erase): $(field protectedStore)"
echo "USB installer disk (DO NOT erase during installation): $(field usbWholeDisk)"
echo 'Only erase the old Tahoe SYSTEM VOLUME GROUP inside the approved replacement container.'
/usr/sbin/diskutil apfs list "$(field targetContainer)"
