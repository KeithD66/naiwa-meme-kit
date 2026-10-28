#!/usr/bin/env python3
"""Render an existing GLB to a PNG; never generates or redesigns a character.

The front/side/back names select camera yaw 0/90/180 degrees around the GLB's
Y axis. They do not certify the model's orientation, identity, or provenance.
Run in .venv-render using both installation steps in requirements-render.txt.
macOS needs a usable native
OpenGL/WindowServer session; this script does not install EGL, OSMesa or apps.
"""
import argparse
import ctypes.util
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('glb', nargs='?', type=Path, help='Existing local .glb file')
    parser.add_argument('--self-test', action='store_true', help='Render a plain cube instead of loading a character')
    parser.add_argument('--view', choices=['front', 'side', 'back'], default='front')
    parser.add_argument('--yaw-offset', type=float, default=0, help='Camera yaw offset for a visually calibrated model orientation')
    parser.add_argument('--output', type=Path, help='PNG destination; default assets/private/references/<name>-<view>.png')
    parser.add_argument('--size', type=int, default=768)
    parser.add_argument('--pitch', type=float, default=0, help='Camera elevation in degrees')
    parser.add_argument('--projection', choices=['orthographic', 'perspective'], default='orthographic')
    args = parser.parse_args()
    if bool(args.glb) == args.self_test:
        parser.error('Provide exactly one existing GLB or --self-test')
    if args.glb and (not args.glb.is_file() or args.glb.suffix.lower() != '.glb'):
        parser.error('Input must be an existing local .glb file')
    if not 64 <= args.size <= 2048 or not -80 <= args.pitch <= 80:
        parser.error('size must be 64–2048; pitch must be -80–80')
    name = args.glb.stem if args.glb else 'render-test'
    args.output = args.output or Path('assets/private/references') / (name + '-' + args.view + '.png')
    if args.output.suffix.lower() != '.png':
        parser.error('Output must use .png')
    return args


def main():
    args = arguments()
    pyopengl_version = version('PyOpenGL')
    if sys.version_info >= (3, 12) and tuple(int(part) for part in pyopengl_version.split('.')[:3]) < (3, 1, 10):
        raise RuntimeError('Python 3.12 textured rendering requires the tested PyOpenGL override: '
                           '.venv-render/bin/python -m pip install --no-deps --upgrade PyOpenGL==3.1.10 '
                           '(after installing requirements-render.txt)')
    # Some macOS versions miss framework stubs through find_library.
    original_find_library = ctypes.util.find_library
    if sys.platform == 'darwin' and not original_find_library('OpenGL'):
        ctypes.util.find_library = lambda name: ('/System/Library/Frameworks/OpenGL.framework/OpenGL' if name == 'OpenGL' else original_find_library(name))

    import numpy as np
    # Compatibility spelling used internally by pyrender 0.1.45; process-local.
    if 'infty' not in np.__dict__:
        np.infty = np.inf
    import pyrender
    import trimesh
    from PIL import Image
    from OpenGL.GL import GL_RENDERER, GL_VENDOR, GL_VERSION, glGetString

    source_sha256 = None
    if args.glb:
        digest = hashlib.sha256()
        with args.glb.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        source_sha256 = digest.hexdigest()
        model = trimesh.load_scene(args.glb, process=False)
    else:
        cube = trimesh.creation.box(extents=[1, 1, 1])
        cube.visual.face_colors = [60, 130, 190, 255]
        cube.apply_transform(trimesh.transformations.euler_matrix(.2, .45, 0))
        model = trimesh.Scene(cube)
    if not model.geometry:
        raise RuntimeError('No mesh geometry in input')
    bounds = np.asarray(model.bounds, dtype=float)
    extent = float(np.max(bounds[1] - bounds[0]))
    if not np.isfinite(bounds).all() or extent <= 0:
        raise RuntimeError('Invalid model bounds')
    original_bounds = bounds.tolist()
    # Uniform framing transform only; the source GLB is never rewritten.
    model.apply_translation(-bounds.mean(axis=0))
    model.apply_scale(2.0 / extent)
    scene = pyrender.Scene(bg_color=[1, 1, 1, 0], ambient_light=[.4, .4, .4])
    mesh_count = 0
    textured_mesh_count = 0
    for node in model.graph.nodes_geometry:
        transform, geometry_name = model.graph[node]
        geometry = model.geometry[geometry_name]
        if not isinstance(geometry, trimesh.Trimesh):
            continue
        # Face-color meshes require flat conversion; texture/vertex meshes
        # retain smooth normals and their imported materials when available.
        smooth = geometry.visual.kind != 'face'
        render_mesh = pyrender.Mesh.from_trimesh(geometry, smooth=smooth)
        if any(primitive.material.baseColorTexture is not None for primitive in render_mesh.primitives):
            textured_mesh_count += 1
        scene.add(render_mesh, pose=transform)
        mesh_count += 1
    if not mesh_count:
        raise RuntimeError('No renderable triangle mesh in input')
    yaw_degrees = {'front': 0, 'side': 90, 'back': 180}[args.view] + args.yaw_offset
    yaw, pitch = np.deg2rad([yaw_degrees, args.pitch])
    eye = 3.4 * np.array([np.sin(yaw) * np.cos(pitch), np.sin(pitch), np.cos(yaw) * np.cos(pitch)])
    zaxis = eye / np.linalg.norm(eye)
    xaxis = np.cross([0, 1, 0], zaxis)
    xaxis /= np.linalg.norm(xaxis)
    pose = np.eye(4)
    pose[:3, :3] = np.column_stack([xaxis, np.cross(zaxis, xaxis), zaxis])
    pose[:3, 3] = eye
    if args.projection == 'orthographic':
        camera = pyrender.OrthographicCamera(xmag=1.25, ymag=1.25, znear=.01, zfar=100)
    else:
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 3, znear=.01, zfar=100)
    scene.add(camera, pose=pose)
    scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=2.4), pose=pose)
    renderer = None
    try:
        try:
            renderer = pyrender.OffscreenRenderer(args.size, args.size)
        except IndexError as exc:
            if sys.platform == 'darwin':
                raise RuntimeError('macOS reported no active screen for the hidden OpenGL context. '
                                   'Wake the display / graphical session and render serially; '
                                   'a short caffeinate -u -t 30 assertion can keep the display active. '
                                   'No texture-less fallback was used.') from exc
            raise
        color, depth = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
        if not np.any(depth > 0):
            raise RuntimeError('No visible geometry was rendered')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(color).save(args.output)
        print(json.dumps({'output': str(args.output), 'input': str(args.glb) if args.glb else None,
                          'self_test': args.self_test, 'input_sha256': source_sha256,
                          'view': args.view, 'camera_yaw_degrees': yaw_degrees,
                          'camera_pitch_degrees': args.pitch, 'projection': args.projection,
                          'identity_verified': False, 'mesh_count': mesh_count,
                          'textured_mesh_count': textured_mesh_count,
                          'pyopengl_version': pyopengl_version,
                          'input_bounds': original_bounds, 'shape': list(color.shape),
                          'visible_pixels': int(np.count_nonzero(depth)),
                          'renderer': glGetString(GL_RENDERER).decode(),
                          'vendor': glGetString(GL_VENDOR).decode(),
                          'opengl': glGetString(GL_VERSION).decode()}, ensure_ascii=False))
    finally:
        if renderer is not None:
            renderer.delete()


if __name__ == '__main__':
    main()
