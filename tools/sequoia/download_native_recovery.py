"""Download Apple's Sequoia Recovery using OpenCore's Apple RSA verification.

Supply an unchanged OpenCore macrecovery.py. Session metadata stays outside Git.
The iMacPro board supports Sequoia as its final OS. Inspect SystemVersion.plist
after downloading; the API product name alone does not establish the OS version.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--macrecovery', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('macrecovery', args.macrecovery)
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)

    def query(url, headers, post=None, raw=False):
        # Only the metadata service uses HTTPS; CDN URLs come from Apple's API.
        data = None if post is None else '\n'.join(k+'='+v for k, v in post.items()).encode()
        response = urlopen(Request(url.replace('http://', 'https://'), headers=headers, data=data), timeout=30)
        return response if raw else (dict(response.headers), response.read())

    recovery.run_query = query
    session = recovery.get_session(type('Options', (), {'verbose': False})())
    info = recovery.get_image_info(session, bid='Mac-7BA5B2D9E42DDD94',
        mlb=recovery.MLB_ZERO, os_type='latest')
    (root / 'recovery-info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')

    def request(kind, start=None, end=None, total=None):
        url, token = info['CU' if kind == 'chunklist' else 'AU'], info['CT' if kind == 'chunklist' else 'AT']
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname != 'oscdn.apple.com':
            raise ValueError('Unexpected Apple Recovery CDN')
        headers = {'User-Agent': 'InternetRecovery/1.0', 'Cookie': 'AssetToken='+token}
        if start is not None:
            headers['Range'] = f'bytes={start}-{end}'
        with urlopen(Request(url, headers=headers), timeout=45) as response:
            if start is None:
                return response.read(65537)
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
                raise ValueError('Recovery range mismatch')
            data = response.read(end-start+2)
            if len(data) != end-start+1:
                raise ValueError('Truncated recovery range')
            return data

    chunklist = root / 'BaseSystem.chunklist'
    chunklist.write_bytes(request('chunklist'))
    # Unchanged upstream verifier checks the Apple RSA key before trusting sizes.
    chunks = list(recovery.verify_chunklist(str(chunklist)))
    total = sum(size for size, _ in chunks)
    print(f'Apple RSA verified: {len(chunks)} chunks, {total} bytes', flush=True)
    ranges = root / ('ranges-' + hashlib.sha256(chunklist.read_bytes()).hexdigest()[:16])
    ranges.mkdir(exist_ok=True)
    step = 16 * 1024 * 1024
    count = (total+step-1)//step

    def get(index):
        start, end = index*step, min(total, (index+1)*step)-1
        dest = ranges / f'{index:04d}.part'
        if dest.exists() and dest.stat().st_size == end-start+1:
            return
        for attempt in range(4):
            try:
                dest.write_bytes(request('image', start, end, total))
                return
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt+1)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for done, future in enumerate(as_completed([pool.submit(get, i) for i in range(count)]), 1):
            future.result()
            if done % 10 == 0 or done == count:
                print(f'Recovery download {done}/{count}', flush=True)
    image = root / 'BaseSystem.partial'
    with image.open('wb') as stream:
        for i in range(count):
            stream.write((ranges / f'{i:04d}.part').read_bytes())
    with contextlib.redirect_stdout(io.StringIO()):
        recovery.verify_image(str(image), str(chunklist))
    image.replace(root / 'BaseSystem.dmg')
    with (root / 'BaseSystem.dmg').open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    result = dict(product=info['AP'], url=info['AU'], bytes=total, sha256=digest,
        appleRsaVerified=True, chunksVerified=len(chunks), nativeBootTested=False)
    (root / 'recovery-verified.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
