#!/bin/bash
# Collect local evidence only; do not change accounts, caches, drivers or EFI.
set -uo pipefail
LOOKBACK=${1:-2h}
[[ "$LOOKBACK" =~ ^[1-9][0-9]*[mhd]$ ]] || { echo 'Use a lookback such as 30m, 2h or 1d.'; exit 1; }
[[ "$(/usr/bin/uname -s)" == Darwin ]] || { echo 'Run this from macOS.'; exit 1; }
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
OUT="$HOME/Desktop/Sequoia-AppStore-$(/bin/date +%Y%m%d-%H%M%S)"
/bin/mkdir -p "$OUT/crashes" || exit 1
exec > >(/usr/bin/tee "$OUT/collection.log") 2>&1
echo 'Collecting previous freeze evidence. Do not open App Store during collection.'
sudo -v || exit 1
/usr/bin/sw_vers > "$OUT/system.txt"
/usr/bin/uname -a >> "$OUT/system.txt"
/usr/sbin/sysctl kern.safeboot kern.bootargs >> "$OUT/system.txt" 2>&1
/usr/bin/csrutil status > "$OUT/sip.txt" 2>&1
/usr/sbin/nvram boot-args csr-active-config > "$OUT/boot-variables.txt" 2>&1
sudo /usr/bin/kmutil showloaded > "$OUT/loaded-extensions.txt" 2>&1
/usr/sbin/system_profiler SPDisplaysDataType -timeout 20 > "$OUT/displays.txt" 2>&1
/usr/sbin/ioreg -r -c IntelAccelerator -l -w0 > "$OUT/accelerator.txt" 2>&1
/usr/sbin/networksetup -listallhardwareports > "$OUT/network-ports.txt" 2>&1
/usr/sbin/ioreg -r -c IONetworkInterface -l -w0 > "$OUT/network-interfaces.txt" 2>&1
/usr/sbin/ioreg -r -c IOPlatformExpertDevice -l -w0 | /usr/bin/grep -E 'WhateverXe|TGL|DataAccess|WebKit' > "$OUT/wex-status.txt" 2>&1
/usr/bin/defaults read /Library/Preferences/FeatureFlags/Domain/CoreMedia > "$OUT/coremedia.txt" 2>&1
/usr/sbin/pkgutil --pkgs | /usr/bin/grep -Ei 'whateverxe|b00t0x' > "$OUT/package-ids.txt"
while IFS= read -r receipt; do
    /usr/sbin/pkgutil --pkg-info "$receipt"
done < "$OUT/package-ids.txt" > "$OUT/package-versions.txt" 2>&1
PREDICATE='process == "App Store" OR process == "appstoreagent" OR process == "appstored" OR process == "storeaccountd" OR process == "storeassetd" OR process == "accountsd" OR process == "akd" OR process == "amsaccountsd" OR process == "WindowServer" OR process == "MTLCompilerService" OR process == "com.apple.WebKit.GPU" OR ((process == "kernel" OR process == "watchdogd") AND (eventMessage CONTAINS[c] "GPU" OR eventMessage CONTAINS[c] "TGL" OR eventMessage CONTAINS[c] "WhateverXe" OR eventMessage CONTAINS[c] "hang" OR eventMessage CONTAINS[c] "stall" OR eventMessage CONTAINS[c] "watchdog" OR eventMessage CONTAINS[c] "AMFI"))'
PREDICATE="$PREDICATE OR process == \"VTDecoderXPCService\" OR process == \"VTEncoderXPCService\" OR subsystem CONTAINS[c] \"VideoToolbox\" OR subsystem CONTAINS[c] \"AppleGVA\""
sudo /usr/bin/log show --last "$LOOKBACK" --style compact --info --predicate "$PREDICATE" > "$OUT/recent-events.log" 2>&1
count=0
for folder in /Library/Logs/DiagnosticReports "$HOME/Library/Logs/DiagnosticReports"; do
    [[ -d "$folder" ]] || continue
    while IFS= read -r file; do
        count=$((count+1))
        [[ $count -le 16 ]] || break
        sudo /usr/bin/head -c 2097152 "$file" > "$OUT/crashes/$count-$(/usr/bin/basename "$file")"
    done < <(/usr/bin/find "$folder" -maxdepth 2 -type f -mtime -2 \( -iname '*WindowServer*' -o -iname '*App*Store*' -o -iname '*appstore*' -o -iname '*accountsd*' -o -iname '*akd*' -o -iname '*MTLCompiler*' -o -iname '*WebKit*GPU*' -o -iname '*panic*' -o -iname '*watchdog*' -o -iname '*GPU*' \) -exec /usr/bin/stat -f '%m %N' {} \; | /usr/bin/sort -rn | /usr/bin/head -n 16 | /usr/bin/cut -d ' ' -f 2-)
done
echo 'Collection finished. No applications were launched and no login data was changed.'
SIZE_KB=$(/usr/bin/du -sk "$OUT" | /usr/bin/awk '{print $1}')
if [[ "$HERE" == /Volumes/* && "$SIZE_KB" -lt 24576 ]]; then
    /bin/mkdir -p "$HERE/Reports"
    if /usr/bin/ditto "$OUT" "$HERE/Reports/$(/usr/bin/basename "$OUT")"; then
        /bin/sync
        echo "Copied report to EFI: $HERE/Reports/$(/usr/bin/basename "$OUT")"
    fi
fi
echo "Desktop report: $OUT"
echo 'Keep the report local for diagnosis. It can contain account or network identifiers.'
read -r -p 'Press Return to finish.'
