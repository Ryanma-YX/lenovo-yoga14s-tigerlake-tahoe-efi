import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capture_format as fmt


class EnvelopeTests(unittest.TestCase):
    def test_outer_checks(self):
        bc = b'BC\xc0\xde'
        self.assertEqual(fmt.layout(bc)['outer'], 'passed-envelope-only')
        for n in (0, 1, 3, 1048577):
            self.assertEqual(fmt.layout(bytes(n))['outer'], 'rejected-length')
        self.assertEqual(fmt.layout(bytes(4))['outer'], 'rejected-bitcode-magic')
        wrapped = struct.pack('<5I', 0x0b17c0de, 0, 20, 4, 0) + bc
        self.assertEqual(fmt.layout(wrapped)['size'], 4)
        for version, offset, size in ((1, 20, 4), (0, 19, 4), (0, 25, 4), (0, 20, 5), (0, 20, 3)):
            data = struct.pack('<5I', 0x0b17c0de, version, offset, size, 0) + bc
            self.assertEqual(fmt.layout(data)['outer'], 'rejected-wrapper-fields')
        self.assertEqual(fmt.layout(wrapped[:16])['outer'], 'rejected-wrapper-short')

    def test_integrity_and_missing_hw(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            meta = {'schema': 1, 'adapter_sha256': fmt.ADAPTER_SHA256,
                    'request_size': 216, 'flags': 0, 'hw': None}
            meta['request'] = fmt.blob(root, 'request', bytes(216))
            meta['bitcode'] = fmt.blob(root, 'bitcode', b'BC\xc0\xde')
            (root / 'capture.json').write_text(json.dumps(meta), encoding='utf-8-sig')
            _, data = fmt.validate(root)
            self.assertNotIn('hw', data)
            (root / 'bitcode.bin').write_bytes(b'other')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                fmt.validate(root)
            meta['bitcode']['file'] = '../bitcode.bin'
            (root / 'capture.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, 'filename'):
                fmt.validate(root)

    def test_branch_flags(self):
        # Imports callbacks without pretending LLDB is present or running them live.
        old = sys.modules.get('lldb')
        sys.modules['lldb'] = types.ModuleType('lldb')
        try:
            spec = importlib.util.spec_from_file_location('capture_test', Path(__file__).resolve().parents[1] / 'lldb_capture.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for flags in (0, 1, 0x40, 0x41, 0x202, 0x246):
                self.assertEqual(module.taken('je', flags), bool(flags & 0x40))
                self.assertEqual(module.taken('jne', flags), not bool(flags & 0x40))
                self.assertEqual(module.taken('jb', flags), bool(flags & 1))
        finally:
            if old is None:
                del sys.modules['lldb']
            else:
                sys.modules['lldb'] = old

    def test_entry_return_capture_with_mock_memory(self):
        old = sys.modules.get('lldb')
        fake_lldb = types.ModuleType('lldb')
        fake_lldb.SBError = lambda: types.SimpleNamespace(Fail=lambda: False)
        sys.modules['lldb'] = fake_lldb
        try:
            spec = importlib.util.spec_from_file_location('memory_capture_test', Path(__file__).resolve().parents[1] / 'lldb_capture.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.ensure = lambda frame: None  # unit test memory/call pairing, not platform validation
            with tempfile.TemporaryDirectory() as temp:
                mod.ROOT = Path(temp)
                target = MagicMock()
                ident = [0]
                def make_bp(addr):
                    ident[0] += 1
                    bp = MagicMock()
                    bp.IsValid.return_value = True
                    bp.GetNumLocations.return_value = 1
                    bp.GetID.return_value = ident[0]
                    return bp
                target.BreakpointCreateByAddress.side_effect = make_bp
                process = MagicMock()
                process.GetTarget.return_value = target
                blocks = {0x2000: bytes(216), 0x3000: b'BC\xc0\xde',
                          0x4000: struct.pack('<8Q', 0x9999, *range(0x5000, 0x5038, 8))}
                for pointer in range(0x5000, 0x5038, 8):
                    blocks[pointer] = bytes(8)
                def read(addr, n, err):
                    for base, data in blocks.items():
                        if base <= addr and addr + n <= base + len(data):
                            return data[addr-base:addr-base+n]
                    return b''
                process.ReadMemory.side_effect = read
                frame = MagicMock()
                frame.GetThread().GetProcess.return_value = process
                frame.GetThread().GetThreadID.return_value = 7
                frame.GetPCAddress().GetFileAddress.return_value = 0x12c0
                registers = dict(rdi=0x1000, rsi=0x2000, rdx=216, rcx=0, r8=0x3000, r9=4, rsp=0x4000, rax=1)
                mod.reg = lambda frame, name: registers[name]
                mod.HW[0x1000] = struct.pack('<I', 0x21) + bytes(124)
                self.assertFalse(mod.entered(frame, None, None))
                self.assertEqual(len(mod.RET), 1)
                loc = MagicMock()
                loc.GetBreakpoint().GetID.return_value = 1
                registers['rsp'] += 8
                self.assertFalse(mod.returned(frame, loc, None))
                self.assertEqual(mod.RET, {})
                meta, data = fmt.validate(Path(temp) / 'request-0001')
                self.assertEqual(meta['result'], 1)
                self.assertEqual(data['bitcode'], b'BC\xc0\xde')
                self.assertEqual(len(meta['output_words']), 7)
        finally:
            if old is None:
                del sys.modules['lldb']
            else:
                sys.modules['lldb'] = old

if __name__ == '__main__':
    unittest.main()
