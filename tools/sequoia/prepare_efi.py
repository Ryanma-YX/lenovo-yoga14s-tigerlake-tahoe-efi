"""Prepare a separate dual-OS bootstrap EFI; never writes a mounted EFI itself."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import zipfile

WIFI_SHA256 = '865d0096dc3dc36b4ac5f60a5896216bfde5774e2c1f175e66ac4761f834937e'
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'

def build(source, archive, output, validator, template=False):
    source, archive, output = map(Path, (source, archive, output))
    if output.exists():
        raise ValueError('Output already exists; never overwrite a prepared or live EFI')
    original = plistlib.loads((source / 'OC/config.plist').read_bytes())
    ident = original['PlatformInfo']['Generic']
    if ident['SystemProductName'] != 'MacBookPro16,2':
        raise ValueError('Unexpected SMBIOS model')
    if not template and (not all(ident[k] for k in ('SystemSerialNumber', 'MLB', 'SystemUUID')) or
                         len(ident['ROM']) != 6 or not any(ident['ROM'])):
        raise ValueError('Real source identity is missing')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != WIFI_SHA256:
        raise ValueError('Sequoia Wi-Fi release hash mismatch')
    if not (source / 'OC/ACPI/SSDT-YTPD.aml').exists():
        raise ValueError('Confirmed trackpad table is missing')
    config = copy.deepcopy(original)
    entries = config['Kernel']['Add']
    old = [e for e in entries if e['BundlePath'] == 'AirportItlwm.kext']
    if len(old) != 1 or old[0]['MinKernel'] != '25.0.0':
        raise ValueError('Expected the known Tahoe Wi-Fi entry')
    new = copy.deepcopy(old[0])
    new.update(BundlePath='AirportItlwm-Sequoia.kext', MinKernel='24.0.0', MaxKernel='24.99.99',
               Comment='Sequoia-only AirportItlwm 2.4.0 alpha 738d4c6')
    entries.insert(entries.index(old[0]), new)
    # Tahoe support remains available for making the installer. SimpleHDA retains
    # its existing Darwin 25 guard; it will not load on Sequoia.
    assert config['ACPI'] == original['ACPI']
    assert config['Booter'] == original['Booter']
    assert config['PlatformInfo'] == original['PlatformInfo']
    assert config['NVRAM'] == original['NVRAM']
    expected = copy.deepcopy(original)
    expected['Kernel']['Add'].insert(expected['Kernel']['Add'].index(old[0]), new)
    assert config == expected
    shutil.copytree(source, output, ignore=shutil.ignore_patterns('._*', '.DS_Store'))
    dest = output / 'OC/Kexts/AirportItlwm-Sequoia.kext'
    dest.mkdir()
    with zipfile.ZipFile(archive) as z:
        members = [i for i in z.infolist() if 'AirportItlwm.kext/' in i.filename and not i.filename.startswith('__MACOSX/')]
        if not members:
            raise ValueError('Release has no AirportItlwm bundle')
        for info in members:
            relative = info.filename.split('AirportItlwm.kext/', 1)[1]
            if not relative or any(p.startswith('._') for p in Path(relative).parts):
                continue
            p = dest / relative
            if not p.resolve().is_relative_to(dest.resolve()):
                raise ValueError('Archive path escapes kext bundle')
            if info.is_dir():
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(info))
    info = plistlib.loads((dest / 'Contents/Info.plist').read_bytes())
    if info['CFBundleIdentifier'] != 'com.zxystd.AirportItlwm':
        raise ValueError('Wrong Wi-Fi bundle identifier')
    (output / 'OC/config.plist').write_bytes(plistlib.dumps(config, sort_keys=False))
    profiles = output.parent / (output.name + '-profiles')
    profiles.mkdir(exist_ok=False)
    accelerated = copy.deepcopy(config)
    args = accelerated['NVRAM']['Add'][GUID]['boot-args'].split()
    if args.count('-wex-noaccel') != 1 or '-x' in args or '-wexoff' in args:
        raise ValueError('Expected the confirmed normal-boot noaccel baseline')
    args.remove('-wex-noaccel')
    accelerated['NVRAM']['Add'][GUID]['boot-args'] = ' '.join(args)
    (profiles / 'config-accelerated.plist').write_bytes(plistlib.dumps(accelerated, sort_keys=False))
    shutil.copy2(output / 'OC/config.plist', profiles / 'config-noaccel.plist')
    for f in (output / 'OC/config.plist', profiles / 'config-accelerated.plist', profiles / 'config-noaccel.plist'):
        r = subprocess.run([str(Path(validator).resolve()), str(f.resolve())], capture_output=True)
        if r.returncode:
            raise ValueError('ocvalidate failed: ' + r.stdout.decode(errors='replace'))
    changed = []
    for p in source.rglob('*'):
        if p.is_file() and not p.name.startswith('._') and p.name != '.DS_Store':
            relative = p.relative_to(source)
            if p.read_bytes() != (output / relative).read_bytes():
                changed.append(relative.as_posix())
    if changed != ['OC/config.plist']:
        raise ValueError('Unexpected changes to original EFI files: ' + repr(changed))
    result = {'sourceIdentityPreserved': True, 'trackpadAndBooterUnchanged': True,
              'originalFilesChanged': changed, 'wifiSourceSha256': WIFI_SHA256,
              'sequoiaWifiKernelRange': ['24.0.0', '24.99.99'],
              'bootstrapBootArguments': 'unchanged; -wex-noaccel retained',
              'ocvalidateProfilesPassed': 3, 'physicalSequoiaBootTested': False,
              'templateOnly': template}
    (output.parent / (output.name + '-validation.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source-efi', type=Path, required=True)
    p.add_argument('--wifi-archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ocvalidate', type=Path, required=True)
    p.add_argument('--template', action='store_true')
    a = p.parse_args()
    build(a.source_efi, a.wifi_archive, a.output, a.ocvalidate, a.template)
