import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(ROOT, "generated", "clips")
VO = os.path.join(ROOT, "generated", "vo")
WORK = os.path.join(ROOT, "generated", "_assembly")
VSEG = os.path.join(WORK, "vseg"); ASEG = os.path.join(WORK, "aseg")
for d in (WORK, VSEG, ASEG):
    os.makedirs(d, exist_ok=True)


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def ff(args):
    subprocess.run(["ffmpeg", "-y"] + args, capture_output=True)


scenes = [f"V{n:02d}" for n in range(1, 16)]
CLIP_LEN, BREATH = 8.0, 0.18
vlist, alist = os.path.join(WORK, "v.txt"), os.path.join(WORK, "a.txt")
vf, af = open(vlist, "w"), open(alist, "w")
total = 0.0
for s in scenes:
    vo, clip = os.path.join(VO, s + ".mp3"), os.path.join(CLIPS, s + ".mp4")
    vd = dur(vo)
    seg = round(vd + BREATH, 3)
    f = max(1.3, min(2.6, CLIP_LEN / seg))
    sped = CLIP_LEN / f
    pad = max(0.0, round(seg - sped, 3))
    vfilter = f"setpts={1.0 / f:.5f}*PTS"
    if pad > 0:
        vfilter += f",tpad=stop_mode=clone:stop_duration={pad}"
    vseg = os.path.join(VSEG, s + ".mp4")
    ff(["-i", clip, "-an", "-filter:v", vfilter, "-t", str(seg), "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", vseg])
    aseg = os.path.join(ASEG, s + ".mp3")
    ff(["-i", vo, "-af", "apad", "-t", str(seg), aseg])
    vf.write(f"file '{vseg.replace(os.sep, '/')}'\n")
    af.write(f"file '{aseg.replace(os.sep, '/')}'\n")
    total += seg
    print(f"{s}: vo={vd:.2f}s -> seg={seg:.2f}s @ {f:.2f}x")
vf.close(); af.close()

vid = os.path.join(WORK, "video.mp4")
aud = os.path.join(WORK, "vo_full.mp3")
final = os.path.join(ROOT, "generated", "final_vo.mp4")
ff(["-f", "concat", "-safe", "0", "-i", vlist, "-c:v", "libx264", "-pix_fmt", "yuv420p", vid])
ff(["-f", "concat", "-safe", "0", "-i", alist, "-c:a", "libmp3lame", "-q:a", "2", aud])
ff(["-i", vid, "-i", aud, "-c:v", "copy", "-c:a", "aac", "-shortest", final])
print(f"TOTAL {total:.1f}s -> {final}")
