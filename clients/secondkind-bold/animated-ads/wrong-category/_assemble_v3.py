import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(ROOT, "generated", "clips_v3")    # silent regens (B01,B02,B03,B05,B06)
V2 = os.path.join(ROOT, "generated", "clips_v2")    # existing VO-scene clips (B04,B07,B08,B09,B10), muted
VO = os.path.join(ROOT, "generated", "vo_v2")        # one clean narrator voice
WORK = os.path.join(ROOT, "generated", "_v3work")
os.makedirs(WORK, exist_ok=True)

# per-beat clip source: silent regens for the old talking beats, existing clips for the VO beats
SRC = {1: V3, 2: V3, 3: V3, 4: V2, 5: V3, 6: V3, 7: V2, 8: V2, 9: V2, 10: V2}
BREATH = 0.15


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def ff(a):
    subprocess.run(["ffmpeg", "-y"] + a, capture_output=True)


vlist, alist = os.path.join(WORK, "v.txt"), os.path.join(WORK, "a.txt")
vf, af = open(vlist, "w"), open(alist, "w")
total = 0.0
for n in range(1, 11):
    beat = f"B{n:02d}"
    clip = os.path.join(SRC[n], beat + ".mp4")
    vo = os.path.join(VO, f"V{n:02d}.mp3")
    vd, cl = dur(vo), dur(clip)
    seg = round(vd + BREATH, 3)
    f = max(1.0, min(1.5, cl / seg))   # gentle ceiling: living image under the voice, NOT fast-forward
    sped = cl / f
    pad = max(0.0, round(seg - sped, 3))
    filt = f"setpts=PTS/{f:.5f}"
    if pad > 0:
        filt += f",tpad=stop_mode=clone:stop_duration={pad}"
    vseg = os.path.join(WORK, beat + ".mp4")
    ff(["-i", clip, "-an", "-filter:v", filt, "-t", str(seg), "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", vseg])
    aseg = os.path.join(WORK, f"V{n:02d}.mp3")
    ff(["-i", vo, "-af", "apad", "-t", str(seg), aseg])
    vf.write(f"file '{vseg.replace(os.sep, '/')}'\n")
    af.write(f"file '{aseg.replace(os.sep, '/')}'\n")
    total += seg
    print(f"{beat}: vo={vd:.2f}s seg={seg:.2f}s @ {f:.2f}x  ({os.path.basename(SRC[n])})")
vf.close(); af.close()

video = os.path.join(WORK, "video.mp4")
aud = os.path.join(WORK, "vo_full.mp3")
final = os.path.join(ROOT, "generated", "final_v3.mp4")
# concat with a subtle warm grade + light grain (fight-the-AI-look, kept restrained for editorial brand)
ff(["-f", "concat", "-safe", "0", "-i", vlist,
    "-vf", "eq=contrast=1.04:saturation=1.05:gamma=0.99,noise=alls=6:allf=t",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
ff(["-f", "concat", "-safe", "0", "-i", alist, "-c:a", "libmp3lame", "-q:a", "2", aud])
ff(["-i", video, "-i", aud, "-c:v", "copy", "-c:a", "aac", "-shortest", final])
print(f"TOTAL {total:.1f}s -> {final}")
