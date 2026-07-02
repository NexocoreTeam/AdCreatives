import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(ROOT, "generated", "clips_v3")
V2 = os.path.join(ROOT, "generated", "clips_v2")
VO = os.path.join(ROOT, "generated", "vo_v2")
WORK = os.path.join(ROOT, "generated", "_v4work")
os.makedirs(WORK, exist_ok=True)

SRC = {1: V3, 2: V3, 3: V3, 4: V2, 5: V3, 6: V3, 7: V2, 8: V2, 9: V2, 10: V2}
HEAD = 0.20   # trim the dead still head off each clip so motion starts ON the cut
TAIL = 0.10   # tiny breath after each line, nothing more


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
    # 1) strip leading silence off the VO so the WORD starts at t=0 (kills the lag)
    voc = os.path.join(WORK, f"V{n:02d}.mp3")
    ff(["-i", vo, "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0", voc])
    vd = dur(voc)
    seg = round(vd + TAIL, 3)
    # 2) trim the still head off the clip, then speed-cap 1.5 and fit to the line
    cl = dur(clip)
    avail = max(0.1, cl - HEAD)
    f = max(1.0, min(1.5, avail / seg))
    filt = f"setpts=PTS/{f:.5f}"
    vseg = os.path.join(WORK, beat + ".mp4")
    ff(["-ss", str(HEAD), "-i", clip, "-an", "-filter:v", filt, "-t", str(seg), "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", vseg])
    aseg = os.path.join(WORK, f"A{n:02d}.mp3")
    ff(["-i", voc, "-af", "apad", "-t", str(seg), aseg])
    vf.write(f"file '{vseg.replace(os.sep, '/')}'\n")
    af.write(f"file '{aseg.replace(os.sep, '/')}'\n")
    total += seg
    print(f"{beat}: word={vd:.2f}s seg={seg:.2f}s @ {f:.2f}x")
vf.close(); af.close()

video = os.path.join(WORK, "video.mp4")
aud = os.path.join(WORK, "vo_full.mp3")
final = os.path.join(ROOT, "generated", "final_v4.mp4")
ff(["-f", "concat", "-safe", "0", "-i", vlist,
    "-vf", "eq=contrast=1.04:saturation=1.05:gamma=0.99,noise=alls=6:allf=t",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", video])
ff(["-f", "concat", "-safe", "0", "-i", alist, "-c:a", "libmp3lame", "-q:a", "2", aud])
ff(["-i", video, "-i", aud, "-c:v", "copy", "-c:a", "aac", "-shortest", final])
print(f"TOTAL {total:.1f}s -> {final}")
