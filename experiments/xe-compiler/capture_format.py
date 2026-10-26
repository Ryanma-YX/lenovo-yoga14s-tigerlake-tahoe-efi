"""Private, bounded capture format. No LLVM parsing or GPU validation is implied."""
import hashlib
import json
from pathlib import Path
import struct

ADAPTER_SHA256 = '5e5b788afa4d5b314f5425f3083aba801573a0a5b6c93a4938bdae61a839401e'
MAX_BLOB = 16 * 1024 * 1024  # capture cap, NOT a proposed adapter limit


def digest(data):
    return hashlib.sha256(data).hexdigest()


def layout(data):
    """Only the outer checks observed in adapter 0x1403..0x14a4."""
    n = len(data)
    if not 4 <= n <= 1048576:
        return {'outer': 'rejected-length', 'bytes': n}
    offset, size = 0, n
    if data[:4] == bytes.fromhex('dec0170b'):
        if n < 20:
            return {'outer': 'rejected-wrapper-short'}
        _, version, offset, size, cpu = struct.unpack_from('<5I', data)
        if version or offset < 20 or offset > n or size < 4 or size > n - offset:
            return {'outer': 'rejected-wrapper-fields', 'version': version,
                    'offset': offset, 'size': size, 'cpu': cpu}
    if data[offset:offset+4] != b'BC\xc0\xde':
        return {'outer': 'rejected-bitcode-magic', 'offset': offset}
    return {'outer': 'passed-envelope-only', 'offset': offset, 'size': size,
            'llvmParse': 'not-tested', 'attributeScan': 'not-tested',
            'functionConversion': 'not-tested'}


def blob(folder, name, data):
    if name not in ('hw', 'request', 'bitcode') or len(data) > MAX_BLOB:
        raise ValueError('Invalid capture blob')
    path = Path(folder) / (name + '.bin')
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o600)
    return {'file': path.name, 'bytes': len(data), 'sha256': digest(data)}


def verified_blob(folder, item, name):
    if item['file'] != name + '.bin':
        raise ValueError('Unexpected filename')
    path = Path(folder) / item['file']
    if path.is_symlink() or not 0 <= item['bytes'] <= MAX_BLOB:
        raise ValueError('Unsafe blob')
    if path.stat().st_size != item['bytes']:
        raise ValueError('Capture length/hash mismatch: ' + name)
    data = path.read_bytes()
    if len(data) != item['bytes'] or digest(data) != item['sha256']:
        raise ValueError('Capture length/hash mismatch: ' + name)
    return data


def validate(folder):
    folder = Path(folder)
    meta = json.loads((folder / 'capture.json').read_text(encoding='utf-8-sig'))
    if meta.get('schema') != 1 or meta.get('adapter_sha256') != ADAPTER_SHA256:
        raise ValueError('Unsupported capture schema or adapter')
    data = {k: verified_blob(folder, meta[k], k) for k in ('request', 'bitcode')}
    if len(data['request']) != 0xd8 or meta['request_size'] != 0xd8 or meta['flags'] != 0:
        raise ValueError('Replay currently admits only observed 0xD8/flags=0 contract')
    if not data['bitcode']:
        raise ValueError('No bitcode sample')
    if meta.get('hw'):
        data['hw'] = verified_blob(folder, meta['hw'], 'hw')
        if len(data['hw']) != 0x80 or struct.unpack_from('<I', data['hw'])[0] != 0x21:
            raise ValueError('Unexpected hardware structure')
    return meta, data


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('capture', type=Path)
    a = p.parse_args()
    m, d = validate(a.capture)
    print(json.dumps({'captureIntegrity': 'passed', 'hardwareCaptured': 'hw' in d,
                      'layout': layout(d['bitcode']), 'result': m.get('result'),
                      'rejections': m.get('rejections', []),
                      'realMetalValidated': False}, indent=2))
