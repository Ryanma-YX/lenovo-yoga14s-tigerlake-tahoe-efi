"""Record pinned upstream provenance without copying its source or Apple assets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

OLD = 'b3f6b09af1a60093c0d953211469d0ef1fbd1847'
NEW = '453a7b5222d1e3f7f26c948feeaedc8f71d058b3'
FILES = ['macos/src/compiler-adapter.cpp', 'macos/src/llvm-bridge.cpp',
         'macos/build-shader-compiler.sh', 'macos/plugin-old-patches.json', 'docs/METAL.md', 'LICENSE']

def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('reference', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    files = {}
    for name in FILES:
        old = git(a.reference, 'show', OLD + ':' + name)
        new = git(a.reference, 'show', NEW + ':' + name)
        files[name] = {'sha256': hashlib.sha256(new).hexdigest(), 'bytes': len(new), 'unchangedSincePreviousAudit': old == new}
    result = {'checkedDateTaipei': '2026-10-26', 'repository': 'https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe',
              'previousCommit': OLD, 'observedMain': NEW, 'files': files,
              'changedFiles': git(a.reference, 'diff', '--name-only', OLD, NEW).decode().splitlines(),
              'licenseHeading': git(a.reference, 'show', NEW + ':LICENSE').decode().splitlines()[0]}
    a.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
