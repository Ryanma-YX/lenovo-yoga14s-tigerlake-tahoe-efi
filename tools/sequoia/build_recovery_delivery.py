"""Add a verified local Recovery host to the existing PRIVATE USB delivery.

No image downloading or disk writes. Use OpenCore's unchanged Apple RSA verifier.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import shutil


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--recovery', type=Path, required=True)
    parser.add_argument('--macrecovery', type=Path, required=True)
    args = parser.parse_args()
    base = args.preparation.resolve()
    root = base / 'Prepared' / 'USB-Delivery'
    setup = root / 'Sequoia-USB'
    spec = importlib.util.spec_from_file_location('macrecovery', args.macrecovery)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = args.recovery / 'BaseSystem.dmg'
    chunklist = args.recovery / 'BaseSystem.chunklist'
    with contextlib.redirect_stdout(io.StringIO()):
        chunks = list(module.verify_chunklist(str(chunklist)))
        module.verify_image(str(image), str(chunklist))
    # This qualified host contains pkgutil --expand-full and codesign. It does
    # not dictate the installed OS; the pinned local package supplies that app.
    if digest(image) != '591f07a9a4a58d855a2e53b86a5f5da854a250000a66a9382adaf106c20f839b':
        raise ValueError('Recovery host differs from the inspected 14.6.1 / 23G93 image')
    metadata = json.loads((setup / 'installer-verified.json').read_text(encoding='utf-8-sig'))
    package = base / 'Downloads' / 'InstallAssistant.pkg'
    if digest(package) != metadata['sha256']:
        raise ValueError('Original complete installer hash mismatch')
    metadata['transferMd5'] = digest(package, 'md5')
    (setup / 'installer-verified.plist').write_bytes(plistlib.dumps(metadata))
    plan = json.loads((setup / 'disk-plan.json').read_text(encoding='utf-8-sig'))
    (setup / 'disk-plan.plist').write_bytes(plistlib.dumps(plan))
    recovery = root / 'com.apple.recovery.boot'
    recovery.mkdir(exist_ok=True)
    shutil.copy2(image, recovery / image.name)
    shutil.copy2(chunklist, recovery / chunklist.name)
    for name in ('recovery_disk_guard.sh', 'Recovery-Install.command'):
        shutil.copy2(Path(__file__).with_name(name), setup / name)
    # Retire the launcher that depends on the unstable old desktop. A stale
    # shortcut must stop before invoking its former formatting workflow.
    (setup / 'Start-USB.command').write_text(
        '#!/bin/bash\necho "Use the independent USB Recovery. See INSTALL-STEPS.md."\nexit 1\n', encoding='utf-8', newline='\n')
    instructions = Path(__file__).resolve().parents[2].joinpath('START-HERE.md').read_text(encoding='utf-8')
    (setup / 'INSTALL-STEPS.md').write_text(instructions, encoding='utf-8')
    (base / 'START-HERE.md').write_text(instructions, encoding='utf-8')
    data_delivery = base / 'Prepared' / 'USB-Data-Delivery'
    data_delivery.mkdir(exist_ok=True)
    for name in ('START-HERE.md', 'START-HERE.txt'):
        (data_delivery / name).write_text(instructions, encoding='utf-8', newline='\n')
    shutil.copy2(Path(__file__).with_name('USB-Install.command'), data_delivery / 'INSTALL.command')
    shutil.copytree(setup, data_delivery / 'Sequoia-Setup', dirs_exist_ok=True)
    report = dict(recoveryHost='Sonoma 14.6.1 / 23G93', installedOS='Sequoia 15.8.1 / 24H32',
        appleChunklistRsaVerified=True, allChunksVerified=len(chunks), recoverySha256=digest(image),
        nativeBootTested=False, installerExecuted=False, metalValidated=False)
    (setup / 'recovery-verified.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    files = [dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
        for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ('recovery-deployment.json', 'usb-deployment.json')]
    (root / 'recovery-deployment.json').write_text(json.dumps(dict(files=files), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(report, files=len(files))))


if __name__ == '__main__':
    main()
