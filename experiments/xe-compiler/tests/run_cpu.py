"""Linux CPU mock test; no Apple binary, LLVM backend or macOS qualification."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture_format as fmt

def main():
    with tempfile.TemporaryDirectory(prefix='xe-cpu-') as temp:
        base = Path(temp)
        flags = ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-g', '-fsanitize=address,undefined']
        cc = shutil.which('g++')
        if not cc:
            raise RuntimeError('g++ is required for the Linux mock test')
        subprocess.run([cc, *flags, str(ROOT / 'replay.cpp'), '-ldl', '-o', str(base / 'runner')], check=True)
        subprocess.run([cc, *flags, '-fPIC', '-shared', str(ROOT / 'tests/mock_adapter.cpp'), '-o', str(base / 'mock.so')], check=True)
        sample = base / 'capture'
        sample.mkdir()
        hw = struct.pack('<I', 0x21) + bytes(124)
        meta = {'schema': 1, 'adapter_sha256': fmt.ADAPTER_SHA256, 'request_size': 216, 'flags': 0}
        for k, b in [('hw', hw), ('request', bytes(216)), ('bitcode', b'BC\xc0\xde')]:
            meta[k] = fmt.blob(sample, k, b)
        (sample / 'capture.json').write_text(json.dumps(meta), encoding='utf-8')
        fmt.validate(sample)
        result = subprocess.run([str(base / 'runner'), '--validated-capture', str(base / 'mock.so'), str(sample)],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
        assert result.stdout == 'adapter_result=1 reply_bytes=0 error_present=1\n', result.stdout
        assert not result.stderr, result.stderr
        print(json.dumps({'stage': 'linux-cpu-mock', 'compiler': 'g++', 'sanitizers': ['ASan', 'UBSan'],
                          'abiForwarding': 'passed', 'borrowedErrorOwnership': 'passed',
                          'macosCompiled': False, 'realAdapterReplayed': False, 'realMetalValidated': False}, indent=2))

if __name__ == '__main__':
    main()
