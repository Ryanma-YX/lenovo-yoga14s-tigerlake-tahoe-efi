#!/bin/bash
# Read-only target map, usable from the installer Terminal or the existing OS.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
WORK=$(mktemp -d /tmp/sequoia-target.XXXXXX)
/usr/bin/osascript -l JavaScript "$HERE/mac_disk_guard.js" "$HERE/disk-plan.json" "$WORK/guard.json" resized-recovery
field() { /usr/bin/plutil -extract "$1" raw -o - "$2"; }
echo "Approved replacement container: $(field targetContainer "$WORK/guard.json")"
echo "Its physical store: $(field targetStore "$WORK/guard.json")"
echo "PROTECTED old data store (DO NOT erase): $(field protectedStore "$WORK/guard.json")"
echo 'Only erase the existing Tahoe SYSTEM VOLUME GROUP inside the approved replacement container.'
echo 'Do not erase the whole SSD, APFS container, protected data store, or temporary installer.'
/usr/sbin/diskutil apfs list "$(field targetContainer "$WORK/guard.json")"
