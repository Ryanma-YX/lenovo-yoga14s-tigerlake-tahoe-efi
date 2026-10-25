"""Validate the archived EFI using Python's standard library and ocvalidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside(base, relative):
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), 'Path escapes EFI: ' + relative)
    return path


def check_config(path):
    xml = ET.fromstring(path.read_bytes())
    for node in xml.iter('dict'):
        keys = [child.text for child in node if child.tag == 'key']
        require(len(keys) == len(set(keys)), 'Duplicate plist dictionary key')
    config = plistlib.loads(path.read_bytes())
    oc = ROOT / 'EFI/OC'
    for entry in config['ACPI']['Add']:
        if entry['Enabled']:
            data = inside(oc / 'ACPI', entry['Path']).read_bytes()
            require(data[:4] in [b'SSDT', b'DSDT'] and sum(data) % 256 == 0,
                    'Invalid AML checksum: ' + entry['Path'])
    active = []
    for i, entry in enumerate(config['Kernel']['Add']):
        if not entry['Enabled']:
            continue
        bundle = inside(oc / 'Kexts', entry['BundlePath'])
        info = plistlib.loads(inside(bundle, entry['PlistPath']).read_bytes())
        if entry['ExecutablePath']:
            require(inside(bundle, entry['ExecutablePath']).is_file(), 'Missing kext executable')
        active.append((i, info['CFBundleIdentifier'], info.get('OSBundleLibraries', {})))
    positions = {identifier: i for i, identifier, _ in active}
    require(len(positions) == len(active), 'Duplicate active kext bundle identifier')
    edges = 0
    for i, identifier, libraries in active:
        for dependency in libraries:
            if dependency in positions:
                edges += 1
                require(positions[dependency] < i,
                        'Dependency loads too late: ' + dependency + ' -> ' + identifier)
    binaries = [ROOT / 'EFI/BOOT/BOOTx64.efi', oc / 'OpenCore.efi']
    binaries += [inside(oc / 'Drivers', entry['Path']) for entry in config['UEFI']['Drivers'] if entry['Enabled']]
    for binary in binaries:
        data = binary.read_bytes()
        require(data[:2] == b'MZ', 'Not a PE image: ' + binary.name)
        offset = struct.unpack_from('<I', data, 0x3C)[0]
        require(data[offset:offset+4] == b'PE\0\0', 'Missing PE signature')
        require(struct.unpack_from('<H', data, offset + 4)[0] == 0x8664, 'EFI is not x86_64')
    identity = config['PlatformInfo']['Generic']
    require(all(identity[key] == '' for key in ['MLB', 'SystemSerialNumber', 'SystemUUID']),
            'Machine identity present in archive template')
    require(identity['ROM'] == bytes(6), 'Machine ROM present in archive template')
    nvram = config['NVRAM']['Add']['7C436110-AB2A-4BBB-A880-FE41995C9F82']
    for key in ['bluetoothInternalControllerInfo', 'bluetoothExternalDongleFailed']:
        require(not any(nvram[key]), 'Machine Bluetooth cache present')
    require(nvram['csr-active-config'] == bytes.fromhex('03080000'), 'Unexpected SIP Data')
    require(config['Kernel']['Quirks']['AppleXcpmExtraMsrs'], 'XCPM workaround is disabled')
    require(not config['Kernel']['Quirks']['ProvideCurrentCpuInfo'], 'Unexpected topology override')
    require(not any('WhateverGreen' in entry['BundlePath'] for entry in config['Kernel']['Add'] if entry['Enabled']),
            'WhateverGreen conflicts with WhateverXe')
    return {'activeKextEntries': len(active), 'internalDependencyEdges': edges,
            'acpiTables': sum(entry['Enabled'] for entry in config['ACPI']['Add'])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    results = {}
    for relative in ['EFI/OC/config.plist', 'profiles/config-basic-display.plist']:
        results[relative] = check_config(ROOT / relative)
    expected = json.loads((ROOT / 'docs/efi-sha256.json').read_text())
    for relative, digest in expected.items():
        require(hashlib.sha256(inside(ROOT, relative).read_bytes()).hexdigest() == digest,
                'SHA256 mismatch: ' + relative)
    hardware = json.loads((ROOT / 'docs/hardware.json').read_text(encoding='utf8'))
    report = {'status': 'passed', 'configs': results, 'hashedFiles': len(expected),
              'identityRedaction': 'passed', 'fileReferences': 'passed',
              'amlChecksums': 'passed', 'kextDependencyOrder': 'passed',
              'UEFIX64Architecture': 'passed', 'physicalMilestone': hardware['verifiedMilestone'],
              'physicalEvidenceSource': 'recorded user feedback; this command does not test hardware',
              **{key: hardware[key] for key in ['completeInstallationVerified',
                 'independentSSDBootVerified', 'trackpadVerified',
                 'desktopStabilityVerified', 'graphicsAccelerationVerified']}}
    if os.name == 'nt':
        for relative in results:
            result = subprocess.run([str(ROOT / 'tools/ocvalidate.exe'), str(ROOT / relative)],
                                    capture_output=True, check=False)
            require(result.returncode == 0, result.stdout.decode('utf8', 'replace'))
        report['ocvalidate'] = 'OpenCore 1.0.8: both configurations passed'
    else:
        report['ocvalidate'] = 'not run: bundled validator is for Windows'
    output = json.dumps(report, indent=2)
    print(output)
    if args.report:
        args.report.write_text(output + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
