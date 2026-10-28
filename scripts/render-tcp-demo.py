#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render TCP diagram + existing Naiwa footage. No character or voice synthesis."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = ['/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/PingFang.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc']
FONT = next((p for p in FONT_CANDIDATES if Path(p).is_file()), '')
WIDTH, HEIGHT, FPS = 720, 1280, 30
SCALE = WIDTH / 1080
BG = '#101423'
GOLD = '#FFCA28'
WHITE = '#F2F4F8'
MUTED = '#B1BACA'


def px(value):
    return round(value * SCALE)


@lru_cache(maxsize=30)
def font(size):
    return ImageFont.truetype(FONT, px(size))


def text(draw, value, xy, size, fill=WHITE, anchor='mm'):
    draw.text((px(xy[0]), px(xy[1])), value, font=font(size), fill=fill, anchor=anchor)


def line(draw, points, fill, width=3):
    draw.line([(px(x), px(y)) for x, y in points], fill=fill, width=max(1, px(width)))


def rounded(draw, box, fill, outline=None, radius=22, width=2):
    draw.rounded_rectangle(tuple(px(x) for x in box), radius=px(radius), fill=fill, outline=outline, width=max(1, px(width)))


@lru_cache(maxsize=110)
def actor_frame(number):
    path = ROOT / ('assets/repos/naiwa-pet/public/pets/naiwa/frames/frame_%04d.webp' % number)
    return Image.open(path).convert('RGBA')


def actor(image, t, small=False):
    # Every pixel of the actor comes from the downloaded sequence.
    number = 0 if t < 23 else min(437, 200 + int((t - 23) * 30))
    source = actor_frame(number)
    if t < 2:
        box = (230, 510, 850, 1340)
        zoom = 1 + 0.025 * math.sin(t * 2)
    else:
        box = (328, 1160, 752, 1725)
        zoom = 1.0
        for beat in [4.5, 8.5, 13.3, 16.5, 23]:
            elapsed = t - beat
            if 0 <= elapsed < 0.45:
                zoom += 0.055 * (1 - elapsed / 0.45)
    x0, y0, x1, y1 = box
    w, h = px(x1-x0), px(y1-y0)
    card = Image.new('RGBA', (w, h), (250, 249, 244, 255))
    ratio = min(w / source.width, h / source.height) * zoom
    resized = source.resize((round(source.width * ratio), round(source.height * ratio)), Image.Resampling.LANCZOS)
    card.alpha_composite(resized, ((w-resized.width)//2, h-resized.height))
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=px(28), fill=255)
    image.paste(card.convert('RGB'), (px(x0), px(y0)), mask)


def draw_packet(draw, packet, t):
    start, end = packet['send_time'], packet['arrival_time']
    if t < start:
        return
    progress = min(1.0, (t-start)/(end-start))
    y = packet['row_y']
    x0, x1 = (220, 860) if packet['sender'] == 'client' else (860, 220)
    x = x0 + (x1-x0)*progress
    color = packet['color']
    line(draw, [(x0,y),(x,y)], color, 6)
    sign = 1 if x1>x0 else -1
    draw.polygon([(px(x),px(y)),(px(x-20*sign),px(y-13)),(px(x-20*sign),px(y+13))], fill=color)
    if progress < 1:
        rounded(draw, (x-27,y-21,x+27,y+21), color, radius=8)
    label = packet['label']
    text(draw,label,(540,y-54),37,color)
    if progress == 1:
        text(draw,'已收到',(x1,y+34),25,color)


def render_frame(story, t):
    im = Image.new('RGB', (WIDTH,HEIGHT), BG)
    d = ImageDraw.Draw(im)
    # Sparse background rules keep packet directions readable.
    for y in range(260,1730,110):
        line(d,[(55,y),(1025,y)],'#1A2235',1)
    shot = next(s for s in story['shots'] if s['start'] <= t < s['end'])
    step = 0 if t < 4 else 1 if t < 8 else 2 if t < 13 else 3
    text(d,'奶蛙 · 网络整活课',(64,67),28,GOLD,'lm')
    headline = shot['headline']
    size = 58 if len(headline)<14 else 44
    text(d,headline,(540,156),size)
    if t < 2:
        text(d,'TCP 三次握手',(540,330),73,GOLD)
        text(d,'先别齁！握完再笑',(540,430),40,MUTED)
    if t >= 2:
        rounded(d,(64,280,1016,1110),'#182034',outline='#2B3652',radius=30)
        rounded(d,(90,300,330,384),'#2C3040',outline=GOLD,radius=18)
        rounded(d,(750,300,990,384),'#213545',outline='#53D4FF',radius=18)
        text(d,'客户端',(210,342),37,GOLD)
        text(d,'服务器',(870,342),37,'#53D4FF')
        state = next(s for s in story['state_intervals'] if s['start'] <= t < s['end'])
        for x,name in [(180,state['client']),(900,state['server'])]:
            color = '#ABED59' if name=='ESTABLISHED' else MUTED
            # Long state names sit on two lines to avoid clipping at the edge.
            shown = {'SYN_RECEIVED':'SYN_RCVD'}.get(name,name)
            text(d,shown,(x,419),23,color)
        for x in [220,860]:
            for y in range(465,1070,28):
                line(d,[(x,y),(x,y+14)],'#4A5670',3)
        for packet in story['packet_events']:
            draw_packet(d,packet,t)
        if t>=18:
            rounded(d,(286,1020,794,1088),'#263825',radius=12)
            text(d,'连接已建立 · 可以传数据',(540,1054),28,'#ABED59')
        if 2<=t<4:
            text(d,'三次确认，不是三次加密',(540,680),42,GOLD)
            text(d,'从一个 SYN 开始',(540,765),35,MUTED)
    actor(im,t)
    d = ImageDraw.Draw(im)
    if t>=2:
        rounded(d,(64,1155,286,1280),'#293449',radius=20)
        text(d,'奶蛙：',(175,1190),31,GOLD)
        reaction = '听得到吗？' if t<8 else '对面回了！' if t<13 else '我收到了！' if t<18 else '懂了吧？' if t<23 else '齁齁齁！'
        text(d,reaction,(175,1240),28)
        rounded(d,(790,1155,1016,1280),'#293449',radius=20)
        text(d,str(step)+'/3',(902,1215),51,'#ABED59' if step==3 else GOLD)
        text(d,'三次握手',(902,1330),26,MUTED)
    caption = next(c for c in story['captions'] if c['start']<=t<c['end'])
    rounded(d,(48,1744,1032,1865),'#202A40',radius=20)
    lines = caption['lines']
    for i,value in enumerate(lines):
        size = 32 if len(value)>26 else 36
        text(d,value,(540,1776+i*48 if len(lines)>1 else 1804),size)
    text(d,'奶蛙现成素材演示  /  BASIC TCP · RFC 9293',(540,1890),19,'#8491A8')
    line(d,[(0,1914),(1080*(t/26),1914)],GOLD,6)
    return im


def main():
    global FONT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', help='Local CJK TTF/TTC font when none is auto-detected')
    parser.add_argument('--preview', type=float, help='Render one timestamp PNG only')
    parser.add_argument('--audio-only', action='store_true', help='Reuse the already-rendered silent picture')
    parser.add_argument('--with-cues', action='store_true', help='Mix existing short meme cues as a local audition preview')
    parser.add_argument('--output', default='outputs/tcp-handshake/naiwa-tcp-handshake.mp4')
    args=parser.parse_args()
    if args.font:
        FONT=args.font
    if not FONT or not Path(FONT).is_file():
        parser.error('A local CJK font is required; use --font PATH')
    story=json.loads((ROOT/'production/tcp-handshake/storyboard.json').read_text())
    dest=ROOT/args.output
    dest.parent.mkdir(parents=True,exist_ok=True)
    if args.preview is not None:
        target=dest.with_name('preview-%04d.png'%round(args.preview*100))
        render_frame(story,args.preview).save(target)
        print(target)
        return
    silent=dest.with_name('silent.mp4')
    if not args.audio_only:
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)]
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for n in range(26*FPS):
                process.stdin.write(render_frame(story,n/FPS).tobytes())
                if n and n%(FPS*5)==0:print('rendered %.0f / 26s'%(n/FPS),flush=True)
        finally:
            process.stdin.close()
        if process.wait()!=0:raise RuntimeError('FFmpeg failed')
    elif not silent.is_file():
        raise RuntimeError('No silent video to reuse')
    # Existing recording clips only; no original voice/laughter is synthesized.
    cues=[{'asset_id':'naiwa-original-audio','path':'assets/repos/naiwa-pet/public/pets/naiwa/audio.m4a','source_start':6.666667,'duration':3.0,'timeline_start':23.0,'gain_db':-5}]
    if args.with_cues:
        cues[:0]=[
            {'asset_id':'nai-hub-hola_ganbadie','path':'assets/repos/NaiLoong/assets/audio/hola_ganbadie.mp3','source_start':0,'duration':1.806604,'timeline_start':0.1,'gain_db':-8},
            {'asset_id':'nai-hub-dupu','path':'assets/repos/NaiLoong/assets/audio/dupu.mp3','source_start':0,'duration':1.194467,'timeline_start':4.5,'gain_db':-8},
            {'asset_id':'nai-hub-dupu','path':'assets/repos/NaiLoong/assets/audio/dupu.mp3','source_start':0,'duration':1.194467,'timeline_start':8.5,'gain_db':-8},
            {'asset_id':'nai-hub-gajiaosai','path':'assets/repos/NaiLoong/assets/audio/gajiaosai.mp3','source_start':0,'duration':1.109751,'timeline_start':13.3,'gain_db':-8}]
    inputs=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent)]
    filters=[]
    for i,cue in enumerate(cues,1):
        inputs += ['-i',str(ROOT/cue['path'])]
        delay=round(cue['timeline_start']*1000)
        filters.append('[%d:a]atrim=start=%s:duration=%s,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume=%sdB,afade=t=out:st=%s:d=0.08,adelay=%d|%d[c%d]'%(i,cue['source_start'],cue['duration'],cue['gain_db'],max(0,cue['duration']-0.08),delay,delay,i))
    filters.append(''.join('[c%d]'%i for i in range(1,len(cues)+1))+'amix=inputs=%d:duration=longest:normalize=0,apad,atrim=duration=26[a]'%len(cues))
    subprocess.run(inputs+['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k','-t','26','-movflags','+faststart',str(dest)],check=True)
    report={'output':str(dest.relative_to(ROOT)),'duration_seconds':26,'resolution':[WIDTH,HEIGHT],'fps':FPS,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'character_pixels':'existing frame_0000 and source frames_0200 through 0289; no generated character pixels','audio_clips':cues,'audio_selection_status':'local_audition_preview; source labels known, semantic/version match not claimed auditioned','synthesized_voice_or_bgm':False,'usage':'local demonstration only; source media rights unresolved','hitem3d_result_used_in_video':False}
    (ROOT/'production/tcp-handshake/render-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(dest)


if __name__=='__main__':
    main()
