"""Hash gate + private subprocess replay. The child may abort; no signal recovery."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from capture_format import ADAPTER_SHA256, digest, validate

def main():
    p = argparse.ArgumentParser()
    p.add_argument('capture', type=Path)
    p.add_argument('--adapter', type=Path, default=Path('/Library/GPUBundles/XeCompilerAdapter.bundle/Contents/MacOS/adapter.dylib'))
    p.add_argument('--runner', type=Path, default=Path(__file__).parent / 'build/xe-replay')
    p.add_argument('--timeout', type=int, default=30)
    args = p.parse_args()
    meta, data = validate(args.capture)
    if 'hw' not in data:
        p.error('Create hardware argument was not captured; do not invent one')
    if meta.get('errors'):
        p.error('Incomplete/error capture; inspect capture.json privately')
    if digest(args.adapter.read_bytes()) != ADAPTER_SHA256:
        p.error('Only the audited unchanged adapter is admitted')
    if platform.system() != 'Darwin' or platform.machine() != 'x86_64':
        p.error('Real adapter replay requires x86_64 macOS')
    try:
        result = subprocess.run([str(args.runner.resolve()), '--validated-capture',
                                 str(args.adapter.resolve()), str(args.capture.resolve())],
                                timeout=args.timeout, capture_output=True, text=True)
        print(json.dumps({'stage': 'original-adapter-subprocess', 'exit': result.returncode,
                          'stdout': result.stdout, 'stderr': result.stderr,
                          'realMetalValidated': False}, indent=2))
        return 0 if result.returncode == 0 else 1
    except subprocess.TimeoutExpired:
        print('Replay timed out; child killed. This is not compiler success.', file=sys.stderr)
        return 124

if __name__ == '__main__':
    sys.exit(main())
