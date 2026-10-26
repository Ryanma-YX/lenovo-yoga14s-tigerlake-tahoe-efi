#!/bin/bash
# Only creates a user-space executable under build/. No driver installation.
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || { echo 'Requires x86_64 macOS' >&2; exit 1; }
xcrun --find clang++ >/dev/null
xcrun --find lldb >/dev/null
mkdir -p build
xcrun clang++ -std=c++17 -arch x86_64 -O1 -g -Wall -Wextra -Werror \
  -mmacosx-version-min=13.0 replay.cpp -o build/xe-replay
codesign --force --sign - build/xe-replay
codesign --verify --strict --verbose=2 build/xe-replay
file build/xe-replay
xcrun clang -arch x86_64 -fobjc-arc -O1 -g -Wall -Wextra -Werror \
  -mmacosx-version-min=13.0 -framework Foundation -framework Metal metal-smoke.m -o build/metal-smoke
codesign --force --sign - build/metal-smoke
codesign --verify --strict --verbose=2 build/metal-smoke
echo 'Runner built and ad-hoc signature checked. No plugin signature or Metal qualification implied.'
