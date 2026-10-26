import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

try:
    from backup_ranges import backup
except ImportError:
    backup = None

@unittest.skipIf(backup is None, 'Requires Python 3.14 native compression.zstd')
class BackupTests(unittest.TestCase):
    def test_offset_source_unchanged_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=os.urandom(17*1024*1024+512)
            source=root/'source';source.write_bytes(data)
            before=hashlib.sha256(data).hexdigest()
            result=backup(str(source),512,len(data)-512,root/'backup.zst',root/'progress.json')
            self.assertEqual(result['rawSha256'],hashlib.sha256(data[512:]).hexdigest())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            self.assertEqual(result['decompressedVerification'],'passed')
            with self.assertRaisesRegex(ValueError,'overwrite'):
                backup(str(source),512,len(data)-512,root/'backup.zst',root/'progress.json')
    def test_short_source_is_never_finalized(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.write_bytes(b'short')
            with self.assertRaisesRegex(IOError,'end of source'):
                backup(str(source),0,100,root/'backup.zst',root/'progress.json')
            self.assertFalse((root/'backup.zst').exists())

if __name__ == '__main__':unittest.main()
