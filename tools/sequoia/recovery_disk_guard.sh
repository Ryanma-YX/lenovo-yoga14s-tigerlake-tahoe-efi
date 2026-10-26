#!/bin/bash
# Source this file from Recovery. Only diskutil/plutil/PlistBuddy are required.
# Reads the private disk-plan.plist; does not erase, resize, or mount anything.
set -euo pipefail
PLAN=${PLAN:?Set PLAN to the private disk-plan.plist}
GUARD_WORK=$(mktemp -d /tmp/sequoia-guard.XXXXXX)
field() { /usr/libexec/PlistBuddy -c "Print :$2" "$1" 2>/dev/null; }
fail() { echo "STOP: $*" >&2; exit 1; }
norm() { printf '%s' "$1" | /usr/bin/tr '[:upper:]' '[:lower:]' | /usr/bin/tr -d '{}-'; }
info() { /usr/sbin/diskutil info -plist "$1" > "$2"; }
find_partition() {
    local spec=$1 wanted candidate id i=0 hits=0 found=''
    wanted=$(norm "$(field "$PLAN" "$spec:guid")")
    while id=$(field "$GUARD_WORK/list.plist" "AllDisks:$i"); do
        i=$((i+1))
        [[ "$id" =~ ^disk[0-9]+s[0-9]+$ ]] || continue
        candidate="$GUARD_WORK/$id.plist"
        info "/dev/$id" "$candidate"
        [[ "$(norm "$(field "$candidate" DiskUUID || true)")" == "$wanted" ]] || continue
        [[ "$(field "$candidate" TotalSize)" == "$(field "$PLAN" "$spec:bytes")" ]] || fail "$spec size changed"
        [[ "$(field "$candidate" PartitionMapPartitionOffset)" == "$(field "$PLAN" "$spec:offset")" ]] || fail "$spec offset changed"
        hits=$((hits+1)); found=$id
    done
    [[ $hits -eq 1 ]] || fail "$spec GPT identity missing or ambiguous"
    printf '%s' "$found"
}
check_whole() {
    local disk=$1 spec=$2
    [[ "$disk" =~ ^disk[0-9]+$ ]] || fail 'invalid physical disk'
    info "/dev/$disk" "$GUARD_WORK/$disk.plist"
    [[ "$(field "$GUARD_WORK/$disk.plist" Internal)" == false ]] || fail 'disk is not external'
    [[ "$(field "$GUARD_WORK/$disk.plist" TotalSize)" == "$(field "$PLAN" "$spec:bytes")" ]] || fail 'physical capacity changed'
}
/usr/sbin/diskutil list -plist > "$GUARD_WORK/list.plist"
SSD_ESP=$(find_partition esp)
PROTECTED_STORE=$(find_partition protected)
TARGET_STORE=$(find_partition target)
SSD_WHOLE=$(field "$GUARD_WORK/$TARGET_STORE.plist" ParentWholeDisk)
[[ "$(field "$GUARD_WORK/$SSD_ESP.plist" ParentWholeDisk)" == "$SSD_WHOLE" && "$(field "$GUARD_WORK/$PROTECTED_STORE.plist" ParentWholeDisk)" == "$SSD_WHOLE" ]] || fail 'SSD partitions belong to different disks'
check_whole "$SSD_WHOLE" disk
USB_ESP=$(find_partition usb:esp)
USB_MEDIA=$(find_partition usb:media)
USB_WHOLE=$(field "$GUARD_WORK/$USB_ESP.plist" ParentWholeDisk)
[[ "$USB_WHOLE" != "$SSD_WHOLE" && "$(field "$GUARD_WORK/$USB_MEDIA.plist" ParentWholeDisk)" == "$USB_WHOLE" ]] || fail 'USB identity conflicts with SSD'
check_whole "$USB_WHOLE" usb:disk
/usr/sbin/diskutil apfs list -plist > "$GUARD_WORK/apfs.plist"
TARGET_CONTAINER=''; i=0; hits=0
while container=$(field "$GUARD_WORK/apfs.plist" "Containers:$i:ContainerReference"); do
    if [[ "$(field "$GUARD_WORK/apfs.plist" "Containers:$i:PhysicalStores:0:DeviceIdentifier" || true)" == "$TARGET_STORE" ]]; then
        ! field "$GUARD_WORK/apfs.plist" "Containers:$i:PhysicalStores:1" >/dev/null || fail 'target container has multiple stores'
        TARGET_CONTAINER=$container; hits=$((hits+1))
    fi
    i=$((i+1))
done
[[ $hits -eq 1 ]] || fail 'target APFS container missing or ambiguous'
echo "Replacement container: $TARGET_CONTAINER (physical store $TARGET_STORE)"
echo "PROTECTED data partition: $PROTECTED_STORE; installation USB: $USB_WHOLE"
