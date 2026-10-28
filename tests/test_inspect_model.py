"""Offline model-package contract tests; no network, renderer, or source mutation."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'inspect-model.py'
SPEC = importlib.util.spec_from_file_location('inspect_model', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TETRA = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nf 1 3 2\nf 1 2 4\nf 2 3 4\nf 3 1 4\n'
TRIANGLE = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'


def glb_document():
    binary = struct.pack('<9f3H', 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2)
    doc = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}],
           'bufferViews': [{'buffer': 0, 'byteLength': 36}, {'buffer': 0, 'byteOffset': 36, 'byteLength': 6}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'type': 'VEC3', 'count': 3},
                         {'bufferView': 1, 'componentType': 5123, 'type': 'SCALAR', 'count': 3}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
           'nodes': [{'mesh': 0, 'translation': [5, 2, -1], 'scale': [2, 2, 2]}],
           'scenes': [{'nodes': [0]}], 'scene': 0}
    return doc, binary


def write_glb(path, doc, binary):
    data = json.dumps(doc).encode()
    data += b' ' * (-len(data) % 4)
    binary += b'\x00' * (-len(binary) % 4)
    chunks = struct.pack('<II', len(data), 0x4e4f534a) + data
    chunks += struct.pack('<II', len(binary), 0x004e4942) + binary
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, 12 + len(chunks)) + chunks)


class ModelAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / 'mesh.obj'

    def obj(self, text=TRIANGLE, mtl=None):
        self.model.write_text(text)
        if mtl:
            (self.root / 'mesh.mtl').write_text(mtl)
        return MODULE.audit_model(self.model)

    def codes(self, report):
        return {i['code'] for i in report['issues']}

    def textured(self, texture='texture.png'):
        source = 'mtllib mesh.mtl\n' + TRIANGLE.replace('f 1 2 3', 'vt 0 0\nvt 1 0\nvt 0 1\nusemtl body\nf 1/1 2/2 3/3')
        return self.obj(source, 'newmtl body\nKd 1 0.5 0\nmap_Kd -s 1 1 1 ' + texture + '\n')

    def test_closed_and_open_topology_and_source_untouched(self):
        report = self.obj(TETRA)
        self.assertTrue(report['safe_to_import'])
        self.assertEqual(report['meshes'][0]['boundary_edge_count'], 0)
        self.assertEqual(report['meshes'][0]['vertex_connected_components'], 1)
        self.assertEqual(report['triangle_count'], 4)
        self.assertEqual(self.model.read_text(), TETRA)
        report = self.obj()
        self.assertEqual(report['meshes'][0]['boundary_edge_count'], 3)
        self.assertIn('boundary_edge_count', self.codes(report))
        self.assertFalse(report['identity_verified'])
        self.assertFalse(report['physical_scale_verified'])

    def test_valid_material_dependency_hashes_and_uvs(self):
        (self.root / 'texture.png').write_bytes(b'fixture-only-no-decoder')
        report = self.textured()
        self.assertTrue(report['safe_to_import'])
        self.assertEqual(report['material_count'], 1)
        self.assertEqual(report['meshes'][0]['uv_count'], 3)
        self.assertEqual({d['kind'] for d in report['dependencies']}, {'material_library', 'texture'})
        self.assertTrue(all(len(d['sha256']) == 64 for d in report['dependencies']))

    def test_native_polygon_counts_preserve_quads_before_triangulation(self):
        source = ('v 0 0 0\nv 1 0 0\nv 2 1 0\nv 1 2 0\nv 0 1 0\n'
                  'f 1 2 3\nf 1 2 3 4\nf 1 2 3 4 5\n')
        report = self.obj(source)
        mesh = report['meshes'][0]
        self.assertTrue(report['safe_to_import'])
        self.assertEqual(mesh['source_face_vertex_histogram'], {'3': 1, '4': 1, '5': 1})
        self.assertEqual(mesh['face_count'], 3)
        self.assertEqual(mesh['triangle_count'], 6)
        self.assertAlmostEqual(mesh['quad_face_fraction'], 1 / 3)
        self.assertEqual(self.model.read_text(), source)
        triangle = self.obj()['meshes'][0]
        self.assertEqual(triangle['source_face_vertex_histogram'], {'3': 1})
        self.assertEqual(triangle['quad_face_fraction'], 0)

    def test_missing_texture_or_material_blocks_import(self):
        self.assertIn('missing_dependency', self.codes(self.textured()))
        self.assertFalse(self.textured()['safe_to_import'])
        report = self.obj('usemtl absent\n' + TRIANGLE)
        self.assertIn('missing_material', self.codes(report))

    def test_textured_faces_without_uv_block_import(self):
        (self.root / 'texture.png').write_bytes(b'fixture')
        report = self.obj('mtllib mesh.mtl\nusemtl body\n' + TRIANGLE,
                          'newmtl body\nmap_Kd texture.png\n')
        self.assertIn('textured_faces_missing_uv', self.codes(report))
        self.assertFalse(report['safe_to_import'])

    def test_remote_absolute_encoded_and_parent_paths_are_blocked(self):
        for name in ('https://example.invalid/x.png', '//example.invalid/x.png', '../x.png',
                     '/tmp/x.png', '%2e%2e/x.png', 'C:\\secret.png', 'file:///tmp/x.png'):
            with self.subTest(name=name):
                report = self.textured(name)
                self.assertFalse(report['safe_to_import'])
                self.assertTrue({'unsafe_dependency', 'dependency_outside_root'} & self.codes(report))

    def test_symlink_escape_and_obj_executable_directives_blocked(self):
        with tempfile.TemporaryDirectory() as external:
            secret = Path(external) / 'outside.png'
            secret.write_bytes(b'not read')
            (self.root / 'texture.png').symlink_to(secret)
            report = self.textured()
            self.assertIn('dependency_outside_root', self.codes(report))
            self.assertFalse(any(d['kind'] == 'texture' for d in report['dependencies']))
        report = self.obj(TRIANGLE + 'csh echo unsafe\ncall ../anything.obj\n')
        self.assertIn('executable_obj_directive', self.codes(report))
        self.assertFalse(report['safe_to_import'])

    def test_negative_obj_indices_supported_invalid_indices_and_nonfinite_rejected(self):
        report = self.obj(TRIANGLE.replace('f 1 2 3', 'f -3 -2 -1'))
        self.assertTrue(report['safe_to_import'])
        for face in ('f 0 2 3', 'f 1 2 4', 'f 1///2 2 3'):
            self.assertFalse(self.obj(TRIANGLE.replace('f 1 2 3', face))['safe_to_import'])
        self.assertFalse(self.obj(TRIANGLE.replace('v 0 0 0', 'v nan 0 0'))['safe_to_import'])

    def test_nonmanifold_and_degenerate_reported_without_repair(self):
        report = self.obj(TRIANGLE + 'v 0 0 1\nv 0 0 -1\nf 1 2 4\nf 1 2 5\nf 1 1 2\n')
        mesh = report['meshes'][0]
        self.assertGreater(mesh['nonmanifold_edge_count'], 0)
        self.assertEqual(mesh['repeated_index_faces'], 1)
        self.assertEqual(mesh['zero_area_triangles'], 1)

    def test_glb_static_node_transform_bounds_and_source_untouched(self):
        path = self.root / 'model.glb'
        doc, binary = glb_document()
        write_glb(path, doc, binary)
        original = path.read_bytes()
        report = MODULE.audit_model(path)
        self.assertTrue(report['safe_to_import'])
        self.assertEqual(report['triangle_count'], 1)
        self.assertEqual(report['bounds'], [[5, 2, -1], [7, 4, -1]])
        self.assertEqual(path.read_bytes(), original)

    def test_glb_remote_dependency_does_not_trigger_fetch(self):
        path = self.root / 'model.glb'
        doc, binary = glb_document()
        doc['images'] = [{'uri': 'https://example.invalid/texture.png'}]
        write_glb(path, doc, binary)
        report = MODULE.audit_model(path)
        self.assertFalse(report['safe_to_import'])
        self.assertIn('unsafe_dependency', self.codes(report))
        self.assertEqual(report['dependencies'], [])

    def test_glb_invalid_lengths_accessors_nodes_and_missing_texture_blocked(self):
        path = self.root / 'model.glb'
        original, binary = glb_document()
        for change in ('accessor', 'node', 'view', 'texture', 'extension'):
            doc = copy.deepcopy(original)
            if change == 'accessor':
                doc['accessors'][0]['count'] = 5000001
            elif change == 'node':
                doc['nodes'][0]['children'] = [0]
            elif change == 'view':
                doc['accessors'][0]['bufferView'] = -1
            elif change == 'texture':
                doc['materials'] = [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}]
            else:
                doc['extensionsRequired'] = ['KHR_draco_mesh_compression']
            write_glb(path, doc, binary)
            with self.subTest(change=change):
                self.assertFalse(MODULE.audit_model(path)['safe_to_import'])
        path.write_bytes(path.read_bytes()[:-1])
        self.assertFalse(MODULE.audit_model(path)['safe_to_import'])

    def test_cli_report_cannot_overwrite_input_or_material(self):
        self.obj('mtllib mesh.mtl\nusemtl body\n' + TRIANGLE, 'newmtl body\nKd 1 1 1\n')
        for target in (self.model, self.root / 'mesh.mtl'):
            previous = target.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(self.model), '--output', str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('must not overwrite', result.stderr)
            self.assertEqual(target.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
