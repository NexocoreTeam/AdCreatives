import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(ROOT, "generated", "v3_clips")
WORK = os.path.join(ROOT, "generated", "_polishwork")
os.makedirs(WORK, exist_ok=True)
HEAD = 0.25  # trim the dead still head off each clip

# (clip, target seconds) — scratch timing from the script; VO will retime precisely later
SCENES = [
    ("S01.mp4", 3.6), ("S02.mp4", 4.8), ("S03.mp4", 3.0), ("S04.mp4", 3.4),
    ("S05salad.mp4", 3.0), ("S05pizza.mp4", 3.0), ("S06.mp4", 3.6),
    ("S07.mp4", 3.8), ("S08.mp4", 4.4), ("S09.mp4", 3.4), ("S10.mp4", 4.4),
]


def ff(a):
    subprocess.run(["ffmpeg", "-y"] + a, capture_output=True)


lst = os.path.join(WORK, "v.txt")
f = open(lst, "w")
total = 0.0
for i, (clip, dur) in enumerate(SCENES):
    seg = os.path.join(WORK, f"{i:02d}.mp4")
    ff(["-ss", str(HEAD), "-i", os.path.join(CL, clip), "-an", "-t", str(dur),
        "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", seg])
    f.write(f"file '{seg.replace(os.sep, '/')}'\n")
    total += dur
f.close()

out = os.path.join(ROOT, "generated", "polished_silent.mp4")
# concat + warm editorial grade + light grain (subtle, premium)
ff(["-f", "concat", "-safe", "0", "-i", lst,
    "-vf", "eq=contrast=1.03:saturation=1.05:gamma=0.99,noise=alls=6:allf=t+u",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out])
print(f"TOTAL {total:.1f}s -> {out}")
