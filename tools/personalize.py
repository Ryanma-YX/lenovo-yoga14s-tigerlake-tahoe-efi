"""Restore only identity fields from a local original config into build/EFI."""
import argparse
import copy
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-config', required=True, type=Path)
    args = parser.parse_args()
    source = plistlib.loads(args.from_config.read_bytes())
    identity = source['PlatformInfo']['Generic']
    if identity['SystemProductName'] != 'MacBookPro16,2':
        raise ValueError('Source identity must be for MacBookPro16,2')
    if not identity['MLB'] or not identity['SystemSerialNumber'] or not identity['SystemUUID']:
        raise ValueError('Source identity is incomplete')
    if not uuid.UUID(identity['SystemUUID']).int:
        raise ValueError('Source UUID is empty')
    if len(identity['ROM']) != 6 or not any(identity['ROM']):
        raise ValueError('Source ROM must contain six nonzero-identity bytes')
    output = ROOT / 'build/EFI'
    if output.exists():
        raise ValueError('build/EFI already exists; choose a separate checkout to avoid overwriting it')
    template = plistlib.loads((ROOT / 'EFI/OC/config.plist').read_bytes())
    config = copy.deepcopy(template)
    for key in ['MLB', 'ROM', 'SystemSerialNumber', 'SystemUUID']:
        config['PlatformInfo']['Generic'][key] = identity[key]
    for key in ['bluetoothInternalControllerInfo', 'bluetoothExternalDongleFailed']:
        if key in source['NVRAM']['Add'].get(GUID, {}):
            config['NVRAM']['Add'][GUID][key] = source['NVRAM']['Add'][GUID][key]
    shutil.copytree(ROOT / 'EFI', output)
    config_path = output / 'OC/config.plist'
    config_path.write_bytes(plistlib.dumps(config))
    if os.name == 'nt':
        result = subprocess.run([str(ROOT / 'tools/ocvalidate.exe'), str(config_path)], capture_output=True)
        if result.returncode:
            raise RuntimeError('Personalized config failed ocvalidate')
    print('Created build/EFI with your local identity. No identities were printed or written into the template.')


if __name__ == '__main__':
    main()
