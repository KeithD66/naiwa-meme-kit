"""Offline cache contracts; never opens a graphics context."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('reference_pack_tool',Path(__file__).resolve().parents[1]/'scripts/render-character-pack.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PackCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.settings={'size':768,'yaw_offset':0,'no_turntable':True}
        self.views=[]
        for i in range(24):
            p=self.root/(str(i)+'.png');p.write_bytes(b'image'+str(i).encode())
            m=self.root/(str(i)+'-mask.png');m.write_bytes(b'mask'+str(i).encode())
            label,yaw=MODULE.VIEWS[i%8];pitch=[0,15,-15][i//8]
            self.views.append({'view':label,'pitch_degrees':pitch,'yaw_degrees':yaw,'path':str(p),'sha256':MODULE.sha256(p),'mask_path':str(m),'mask_sha256':MODULE.sha256(m)})
        p=self.root/'contact-sheet.jpg';p.write_bytes(b'contact')
        self.data={'source_model_sha256':'modelhash','settings':self.settings,'views':self.views,'artifact_hashes':{'contact-sheet.jpg':MODULE.sha256(p)}}
        self.save()

    def save(self):
        (self.root/'reference-pack.json').write_text(json.dumps(self.data))

    def test_completed_pack_reuses_without_renderer(self):
        self.assertTrue(MODULE.verify_cached_pack(self.root,'modelhash',self.settings))

    def test_model_or_camera_change_invalidates_existing_pack(self):
        for model,settings in [('other',self.settings),('modelhash',{'size':512})]:
            with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,model,settings)

    def test_changed_or_missing_reference_is_not_reused(self):
        p=Path(self.views[0]['path']);p.write_bytes(b'changed')
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)
        p.unlink()
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)

    def test_partial_pack_or_changed_preview_is_not_reused(self):
        self.data['views']=self.views[:-1];self.save()
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)
        self.data['views']=self.views;self.save()
        (self.root/'contact-sheet.jpg').write_bytes(b'bad')
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)

    def test_duplicate_angles_and_missing_required_previews_are_not_reused(self):
        last=self.data['views'][-1]
        original=dict(last)
        last.update(view='front',pitch_degrees=0,yaw_degrees=0);self.save()
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)
        last.update(original)
        other=self.root/'other.jpg';other.write_bytes(b'other')
        self.data['artifact_hashes']={'other.jpg':MODULE.sha256(other)};self.save()
        with self.assertRaises(ValueError):MODULE.verify_cached_pack(self.root,'modelhash',self.settings)


if __name__=='__main__':unittest.main()
