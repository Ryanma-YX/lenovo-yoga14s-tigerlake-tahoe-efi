"""Optional Capstone check of hash-pinned breakpoint sites against the real file.

These file offsets equal virtual addresses only for this audited adapter image.
The live collector uses ResolveFileAddress instead of assuming a load slide.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capture_format import ADAPTER_SHA256, digest

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('adapter', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    data = a.adapter.read_bytes()
    if digest(data) != ADAPTER_SHA256:
        raise ValueError('Wrong adapter')
    sys.modules['lldb'] = types.ModuleType('lldb')
    spec = importlib.util.spec_from_file_location('offset_audit', Path(__file__).with_name('lldb_capture.py'))
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    observations = []
    for address, (kind, reason) in capture.SITES.items():
        ins = next(cs.disasm(data[address:address+16], address))
        if ins.mnemonic != kind:
            raise ValueError('Breakpoint is not expected instruction: ' + hex(address))
        observations.append({'site': hex(address), 'instruction': ins.mnemonic + ' ' + ins.op_str,
                             'reason': reason})
    a.output.write_text(json.dumps({'adapter_sha256': digest(data), 'scope': 'static-x86_64-disassembly',
                                    'sites': observations, 'liveBreakpointTested': False}, indent=2) + '\n', encoding='utf-8')
