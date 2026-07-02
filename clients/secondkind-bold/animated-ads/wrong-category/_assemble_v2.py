import os, re, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(ROOT, "generated", "clips_v2")
WORK = os.path.join(ROOT, "generated", "_v2work")
os.makedirs(WORK, exist_ok=True)
SPEED = 1.4
scenes = [f"B{n:02d}" for n in range(1, 11)]   # 10-beat v2 script


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def silences(p):
    r = subprocess.run(["ffmpeg", "-i", p, "-af",
                        "highpass=f=220,lowpass=f=3200,silencedetect=noise=-16dB:d=0.2",
                        "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return st, en


listf = os.path.join(WORK, "list.txt")
lf = open(listf, "w")
total = 0.0
for s in scenes:
    clip = os.path.join(CLIPS, s + ".mp4")
    cd = dur(clip)
    st, en = silences(clip)
    a = min(en) if (st and en and min(st) < 0.15) else 0.0
    b = cd
    if len(st) > len(en):
        b = max(st)
    elif st and en and max(st) > max(en):
        b = max(st)
    a = max(0.0, a - 0.06)
    b = min(cd, b + 0.10)
    td = round(b - a, 3)
    if td < 0.6:
        a, td = 0.0, cd
    out = os.path.join(WORK, s + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-i", clip, "-t", f"{td:.3f}",
                    "-filter_complex", f"[0:v]setpts=PTS/{SPEED}[v];[0:a]atempo={SPEED}[a]",
                    "-map", "[v]", "-map", "[a]", "-r", "30", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", out], capture_output=True)
    lf.write(f"file '{out.replace(os.sep, '/')}'\n")
    total += td / SPEED
    print(f"{s}: clip={cd:.2f}s speech=[{a:.2f},{b:.2f}] -> {td / SPEED:.2f}s")
lf.close()

final = os.path.join(ROOT, "generated", "final_v2.mp4")
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", final],
               capture_output=True)
print(f"TOTAL {total:.1f}s -> {final}")
