#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render repeatable multi-angle references and a CAMERA orbit from one static GLB."""
import argparse
import ctypes.util
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]
VIEWS = [('front',0),('front-right',45),('right',90),('back-right',135),('back',180),('back-left',225),('left',270),('front-left',315)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_cached_pack(output, model_hash, settings):
    manifest=output/'reference-pack.json'
    if not manifest.is_file():
        return False
    data=json.loads(manifest.read_text())
    if data.get('source_model_sha256')!=model_hash or data.get('settings')!=settings:
        raise ValueError('Existing pack uses another model/settings; use a new version directory or --force')
    expected={(label,pitch) for label,_ in VIEWS for pitch in [0,15,-15]}
    observed=[(v.get('view'),v.get('pitch_degrees')) for v in data.get('views',[])]
    if len(observed)!=24 or set(observed)!=expected:
        raise ValueError('Cached pack must contain 24 unique view/pitch combinations')
    used_paths=set()
    for view in data.get('views',[]):
        yaw=dict(VIEWS)[view['view']]+settings.get('yaw_offset',0)
        if not math.isclose(view.get('yaw_degrees',float('inf')),yaw,abs_tol=1e-8):
            raise ValueError('Cached view yaw disagrees with its label/settings')
        for path_key,hash_key in [('path','sha256'),('mask_path','mask_sha256')]:
            path=Path(view[path_key])
            if output.resolve() not in path.resolve().parents or path.resolve() in used_paths:
                raise ValueError('Cached view path escapes or reuses another reference file')
            used_paths.add(path.resolve())
            if not path.is_file() or sha256(path)!=view[hash_key]:
                raise ValueError('Cached reference bytes changed; inspect before --force')
    required={'contact-sheet.jpg'}
    if not settings.get('no_turntable',False):required.add('turntable.mp4')
    if not required.issubset(data.get('artifact_hashes',{})):
        raise ValueError('Cached pack is missing required preview checksums')
    for name,digest in data['artifact_hashes'].items():
        path=output/name
        if output.resolve() not in path.resolve().parents:
            raise ValueError('Cached preview path escapes the pack')
        if not path.is_file() or sha256(path)!=digest:
            raise ValueError('Cached preview bytes changed; inspect before --force')
    return True


def camera_pose(np, yaw_degrees, pitch_degrees, target, distance):
    yaw, pitch = np.deg2rad([yaw_degrees, pitch_degrees])
    eye = target + distance * np.array([np.sin(yaw)*np.cos(pitch), np.sin(pitch), np.cos(yaw)*np.cos(pitch)])
    z = (eye-target) / np.linalg.norm(eye-target)
    x = np.cross([0,1,0],z); x /= np.linalg.norm(x)
    pose = np.eye(4)
    pose[:3,:3] = np.column_stack([x,np.cross(z,x),z])
    pose[:3,3] = eye
    return pose


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model',type=Path)
    parser.add_argument('--character-id',required=True)
    parser.add_argument('--version-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--size',type=int,default=768)
    parser.add_argument('--yaw-offset',type=float,default=0)
    parser.add_argument('--turntable-seconds',type=float,default=6)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--no-turntable',action='store_true')
    parser.add_argument('--force',action='store_true',help='Explicitly rebuild local renders; never creates a new API model')
    args=parser.parse_args()
    if not args.model.is_file() or args.model.suffix.lower()!='.glb':parser.error('Existing local GLB required')
    if not 256<=args.size<=1536 or not 1<=args.turntable_seconds<=12 or not 12<=args.fps<=30:parser.error('Invalid render size/timing')
    if not args.no_turntable and args.size%2:parser.error('H.264 turntable needs an even canvas size')
    settings={'character_id':args.character_id,'version_id':args.version_id,'size':args.size,'yaw_offset':args.yaw_offset,'turntable_seconds':args.turntable_seconds,'fps':args.fps,'no_turntable':args.no_turntable}
    source_hash=sha256(args.model)
    if not args.force and verify_cached_pack(args.output,source_hash,settings):
        print(json.dumps({'output':str(args.output),'reused':True,'source_unchanged':True}));return
    args.output.mkdir(parents=True,exist_ok=True)
    # Audit prior to importing assets or decoding their dependencies.
    audit_path=args.output/'pre-render-audit.json'
    audit=subprocess.run([sys.executable,str(ROOT/'scripts/inspect-model.py'),str(args.model),'--root',str(args.model.parent),'--output',str(audit_path)],capture_output=True,text=True)
    if audit.returncode!=0:raise RuntimeError('Model audit blocked import; see '+str(audit_path))
    if sys.version_info>=(3,12) and tuple(map(int,version('PyOpenGL').split('.')[:3]))<(3,1,10):raise RuntimeError('Use the tested PyOpenGL 3.1.10 override')
    original=ctypes.util.find_library
    if sys.platform=='darwin' and not original('OpenGL'):
        ctypes.util.find_library=lambda name: '/System/Library/Frameworks/OpenGL.framework/OpenGL' if name=='OpenGL' else original(name)
    import numpy as np
    if 'infty' not in np.__dict__:np.infty=np.inf
    import trimesh,pyrender
    from PIL import Image,ImageDraw,ImageFont
    scene_data=trimesh.load_scene(args.model,process=False)
    bounds=np.asarray(scene_data.bounds,dtype=float)
    if not np.isfinite(bounds).all():raise RuntimeError('Non-finite model bounds')
    target=bounds.mean(axis=0)
    extent=bounds[1]-bounds[0]
    # One framing scale for ALL directions/pitches; no frame-by-frame resizing.
    radius=float(np.linalg.norm(extent)/2)
    half_frame=radius*1.18
    scene=pyrender.Scene(bg_color=[1,1,1,0],ambient_light=[.45,.45,.45])
    texture_meshes=0
    for node in scene_data.graph.nodes_geometry:
        transform,key=scene_data.graph[node]
        geometry=scene_data.geometry[key]
        if not isinstance(geometry,trimesh.Trimesh):continue
        mesh=pyrender.Mesh.from_trimesh(geometry,smooth=geometry.visual.kind!='face')
        texture_meshes+=int(any(p.material.baseColorTexture is not None for p in mesh.primitives))
        scene.add(mesh,pose=transform)
    camera=pyrender.OrthographicCamera(xmag=half_frame,ymag=half_frame,znear=.01,zfar=max(100,radius*20))
    cam_node=scene.add(camera,pose=np.eye(4))
    # The key light moves with the camera for a comparable inspection view.
    light_node=scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=2.2),pose=np.eye(4))
    renderer=None
    views=[]
    try:
        renderer=pyrender.OffscreenRenderer(args.size,args.size)
        for pitch in [0,15,-15]:
            folder=args.output/('level' if pitch==0 else 'above' if pitch>0 else 'below')
            folder.mkdir(parents=True,exist_ok=True)
            for label,yaw in VIEWS:
                pose=camera_pose(np,yaw+args.yaw_offset,pitch,target,max(4*radius,3))
                scene.set_pose(cam_node,pose=pose);scene.set_pose(light_node,pose=pose)
                rgba,depth=renderer.render(scene,flags=pyrender.RenderFlags.RGBA)
                if not np.any(depth>0):raise RuntimeError('Blank view: '+label)
                path=folder/(label+'.png')
                Image.fromarray(rgba).save(path)
                mask=folder/(label+'-mask.png')
                Image.fromarray(np.where(depth>0,255,0).astype('uint8')).save(mask)
                views.append({'view':label,'pitch_degrees':pitch,'yaw_degrees':yaw+args.yaw_offset,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mask_path':str(mask),'mask_sha256':hashlib.sha256(mask.read_bytes()).hexdigest(),'camera_to_world':pose.tolist(),'visible_pixels':int(np.count_nonzero(depth))})
            print('rendered pitch',pitch,flush=True)
        if not args.no_turntable:
            # This orbit is a QA preview of a STATIC mesh, never a rigged action.
            video=args.output/'turntable.mp4'
            command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',str(args.size)+'x'+str(args.size),'-r',str(args.fps),'-i','-','-an','-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
            encoder=subprocess.Popen(command,stdin=subprocess.PIPE)
            frames=round(args.turntable_seconds*args.fps)
            try:
                for n in range(frames):
                    pose=camera_pose(np,360*n/frames+args.yaw_offset,8,target,max(4*radius,3))
                    scene.set_pose(cam_node,pose=pose);scene.set_pose(light_node,pose=pose)
                    rgba,depth=renderer.render(scene,flags=pyrender.RenderFlags.RGBA)
                    image=Image.fromarray(rgba)
                    background=Image.new('RGBA',image.size,(242,242,239,255))
                    background.alpha_composite(image)
                    encoder.stdin.write(background.convert('RGB').tobytes())
            finally:encoder.stdin.close()
            if encoder.wait()!=0:raise RuntimeError('Turntable encoder failed')
        # Contact sheet shows only real rendered pixels and labels, no new character art.
        thumb=256
        sheet=Image.new('RGB',(thumb*4,(thumb+30)*2),(242,242,239))
        draw=ImageDraw.Draw(sheet)
        for n,(label,_) in enumerate(VIEWS):
            path=args.output/'level'/(label+'.png')
            image=Image.open(path).convert('RGBA');image.thumbnail((thumb,thumb))
            x=(n%4)*thumb;y=(n//4)*(thumb+30)
            sheet.paste(image,(x+(thumb-image.width)//2,y+(thumb-image.height)//2),image)
            draw.text((x+8,y+thumb+3),label,fill=(25,28,35),font=ImageFont.load_default(size=16))
        sheet.save(args.output/'contact-sheet.jpg',quality=92)
    finally:
        if renderer is not None:renderer.delete()
    if hashlib.sha256(args.model.read_bytes()).hexdigest()!=source_hash:raise RuntimeError('Source model changed')
    manifest={'schema_version':1,'character_id':args.character_id,'version_id':args.version_id,'source_model':str(args.model),'source_model_sha256':source_hash,'texture_meshes':texture_meshes,'canvas':[args.size,args.size],'projection':'orthographic','half_frame':half_frame,'look_target':target.tolist(),'source_world_bounds':bounds.tolist(),'views':views,'turntable':None if args.no_turntable else {'path':str(args.output/'turntable.mp4'),'duration_seconds':args.turntable_seconds,'fps':args.fps,'mesh_animation':False,'camera_orbit_only':True},'contact_sheet':str(args.output/'contact-sheet.jpg'),'capabilities':{'static_mesh':True,'rigging_created':False,'character_motion_created':False,'silhouette_masks':True},'visual_review':'not_reviewed','identity_or_license_certified':False}
    manifest['settings']=settings
    manifest['view_label_basis']='camera orbit yaw, not anatomical left/right certification'
    manifest['artifact_hashes']={'contact-sheet.jpg':sha256(args.output/'contact-sheet.jpg')}
    if not args.no_turntable:
        manifest['artifact_hashes']['turntable.mp4']=sha256(args.output/'turntable.mp4')
    (args.output/'reference-pack.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'views':len(views),'masks':len(views),'turntable':not args.no_turntable,'source_unchanged':True},ensure_ascii=False))


if __name__=='__main__':
    main()
