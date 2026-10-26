import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from download_installer import verify_integrity, verify_catalog_xar

def manifest(data):
    head = struct.pack('<4sIBBBxQQQ', b'CNKL', 36, 1, 1, 2, 1, 36, 72)
    chunks = struct.pack('<I32s', len(data), hashlib.sha256(data).digest())
    raw = head + chunks
    return raw + hashlib.sha256(raw).digest()

class IntegrityTests(unittest.TestCase):
    def test_xar_catalog_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fixture.xar'
            toc=b'<xar><toc><checksum style="sha1"><offset>0</offset><size>20</size></checksum></toc></xar>'
            compressed=zlib.compress(toc);digest=hashlib.sha1(compressed).digest()
            p.write_bytes(struct.pack('>IHHQQI',0x78617221,28,1,len(compressed),len(toc),1)+compressed+digest+b'payload')
            self.assertTrue(verify_catalog_xar(p,digest.hex())['verified'])
            self.assertNotEqual(hashlib.sha1(p.read_bytes()).hexdigest(),digest.hex())
            with self.assertRaisesRegex(ValueError,'digest mismatch'):verify_catalog_xar(p,'0'*40)
    def test_correct_and_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, m = Path(tmp)/'package', Path(tmp)/'manifest'
            p.write_bytes(b'fixture');m.write_bytes(manifest(b'fixture'))
            result = verify_integrity(p,m)
            self.assertEqual(result['sha256'], hashlib.sha256(b'fixture').hexdigest())
            self.assertFalse(result['nativeAppleSignatureVerified'])
            p.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'chunk mismatch'): verify_integrity(p,m)
    def test_trailing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,m=Path(tmp)/'package',Path(tmp)/'manifest'
            p.write_bytes(b'fixture-extra');m.write_bytes(manifest(b'fixture'))
            with self.assertRaisesRegex(ValueError,'Trailing'):verify_integrity(p,m)
    def test_manifest_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,m=Path(tmp)/'package',Path(tmp)/'manifest'
            p.write_bytes(b'fixture');m.write_bytes(manifest(b'fixture')[:-1]+b'x')
            with self.assertRaisesRegex(ValueError,'checksum/length'):verify_integrity(p,m)

if __name__ == '__main__': unittest.main()
