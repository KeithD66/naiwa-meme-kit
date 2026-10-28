#!/usr/bin/env python3
"""Read-only, offline OBJ/MTL/GLB audit before import into a renderer.

Only this parser reads files; no model code, material commands, network requests,
or external geometry loaders are run. Relative dependencies must resolve inside
--root (default: model directory), including through symlinks. This is a technical
audit, never character identity, physical-scale, rigging, or rights approval.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import shlex
import struct
import sys
from urllib.parse import unquote, urlsplit


class AuditError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def words(line):
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.escape = ''
    lexer.commenters = '#'
    return list(lexer)


def topology(vertices, faces):
    """Index topology, without welding vertices or changing source geometry."""
    parent = list(range(len(vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edges, used = Counter(), set()
    polygon_sizes = Counter()
    repeated = zero_area = triangles = 0
    for face in faces:
        polygon_sizes[len(face)] += 1
        used.update(face)
        for v in face[1:]:
            parent[find(v)] = find(face[0])
        if len(set(face)) != len(face):
            repeated += 1
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))] += 1
        for i in range(1, len(face) - 1):
            triangles += 1
            a, b, c = (vertices[j] for j in (face[0], face[i], face[i + 1]))
            u, v = [b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)]
            cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            if sum(n*n for n in cross) == 0:
                zero_area += 1
    bounds = [[min(v[i] for v in vertices) for i in range(3)],
              [max(v[i] for v in vertices) for i in range(3)]] if vertices else None
    return {'vertex_count': len(vertices), 'face_count': len(faces), 'triangle_count': triangles,
            'source_face_vertex_histogram': {str(size): count for size, count in sorted(polygon_sizes.items())},
            'quad_face_fraction': polygon_sizes[4] / len(faces) if faces else 0.0,
            'bounds': bounds, 'extent': [bounds[1][i]-bounds[0][i] for i in range(3)] if bounds else None,
            'vertex_connected_components': len({find(i) for i in used}),
            'unused_vertex_count': len(vertices)-len(used), 'edge_count': len(edges),
            'boundary_edge_count': sum(n == 1 for n in edges.values()),
            'nonmanifold_edge_count': sum(n > 2 for n in edges.values()),
            'repeated_index_faces': repeated, 'zero_area_triangles': zero_area,
            'topology_basis': 'source vertex indices; no welding, repair, or retopology'}


class Auditor:
    def __init__(self, model, root=None):
        self.model = Path(model).resolve()
        self.root = Path(root).resolve() if root else self.model.parent
        self.issues = []
        self.dependencies = {}

    def issue(self, severity, code, detail):
        self.issues.append({'severity': severity, 'code': code, 'detail': str(detail)})

    def dependency(self, name, base, kind):
        """Never open absolute, remote, traversal, or symlink-escaped dependencies."""
        decoded = unquote(name)
        if (not name or '\x00' in name or '\\' in name or urlsplit(decoded).scheme
                or urlsplit(decoded).netloc or PureWindowsPath(decoded).drive
                or decoded.startswith('/') or '?' in name or '#' in name):
            self.issue('error', 'unsafe_dependency', name)
            return None
        path = (base / decoded).resolve()
        if not path.is_relative_to(self.root):
            self.issue('error', 'dependency_outside_root', name)
            return None
        if not path.is_file():
            self.issue('error', 'missing_dependency', name)
            return None
        relative = path.relative_to(self.root).as_posix()
        if relative not in self.dependencies:
            data = path.read_bytes()
            self.dependencies[relative] = {'path': relative, 'kind': kind, 'bytes': len(data), 'sha256': sha256(data)}
        return path

    def inspect(self):
        if not self.model.is_relative_to(self.root):
            raise AuditError('Model itself is outside --root')
        data = self.model.read_bytes()
        report = {'schema_version': 1, 'input': str(self.model), 'root': str(self.root),
                  'sha256': sha256(data), 'bytes': len(data), 'format': self.model.suffix.lower().lstrip('.'),
                  'identity_verified': False, 'physical_scale_verified': False,
                  'rigging_verified': False, 'orientation': 'uncalibrated',
                  'units': 'unknown; do not infer centimetres from numerical bounds', 'meshes': []}
        try:
            if self.model.suffix.lower() == '.obj':
                report.update(self.obj(data))
            elif self.model.suffix.lower() == '.glb':
                report.update(self.glb(data))
            else:
                raise AuditError('Only existing local .obj and .glb files are supported')
            if not report['meshes'] or not sum(m['triangle_count'] for m in report['meshes']):
                self.issue('error', 'empty_geometry', 'No decoded triangle geometry')
            for mesh in report['meshes']:
                for field in ('boundary_edge_count', 'nonmanifold_edge_count', 'repeated_index_faces', 'zero_area_triangles'):
                    if mesh[field]:
                        self.issue('warning', field, f"{mesh.get('name', 'mesh')}: {mesh[field]}")
                if mesh['extent'] and max(mesh['extent']) == 0:
                    self.issue('error', 'zero_extent', mesh.get('name', 'mesh'))
        except (AuditError, ValueError, KeyError, IndexError, TypeError, AttributeError,
                OverflowError, RecursionError, struct.error, UnicodeError) as exc:
            self.issue('error', 'invalid_model', exc)
        report['dependencies'] = list(self.dependencies.values())
        report['issues'] = self.issues
        report['status'] = 'blocked' if any(i['severity'] == 'error' for i in self.issues) else ('warnings' if self.issues else 'ok')
        report['safe_to_import'] = report['status'] != 'blocked'
        report['mesh_count'] = len(report['meshes'])
        report['triangle_count'] = sum(m['triangle_count'] for m in report['meshes'])
        return report

    def obj(self, data):
        vertices, faces, used, libraries = [], [], set(), []
        vt = vn = objects = groups = 0
        referenced_uv = referenced_normals = faces_without_material = faces_without_uv = 0
        missing_uv_by_material = Counter()
        active_material = None
        for lineno, line in enumerate(data.decode('utf-8-sig').splitlines(), 1):
            token = words(line)
            if not token:
                continue
            command, arg = token[0], token[1:]
            if command == 'v':
                value = [float(v) for v in arg[:3]]
                if len(value) != 3 or not all(math.isfinite(v) for v in value):
                    raise AuditError(f'Invalid vertex on OBJ line {lineno}')
                vertices.append(value)
            elif command == 'vt':
                if not arg or not all(math.isfinite(float(v)) for v in arg):
                    raise AuditError(f'Invalid UV on OBJ line {lineno}')
                vt += 1
            elif command == 'vn':
                if len(arg) != 3 or not all(math.isfinite(float(v)) for v in arg):
                    raise AuditError(f'Invalid normal on OBJ line {lineno}')
                vn += 1
            elif command == 'f':
                if len(arg) < 3:
                    raise AuditError(f'Face has fewer than 3 vertices on OBJ line {lineno}')
                face, with_uv = [], True
                for vertex in arg:
                    index = vertex.split('/')
                    if len(index) > 3:
                        raise AuditError(f'Invalid face index on OBJ line {lineno}')
                    for offset, total in enumerate((len(vertices), vt, vn)):
                        if offset >= len(index) or not index[offset]:
                            if offset == 0:
                                raise AuditError('Face missing a vertex index')
                            if offset == 1:
                                with_uv = False
                            continue
                        n = int(index[offset])
                        resolved = n - 1 if n > 0 else total + n
                        if n == 0 or not 0 <= resolved < total:
                            raise AuditError(f'Out-of-range face index on OBJ line {lineno}')
                        if offset == 0:
                            face.append(resolved)
                        elif offset == 1:
                            referenced_uv += 1
                        else:
                            referenced_normals += 1
                faces.append(face)
                faces_without_uv += not with_uv
                faces_without_material += active_material is None
                if not with_uv:
                    missing_uv_by_material[active_material] += 1
            elif command == 'mtllib':
                libraries.extend(arg)
            elif command == 'usemtl':
                active_material = ' '.join(arg)
                used.add(active_material)
            elif command == 'o':
                objects += 1
            elif command == 'g':
                groups += 1
            elif command in {'call', 'csh'}:
                self.issue('error', 'executable_obj_directive', f'{command} at line {lineno}')
            elif command not in {'s', 'vp', 'l', 'p'}:
                self.issue('warning', 'unsupported_obj_directive', f'{command} at line {lineno}')
        materials = {}
        for library in libraries:
            path = self.dependency(library, self.model.parent, 'material_library')
            if path:
                materials.update(self.mtl(path))
        for name in sorted(used - set(materials)):
            self.issue('error', 'missing_material', name)
        if not materials:
            self.issue('warning', 'no_materials', 'Untextured appearance may not preserve the reference')
        elif faces_without_material:
            self.issue('warning', 'faces_without_material', faces_without_material)
        for name, material in materials.items():
            if material['texture_maps'] and missing_uv_by_material[name]:
                self.issue('error', 'textured_faces_missing_uv', f'{name}: {missing_uv_by_material[name]}')
        mesh = topology(vertices, faces)
        mesh.update({'name': self.model.stem, 'uv_count': vt, 'normal_count': vn,
                     'referenced_uv_indices': referenced_uv, 'referenced_normal_indices': referenced_normals,
                     'faces_without_material': faces_without_material, 'faces_without_uv': faces_without_uv})
        return {'meshes': [mesh], 'object_declarations': objects, 'group_declarations': groups,
                'material_count': len(materials), 'materials': list(materials.values()),
                'bounds': mesh['bounds'], 'coordinate_convention': 'unknown; visually calibrate up and front'}

    def mtl(self, path):
        result, current = {}, None
        maps = {'map_ka', 'map_kd', 'map_ks', 'map_ns', 'map_d', 'bump', 'map_bump', 'disp', 'decal', 'norm',
                'map_pr', 'map_pm', 'map_ps', 'map_ke', 'map_ao', 'refl'}
        for lineno, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            token = words(line)
            if not token:
                continue
            command, arg = token[0], token[1:]
            if command == 'newmtl':
                name = ' '.join(arg)
                current = result.setdefault(name, {'name': name, 'texture_maps': []})
            elif command.lower() in maps:
                if current is None:
                    raise AuditError(f'Texture map before material in {path.name}:{lineno}')
                texture = self.map_filename(arg)
                file = self.dependency(texture, path.parent, 'texture')
                current['texture_maps'].append({'channel': command, 'reference': texture,
                                                'path': file.relative_to(self.root).as_posix() if file else None})
            elif current is not None and command.lower() in {'kd', 'ka', 'ks', 'ke', 'd', 'tr', 'ns', 'ni', 'illum', 'pr', 'pm'}:
                values = [float(v) for v in arg]
                if not all(math.isfinite(v) for v in values):
                    raise AuditError(f'Non-finite material value in {path.name}:{lineno}')
                current[command] = values
        return result

    @staticmethod
    def map_filename(args):
        args = list(args)
        fixed = {'-blendu': 1, '-blendv': 1, '-cc': 1, '-clamp': 1, '-texres': 1,
                 '-bm': 1, '-imfchan': 1, '-type': 1, '-mm': 2, '-boost': 1}
        while args and args[0].startswith('-'):
            flag = args.pop(0)
            if flag in {'-o', '-s', '-t'}:
                count = 0
                while args and count < 3:
                    try:
                        float(args[0])
                    except ValueError:
                        break
                    args.pop(0)
                    count += 1
                if not count:
                    raise AuditError(f'Missing numeric values for MTL {flag}')
            elif flag in fixed:
                count = fixed[flag]
                if len(args) <= count:
                    raise AuditError(f'Missing option or texture filename for MTL {flag}')
                del args[:count]
            else:
                raise AuditError(f'Unsupported MTL texture option {flag}')
        if not args:
            raise AuditError('Missing texture filename')
        return ' '.join(args)

    def glb(self, data):
        if len(data) < 20:
            raise AuditError('Truncated GLB header')
        magic, version, length = struct.unpack_from('<4sII', data)
        if magic != b'glTF' or version != 2 or length != len(data):
            raise AuditError('Invalid GLB 2 header or declared length')
        chunks, offset = [], 12
        while offset < len(data):
            size, kind = struct.unpack_from('<II', data, offset)
            offset += 8
            if size % 4 or offset + size > len(data):
                raise AuditError('Invalid GLB chunk length')
            chunks.append((kind, data[offset:offset + size]))
            offset += size
        if not chunks or chunks[0][0] != 0x4e4f534a:
            raise AuditError('GLB first chunk must be JSON')
        doc = json.loads(chunks[0][1].rstrip(b' \x00'))
        if not isinstance(doc, dict) or doc.get('asset', {}).get('version') != '2.0':
            raise AuditError('GLB JSON must describe a glTF 2.0 asset')
        binary = [value for kind, value in chunks if kind == 0x004e4942]
        if len(binary) > 1:
            raise AuditError('Multiple BIN chunks')
        buffers = []
        for i, buffer in enumerate(doc.get('buffers', [])):
            if 'uri' in buffer:
                path = self.dependency(buffer['uri'], self.model.parent, 'buffer')
                value = path.read_bytes() if path else b''
            else:
                value = binary[0] if i == 0 and binary else b''
            if len(value) < int(buffer['byteLength']):
                self.issue('error', 'missing_buffer_bytes', i)
            buffers.append(value)
        for i, image in enumerate(doc.get('images', [])):
            if 'uri' in image:
                self.dependency(image['uri'], self.model.parent, 'texture')
            elif 'bufferView' in image:
                self.buffer_view(doc, buffers, image['bufferView'])
            else:
                self.issue('error', 'missing_image_data', i)
        for extension in doc.get('extensionsRequired', []):
            self.issue('error', 'unsupported_required_gltf_extension', extension)
        materials = doc.get('materials', [])
        for material in materials:
            references = [v for k, v in material.items() if k.endswith('Texture')]
            references.extend(v for k, v in material.get('pbrMetallicRoughness', {}).items() if k.endswith('Texture'))
            for reference in references:
                if not isinstance(reference, dict) or not 0 <= reference.get('index', -1) < len(doc.get('textures', [])):
                    self.issue('error', 'missing_material_texture', reference)
        for texture in doc.get('textures', []):
            if not 0 <= texture.get('source', -1) < len(doc.get('images', [])):
                self.issue('error', 'missing_texture_image', texture.get('source'))
        meshes, geometry = [], []
        for mesh_i, mesh in enumerate(doc.get('meshes', [])):
            for primitive_i, primitive in enumerate(mesh.get('primitives', [])):
                attrs = primitive.get('attributes', {})
                if 'POSITION' not in attrs:
                    raise AuditError('Primitive has no POSITION accessor')
                position_accessor = doc['accessors'][attrs['POSITION']]
                if position_accessor['componentType'] != 5126 or position_accessor['type'] != 'VEC3':
                    raise AuditError('POSITION must be a float VEC3 accessor')
                vertices = self.accessor(doc, buffers, attrs['POSITION'])
                if not vertices or any(len(v) != 3 or not all(math.isfinite(x) for x in v) for v in vertices):
                    raise AuditError('Invalid primitive positions')
                if 'indices' in primitive:
                    index_accessor = doc['accessors'][primitive['indices']]
                    if index_accessor['componentType'] not in (5121, 5123, 5125) or index_accessor['type'] != 'SCALAR':
                        raise AuditError('Triangle indices must be unsigned integer SCALAR accessors')
                indices = ([int(v[0]) for v in self.accessor(doc, buffers, primitive['indices'])]
                           if 'indices' in primitive else list(range(len(vertices))))
                if any(i < 0 or i >= len(vertices) for i in indices):
                    raise AuditError('Out-of-range primitive vertex index')
                mode = primitive.get('mode', 4)
                if mode == 4 and len(indices) % 3 == 0:
                    faces = [indices[i:i+3] for i in range(0, len(indices), 3)]
                elif mode == 5:
                    faces = [([indices[i+1], indices[i], indices[i+2]] if i % 2 else indices[i:i+3])
                             for i in range(len(indices)-2)]
                elif mode == 6:
                    faces = [[indices[0], indices[i], indices[i+1]] for i in range(1, len(indices)-1)]
                else:
                    raise AuditError(f'Unsupported primitive mode or index count: {mode}')
                material = primitive.get('material')
                if material is not None and not 0 <= material < len(materials):
                    raise AuditError('Primitive material out of range')
                for attribute, accessor_index in attrs.items():
                    if not isinstance(accessor_index, int) or not 0 <= accessor_index < len(doc['accessors']):
                        raise AuditError(f'Invalid {attribute} accessor index')
                    if doc['accessors'][accessor_index]['count'] != len(vertices):
                        raise AuditError(f'{attribute} attribute count does not match POSITION')
                    # Validate storage bounds, including attributes not used for topology.
                    if attribute != 'POSITION':
                        self.accessor(doc, buffers, accessor_index)
                if material is not None:
                    pbr = materials[material].get('pbrMetallicRoughness', {})
                    if 'baseColorTexture' in pbr and 'TEXCOORD_0' not in attrs:
                        self.issue('error', 'textured_faces_missing_uv', f'mesh {mesh_i}, primitive {primitive_i}')
                item = topology(vertices, faces)
                item.update({'name': f'mesh-{mesh_i}-primitive-{primitive_i}', 'material_index': material,
                             'has_uv': 'TEXCOORD_0' in attrs, 'has_normals': 'NORMAL' in attrs})
                meshes.append(item)
                geometry.append((mesh_i, vertices))
        world_vertices = self.world_vertices(doc, geometry)
        bounds = [[min(v[i] for v in world_vertices) for i in range(3)],
                  [max(v[i] for v in world_vertices) for i in range(3)]] if world_vertices else None
        return {'meshes': meshes, 'material_count': len(materials), 'texture_count': len(doc.get('textures', [])),
                'materials': materials,
                'image_count': len(doc.get('images', [])), 'skin_count': len(doc.get('skins', [])),
                'animation_count': len(doc.get('animations', [])), 'bounds': bounds,
                'coordinate_convention': 'glTF nominal +Y up, metres; real-world scale/front still unverified'}

    @staticmethod
    def buffer_view(doc, buffers, index):
        if not isinstance(index, int) or not 0 <= index < len(doc.get('bufferViews', [])):
            raise AuditError('Invalid buffer view index')
        view = doc['bufferViews'][index]
        if not isinstance(view['buffer'], int) or not 0 <= view['buffer'] < len(buffers):
            raise AuditError('Invalid buffer index')
        value = buffers[view['buffer']]
        start, count = view.get('byteOffset', 0), view['byteLength']
        if start < 0 or count < 0 or start + count > len(value):
            raise AuditError('Buffer view outside buffer')
        return view, value[start:start+count]

    def accessor(self, doc, buffers, index):
        if not isinstance(index, int) or index < 0:
            raise AuditError('Invalid accessor index')
        accessor = doc['accessors'][index]
        if 'sparse' in accessor or 'bufferView' not in accessor:
            raise AuditError('Sparse or implicit accessors unsupported by this audit')
        view, value = self.buffer_view(doc, buffers, accessor['bufferView'])
        code, size = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2),
                      5125: ('I', 4), 5126: ('f', 4)}[accessor['componentType']]
        width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[accessor['type']]
        count, start = accessor['count'], accessor.get('byteOffset', 0)
        stride = view.get('byteStride', size*width)
        if (not isinstance(count, int) or not 0 <= count <= 5000000 or start < 0 or stride < size*width
                or (count and start + (count-1)*stride + size*width > len(value))):
            raise AuditError('Accessor outside buffer view or inspection size limit')
        return [struct.unpack_from('<'+code*width, value, start+i*stride) for i in range(count)]

    @staticmethod
    def world_vertices(doc, geometry):
        """Evaluate static node TRS/matrix; never apply skinning or animations."""
        identity = [[float(i == j) for j in range(4)] for i in range(4)]

        def multiply(a, b):
            return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

        def local(node):
            if 'matrix' in node:
                v = node['matrix']
                if len(v) != 16:
                    raise AuditError('Invalid node matrix')
                return [[v[j*4+i] for j in range(4)] for i in range(4)]
            x, y, z, w = node.get('rotation', [0, 0, 0, 1])
            s, t = node.get('scale', [1, 1, 1]), node.get('translation', [0, 0, 0])
            r = [[1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w],
                 [2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w],
                 [2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y]]
            return [[r[i][j]*s[j] if j < 3 else t[i] for j in range(4)] for i in range(3)] + [[0, 0, 0, 1]]

        nodes = doc.get('nodes', [])
        if not nodes:
            return [v for _, vertices in geometry for v in vertices]
        children = {c for n in nodes for c in n.get('children', [])}
        scenes = doc.get('scenes', [])
        if scenes and (not isinstance(doc.get('scene', 0), int) or not 0 <= doc.get('scene', 0) < len(scenes)):
            raise AuditError('Invalid active scene index')
        roots = scenes[doc.get('scene', 0)].get('nodes', []) if scenes else [i for i in range(len(nodes)) if i not in children]
        result = []

        def visit(index, transform, ancestors):
            if index in ancestors or not 0 <= index < len(nodes):
                raise AuditError('Cyclic or invalid node hierarchy')
            node = nodes[index]
            transform = multiply(transform, local(node))
            if not all(math.isfinite(v) for row in transform for v in row):
                raise AuditError('Non-finite node transform')
            for mesh_i, vertices in geometry:
                if mesh_i == node.get('mesh'):
                    result.extend([[sum(transform[i][j]*list(v + (1,))[j] for j in range(4)) for i in range(3)] for v in vertices])
            for child in node.get('children', []):
                visit(child, transform, ancestors | {index})
        for index in roots:
            visit(index, identity, set())
        if not result:
            raise AuditError('No mesh is instanced in active scene')
        return result


def audit_model(model, root=None):
    return Auditor(model, root).inspect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--root', type=Path, help='Allowed extracted-package root; defaults to model directory')
    parser.add_argument('--output', type=Path, help='Optional JSON report (must not overwrite an input/dependency)')
    args = parser.parse_args()
    try:
        report = audit_model(args.model, args.root)
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            output = args.output.resolve()
            protected = {Path(report['input'])} | {Path(report['root']) / d['path'] for d in report['dependencies']}
            if output in protected:
                raise AuditError('Report must not overwrite the model or any dependency')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding='utf-8')
        print(rendered, end='')
        return 2 if report['status'] == 'blocked' else 0
    except (OSError, AuditError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
