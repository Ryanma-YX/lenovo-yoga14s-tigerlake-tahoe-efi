"""Offline Mach-O inventory; signature presence is NOT signature validation."""
import argparse
import json
from pathlib import Path
import struct

from capture_format import digest

def inspect(path):
    whole = Path(path).read_bytes()
    b = whole
    if b[:4] == bytes.fromhex('cafebabe'):
        for i in range(struct.unpack_from('>I', b, 4)[0]):
            cpu, sub, off, size, align = struct.unpack_from('>5I', b, 8 + i * 20)
            if cpu == 0x1000007:
                b = b[off:off+size]
                break
    if b[:4] != bytes.fromhex('cffaedfe') or struct.unpack_from('<I', b, 4)[0] != 0x1000007:
        raise ValueError('Expected x86_64 Mach-O')
    deps, symbols, signature, uuid = [], [], None, None
    pos, symtab = 32, None
    for _ in range(struct.unpack_from('<I', b, 16)[0]):
        cmd, size = struct.unpack_from('<II', b, pos)
        if size < 8 or pos + size > len(b):
            raise ValueError('Malformed Mach-O load command')
        if cmd in (0xc, 0x80000018, 0x8000001f, 0x80000023):
            off = struct.unpack_from('<I', b, pos + 8)[0]
            deps.append({'command': hex(cmd), 'name': b[pos+off:pos+size].split(b'\0')[0].decode()})
        elif cmd == 2:
            symtab = struct.unpack_from('<4I', b, pos + 8)
        elif cmd == 0x1b:
            uuid = b[pos+8:pos+24].hex()
        elif cmd == 0x1d:
            signature = dict(zip(('offset', 'bytes'), struct.unpack_from('<2I', b, pos+8)))
        pos += size
    if symtab:
        off, count, strings, strsize = symtab
        for i in range(count):
            name, kind, section, desc, value = struct.unpack_from('<IBBHQ', b, off + i * 16)
            if kind & 0xe0 or not kind & 1:
                continue
            text = b[strings+name:strings+strsize].split(b'\0')[0].decode(errors='replace')
            if text.startswith(('_MTLCompiler', '_CreateShader', '_CompileCSAIR', '_CompileVSAIR',
                                '_CompilePSAIR', '_DeleteShader', '_DeleteCSAIR', '_DeleteVSAIR', '_DeletePSAIR')):
                symbols.append({'name': text, 'defined': bool(kind & 0x0e), 'value': hex(value)})
    return {'sha256': digest(whole), 'bytes': len(whole), 'uuid': uuid, 'dependencies': deps,
            'compiler_symbols': symbols, 'code_signature_command': signature,
            'signature_verified': False, 'macos_loaded': False}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('binary', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    report = json.dumps(inspect(a.binary), indent=2) + '\n'
    if a.output:
        a.output.write_text(report, encoding='utf-8')
    else:
        print(report, end='')
