#!/bin/bash
# Read-only evidence and complete bundle backup; no EFI/disk/driver mutation.
set -euo pipefail
umask 077
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || { echo 'Requires x86_64 macOS' >&2; exit 1; }
OUT=${1:?Usage: bash preflight-macos.sh /absolute/new-private-directory}
[[ "$OUT" == /* && ! -e "$OUT" ]] || { echo 'Use a new absolute directory' >&2; exit 1; }
mkdir -m 700 -p -- "$OUT"
B=/Library/GPUBundles/XeCompilerAdapter.bundle
EXPECTED=5e5b788afa4d5b314f5425f3083aba801573a0a5b6c93a4938bdae61a839401e
ACTUAL=$(shasum -a 256 "$B/Contents/MacOS/adapter.dylib" | awk '{print $1}')
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo 'Adapter differs; stop before attaching' >&2; exit 1; }
sw_vers > "$OUT/macos-version.txt"
uname -r >> "$OUT/macos-version.txt"
shasum -a 256 "$B/Contents/MacOS/"* > "$OUT/bundle-sha256.txt"
codesign -dvvv --verbose=4 "$B" > "$OUT/signature.txt" 2>&1 || true
if codesign --verify --strict --verbose=4 "$B" > "$OUT/signature-verify.txt" 2>&1; then
  echo passed > "$OUT/signature-status.txt"
else
  echo failed > "$OUT/signature-status.txt"
fi
otool -L "$B/Contents/MacOS/adapter.dylib" > "$OUT/dependencies.txt"
nm -gU "$B/Contents/MacOS/adapter.dylib" > "$OUT/exports.txt"
xcrun --find clang++ > "$OUT/toolchain.txt"
xcrun --find lldb >> "$OUT/toolchain.txt"
LLVM=/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib
if [[ -e "$LLVM" ]]; then
  dyld_info -exports "$LLVM" > "$OUT/tahoe-llvm-exports.txt" 2>&1 || true
else
  echo 'Not a standalone file; may reside in dyld shared cache. Not proof of absent runtime image.' > "$OUT/tahoe-llvm-exports.txt"
fi
ditto --rsrc --extattr --acl "$B" "$OUT/XeCompilerAdapter.bundle"
shasum -a 256 "$OUT/XeCompilerAdapter.bundle/Contents/MacOS/adapter.dylib" > "$OUT/backup-adapter-sha256.txt"
echo 'Private evidence and full adapter bundle backup created. Keep locally; do not upload Apple payloads.'
