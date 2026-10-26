"""Execute the actual Bash guard with fixture-backed diskutil/PlistBuddy.

Run with Python on Linux/WSL. Only the executable paths in a temporary copy are
replaced; production code has no environment-variable bypass for disk checks.
"""
import copy
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest


class GuardTests(unittest.TestCase):
    def test_guard_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = {
                'esp': dict(guid='aaa', offset=1048576, bytes=272629760),
                'protected': dict(guid='bbb', offset=290455552, bytes=273049190400),
                'target': dict(guid='ccc', offset=273339645952, bytes=238770524160),
            }
            plan = dict(specs, disk={'bytes': 512110190592}, usb={
                'disk': {'bytes': 61530439680},
                'esp': dict(guid='ddd', offset=1048576, bytes=8589934592),
                'media': dict(guid='eee', offset=8590983168, bytes=52938407936)})
            (root / 'plan.plist').write_bytes(plistlib.dumps(plan))
            disks = {}
            for whole, items, size in [
                ('disk17', [(specs['esp'], 1), (specs['protected'], 3), (specs['target'], 4)], plan['disk']['bytes']),
                ('disk22', [(plan['usb']['esp'], 1), (plan['usb']['media'], 2)], plan['usb']['disk']['bytes'])
            ]:
                disks[whole] = dict(Internal=False, TotalSize=size, Size=size)
                for spec, number in items:
                    disks[f'{whole}s{number}'] = dict(DiskUUID=spec['guid'], TotalSize=spec['bytes'], Size=spec['bytes'],
                        PartitionMapPartitionOffset=spec['offset'], ParentWholeDisk=whole)
            good = dict(disks=disks, apfs={'Containers': [dict(ContainerReference='disk31',
                PhysicalStores=[{'DeviceIdentifier': 'disk17s4'}])]})
            mock = root / 'mock.py'
            mock.write_text('''#!/usr/bin/env python3
import json,plistlib,sys
from pathlib import Path
mode,*args=sys.argv[1:]
try:
 if mode=='buddy':
  value=plistlib.loads(Path(args[2]).read_bytes())
  for key in args[1].removeprefix('Print :').split(':'):
   value=value[int(key)] if isinstance(value,list) else value[key]
  print(str(value).lower() if isinstance(value,bool) else value)
 else:
  data=json.loads(Path(__file__).with_name('state.json').read_text())
  if args[0]=='list':
   physical=[]
   for name,info in data['disks'].items():
    if 'ParentWholeDisk' not in info:
     physical.append({'DeviceIdentifier':name,'Size':info['Size'],'Partitions':[
      {'DeviceIdentifier':p,'Size':v['Size']} for p,v in data['disks'].items() if v.get('ParentWholeDisk')==name]})
   value={'AllDisks':list(data['disks']),'AllDisksAndPartitions':physical}
  elif args[:2]==['apfs','list']: value=data['apfs']
  else: value=data['disks'][args[-1].removeprefix('/dev/')]
  sys.stdout.buffer.write(plistlib.dumps(value))
except (KeyError,IndexError,ValueError): sys.exit(1)
''')
            source = Path(__file__).with_name('recovery_disk_guard.sh').read_text()
            source = source.replace('/usr/sbin/diskutil', f'python3 {mock} diskutil')
            source = source.replace('/usr/libexec/PlistBuddy', f'python3 {mock} buddy')
            script = root / 'guard.sh'
            script.write_text(source)
            def run(state):
                (root / 'state.json').write_text(json.dumps(state))
                return subprocess.run(['bash', str(script)], env={'PATH': '/usr/bin:/bin',
                    'PLAN': str(root / 'plan.plist')}, capture_output=True, text=True)
            result = run(good)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('disk31', result.stdout)
            # Same physical partition, but unmounted ExFAT volume capacity is 0.
            unmounted = copy.deepcopy(good)
            unmounted['disks']['disk22s2']['TotalSize'] = 0
            result = run(unmounted)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Mounted filesystem capacity can also differ from partition size.
            unmounted['disks']['disk22s2']['TotalSize'] = plan['usb']['media']['bytes'] - 4096
            result = run(unmounted)
            self.assertEqual(result.returncode, 0, result.stderr)
            for label, mutate in [
                ('protected-size', lambda x: x['disks']['disk17s3'].update(Size=1)),
                ('usb-partition-size', lambda x: x['disks']['disk22s2'].update(Size=52938407935)),
                ('target-offset', lambda x: x['disks']['disk17s4'].update(PartitionMapPartitionOffset=1)),
                ('internal-ssd', lambda x: x['disks']['disk17'].update(Internal=True)),
                ('usb-capacity', lambda x: x['disks']['disk22'].update(Size=1)),
                ('usb-parent', lambda x: x['disks']['disk22s2'].update(ParentWholeDisk='disk17')),
                ('ambiguous-guid', lambda x: x['disks'].update(disk99s1=copy.deepcopy(x['disks']['disk17s1']))),
                ('multiple-stores', lambda x: x['apfs']['Containers'][0]['PhysicalStores'].append({'DeviceIdentifier': 'disk0s1'})),
                ('missing-container', lambda x: x['apfs'].update(Containers=[])),
            ]:
                with self.subTest(label=label):
                    altered = copy.deepcopy(good)
                    mutate(altered)
                    result = run(altered)
                    self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
