"""Resume a full Apple installer, then verify its integrityDataV1 SHA-256 chunks.

Inputs/outputs belong outside Git. Native Apple package signature verification
is still required on macOS; a matching transport digest does not replace it.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import struct
import time
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import urlparse
from urllib.request import Request, urlopen

def verify_catalog_xar(path, expected):
    # Apple's catalog Digest identifies the compressed XAR table of contents,
    # not the SHA-1 of the entire multi-gigabyte package.
    with Path(path).open('rb') as stream:
        header = stream.read(28)
        magic, size, version, compressed, uncompressed, algorithm = struct.unpack('>IHHQQI', header)
        if (magic, size, version, algorithm) != (0x78617221, 28, 1, 1) or not 0 < compressed < 8*1024*1024 or not 0 < uncompressed < 16*1024*1024:
            raise ValueError('Unexpected XAR header')
        raw = stream.read(compressed)
        if hashlib.sha1(raw).hexdigest() != expected.lower():
            raise ValueError('Apple catalog XAR TOC digest mismatch')
        toc = zlib.decompress(raw)
        if len(toc) != uncompressed:
            raise ValueError('XAR TOC length mismatch')
        root = ET.fromstring(toc)
        checksum = root.find('toc/checksum')
        if checksum is None or checksum.attrib.get('style') != 'sha1' or checksum.findtext('size') != '20':
            raise ValueError('Unsupported XAR checksum')
        offset = int(checksum.findtext('offset'))
        if not 0 <= offset <= Path(path).stat().st_size - 20 - size - compressed:
            raise ValueError('XAR checksum outside package')
        stream.seek(size + compressed + offset)
        if stream.read(20).hex() != expected.lower():
            raise ValueError('Stored XAR TOC checksum mismatch')
    return {'verified': True, 'kind': 'xar-compressed-toc-sha1', 'digest': expected.lower()}

def verify_integrity(path, manifest):
    raw = Path(manifest).read_bytes()
    magic, length, version, method, signature, count, offset, end = struct.unpack_from('<4sIBBBxQQQ', raw)
    if (magic, length, version, method, signature, offset) != (b'CNKL', 36, 1, 1, 2, 36):
        raise ValueError('Unsupported integrityDataV1 format')
    if end != offset + count * 36 or len(raw) != end + 32 or hashlib.sha256(raw[:end]).digest() != raw[end:]:
        raise ValueError('Invalid integrity manifest checksum/length')
    total, sha1, sha256 = 0, hashlib.sha1(), hashlib.sha256()
    with Path(path).open('rb') as stream:
        for i in range(count):
            size, expected = struct.unpack_from('<I32s', raw, offset + i * 36)
            if not 0 < size <= 64 * 1024 * 1024:
                raise ValueError('Invalid integrity chunk length')
            chunk = stream.read(size)
            if len(chunk) != size or hashlib.sha256(chunk).digest() != expected:
                raise ValueError('Apple integrity chunk mismatch: %d' % i)
            sha1.update(chunk)
            sha256.update(chunk)
            total += size
        if stream.read(1):
            raise ValueError('Trailing package bytes')
    return {'chunks': count, 'bytes': total, 'signatureMethod': signature,
            'manifestChecksumVerified': True, 'nativeAppleSignatureVerified': False,
            'sha1': sha1.hexdigest(), 'sha256': sha256.hexdigest()}

def download(selection, target, workers=6, step=16 * 1024 * 1024):
    info = json.loads(Path(selection).read_text(encoding='utf-8-sig'))
    package = info['package']
    url, total, expected = package['URL'], package['Size'], package['Digest'].lower()
    if info['version'] != '15.8.1' or info['build'] != '24H32':
        raise ValueError('This preparation is pinned to 15.8.1 / 24H32')
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'swcdn.apple.com':
        raise ValueError('Expected Apple HTTPS CDN')
    if len(expected) != 40 or total < 10_000_000_000:
        raise ValueError('Missing complete-installer metadata')
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Final file already exists; verify instead of overwriting')
    parts = target.with_name(target.name + '.parts')
    parts.mkdir(exist_ok=True)
    manifest = parts / 'source.json'
    identity = {'url': url, 'bytes': total, 'sha1': expected, 'step': step}
    if manifest.exists():
        if json.loads(manifest.read_text()) != identity:
            raise ValueError('Existing parts belong to another download')
    else:
        manifest.write_text(json.dumps(identity), encoding='utf-8')
    count = (total + step - 1) // step
    def get(index):
        start, end = index * step, min(total, (index + 1) * step) - 1
        out = parts / ('%05d.part' % index)
        if out.exists() and out.stat().st_size == end - start + 1:
            return out.stat().st_size
        for attempt in range(5):
            try:
                req = Request(url + '?xe_part=%d&attempt=%d' % (index, attempt),
                              headers={'Range': 'bytes=%d-%d' % (start, end), 'User-Agent': 'SequoiaPreparation/1.0'})
                with urlopen(req, timeout=60) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != 'bytes %d-%d/%d' % (start, end, total):
                        raise ValueError('Server did not honor exact range')
                    data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise ValueError('Short range')
                tmp = out.with_suffix('.partial')
                tmp.write_bytes(data)
                tmp.replace(out)
                return len(data)
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(attempt + 1)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(get, i) for i in range(count)]
        for n, future in enumerate(as_completed(futures), 1):
            done += future.result()
            if n % 20 == 0 or n == count:
                print('Apple installer ranges %d/%d (%.1f%%)' % (n, count, done * 100 / total), flush=True)
    sha1, sha256 = hashlib.sha1(), hashlib.sha256()
    partial = target.with_suffix('.partial')
    with partial.open('wb') as output:
        for i in range(count):
            with (parts / ('%05d.part' % i)).open('rb') as source:
                while chunk := source.read(8 * 1024 * 1024):
                    output.write(chunk)
                    sha1.update(chunk)
                    sha256.update(chunk)
    if partial.stat().st_size != total:
        raise ValueError('Full installer size mismatch')
    integrity = target.with_name('InstallAssistant.pkg.integrityDataV1')
    if not integrity.exists():
        integrity_url = package['IntegrityDataURL']
        if urlparse(integrity_url).scheme != 'https' or urlparse(integrity_url).hostname != 'swcdn.apple.com':
            raise ValueError('Invalid Apple integrity URL')
        integrity.write_bytes(urlopen(integrity_url, timeout=45).read())
    verified = verify_integrity(partial, integrity)
    if verified['bytes'] != total:
        raise ValueError('Integrity manifest describes another package length')
    xar_digest = verify_catalog_xar(partial, expected)
    partial.replace(target)
    report = {'version': info['version'], 'build': info['build'], 'product': info['product'],
              'bytes': total, 'sha1': sha1.hexdigest(), 'sha256': sha256.hexdigest(),
              'catalogDigest': xar_digest, 'catalogDigestVerified': True,
              'integrityDataV1': verified, 'nativePackageSignatureVerified': False,
              'installerExecuted': False}
    target.with_name('installer-verified.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('selection', type=Path)
    p.add_argument('target', type=Path)
    p.add_argument('--workers', type=int, default=6)
    a = p.parse_args()
    download(a.selection, a.target, workers=a.workers)
