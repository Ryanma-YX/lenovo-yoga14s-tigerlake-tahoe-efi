"""Fast read-only range backup using Python 3.14's native zstd codec.

The PowerShell wrapper must establish exact disk/partition identity first.
This helper opens the source read-only, never restores or writes disk sectors.
"""
import argparse
import compression.zstd as zstd
import hashlib
import json
import os
from pathlib import Path
import time

def backup(source, offset, length, destination, progress):
    destination, progress = Path(destination), Path(progress)
    if destination.exists() or destination.with_suffix(destination.suffix + '.partial').exists():
        raise ValueError('Refusing to overwrite backup')
    partial = destination.with_suffix(destination.suffix + '.partial')
    if offset < 0 or length <= 0:
        raise ValueError('Invalid source range')
    def status(stage, done):
        tmp = progress.with_suffix('.tmp')
        tmp.write_text(json.dumps({'stage': stage, 'bytes': done, 'total': length}), encoding='utf-8')
        tmp.replace(progress)
    sha = hashlib.sha256()
    done, next_report = 0, 0
    with open(source, 'rb', buffering=0) as inp, partial.open('xb') as raw:
        inp.seek(offset)
        with zstd.ZstdFile(raw, mode='wb', level=1) as out:
            while done < length:
                if (destination.parent / 'cancel-backup').exists():
                    raise RuntimeError('Backup cancellation requested; partial is not verified')
                chunk = inp.read(min(16 * 1024 * 1024, length - done))
                if not chunk:
                    raise IOError('Unexpected end of source range')
                sha.update(chunk)
                out.write(chunk)
                done += len(chunk)
                if done >= next_report or done == length:
                    status('read-and-compress-zstd', done)
                    next_report = done + 1024 * 1024 * 1024
        raw.flush()
        os.fsync(raw.fileno())
    status('verify-decompressed-backup', 0)
    check, verified = hashlib.sha256(), 0
    with zstd.open(partial, 'rb') as inp:
        while chunk := inp.read(16 * 1024 * 1024):
            check.update(chunk)
            verified += len(chunk)
            if verified % (1024 * 1024 * 1024) == 0:
                status('verify-decompressed-backup', verified)
    if verified != length or sha.digest() != check.digest():
        raise IOError('Decompressed backup does not match source length/SHA-256')
    partial.replace(destination)
    report = {'file': destination.name, 'offset': offset, 'rawBytes': length,
              'rawSha256': sha.hexdigest(), 'compressedBytes': destination.stat().st_size,
              'decompressedVerification': 'passed', 'codec': 'zstd-level-1', 'sourceAccess': 'read-only'}
    destination.with_suffix(destination.suffix + '.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    status('complete', length)
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source')
    p.add_argument('offset', type=int)
    p.add_argument('length', type=int)
    p.add_argument('destination', type=Path)
    p.add_argument('progress', type=Path)
    a = p.parse_args()
    print(json.dumps(backup(a.source, a.offset, a.length, a.destination, a.progress)))
