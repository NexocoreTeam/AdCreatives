# Post-production + QC mechanics

The ffmpeg patterns for the edit, plus the failure taxonomy and the gotchas for when
Claude is generating / reviewing via the Higgsfield MCP.

---

## When Claude can't watch motion (frame-checking MCP clips)

Claude cannot watch a video. To QC a generated clip, extract frames and Read them:

```bash
ffmpeg -y -i clip.mp4 -vf "fps=2" "frames/clip_%03d.png"
```

Then Read the frames to judge composition, character consistency, the "keep accurate"
items, and obvious artifacts. You are checking the picture, not the motion, so still trust
the user's eyes on pacing for any clip they generated in the web app.

**Preview players:** build a small `preview.html` with the clips in `<video>` tags and open
it with `Start-Process` (on this machine, the file-send widget does not render in the
terminal). One column of raw clips next to the script captions is the fastest review.

**Queue flakiness:** Higgsfield jobs sometimes stick in `queued` / `in_progress` for
minutes or go zombie. Resubmitting a fresh job usually clears it. Use a background polling
loop, not chained `sleep`.

---

## The assembly script (trim, concat, grade, grain)

Pattern proven on the SK Bold cut. Per scene: trim the dead head, set a target duration,
concat, then one warm grade + light grain over the whole thing.

```python
import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(ROOT, "generated", "clips")
WORK  = os.path.join(ROOT, "generated", "_work")
os.makedirs(WORK, exist_ok=True)
HEAD = 0.25  # trim the still/dead head off each clip

# (clip, target seconds) - time each scene to its VO line
SCENES = [("S01.mp4", 9.0), ("S02.mp4", 11.0), ...]

def ff(args):
    subprocess.run(["ffmpeg", "-y"] + args, capture_output=True)

lst = os.path.join(WORK, "v.txt")
with open(lst, "w") as f:
    for i, (clip, dur) in enumerate(SCENES):
        seg = os.path.join(WORK, f"{i:02d}.mp4")
        ff(["-ss", str(HEAD), "-i", os.path.join(CLIPS, clip), "-an", "-t", str(dur),
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", seg])
        f.write(f"file '{seg.replace(os.sep, '/')}'\n")

out = os.path.join(ROOT, "generated", "cut_silent.mp4")
# concat + warm editorial grade + light grain (premium, takes the plastic AI sheen off)
ff(["-f", "concat", "-safe", "0", "-i", lst,
    "-vf", "eq=contrast=1.03:saturation=1.05:gamma=0.99,noise=alls=6:allf=t+u",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out])
```

### Speed-mapping a single scene (pacing)
```bash
# 1.4x faster (tighten a dead spot):
ffmpeg -y -i in.mp4 -an -filter:v "setpts=PTS/1.4" out.mp4
# 0.8x slower (hold an impact beat):
ffmpeg -y -i in.mp4 -an -filter:v "setpts=PTS/0.8" out.mp4
```

### Mux the VO + music under the picture
```bash
# music bed under voice: voice ~ -5dB, music ~ -25dB
ffmpeg -y -i cut_silent.mp4 -i vo.mp3 -i music.mp3 -filter_complex \
 "[1:a]volume=0.9[v];[2:a]volume=0.06[m];[v][m]amix=inputs=2:duration=longest[a]" \
 -map 0:v -map "[a]" -c:v copy -shortest cut_mixed.mp4
```

### Captions LAST
Burn captions only on the locked `cut_mixed.mp4`. Sentence case, brand font, no em / en
dashes, include the CTA. (Often the cleanest hand-off: lock everything, then a caption +
zoom-punch pass.)

---

## Fight-the-AI-look toolkit

| Tell | Fix in post |
|---|---|
| Too clean / plastic sheen | `noise=alls=6:allf=t+u` grain + slight `eq` grade |
| Too symmetric / centered | crop tighter, off-center, subtle Ken-Burns push |
| Dead air at clip start/end | trim head/tail; cut tighter than the AI framed it |
| Flat energy | speed-map, harder cuts on the beat, add SFX |
| Feels synthetic | cut in real B-roll, client logos, product footage |

---

## QC failure taxonomy (keep vs kill)

| Symptom | Cause | Action |
|---|---|---|
| Face / clothes change between scenes | broke the reference chain | KILL, re-anchor references, re-roll |
| Prop changed (clock, screen, label, text) | model drift | KILL if central; else fix/cover in post |
| Item appears / vanishes | model drift | fix in post (cut or B-roll) |
| Expression right, background off | normal trade-off | KEEP, fix in post |
| Character talking when it should be silent | prompt let the mouth move | re-roll with "mouth closed, no talking" |
| Object stretches / wrong proportion (e.g. real product) | text-only over-described | re-roll from the real reference image + "keep accurate" |
| Energy clashes with neighbors | pacing | usually KEEP, fix with speed + grade |

**Stack feedback forward:** every fix becomes a standing rule applied to all later scene
prompts, so the back half of the ad is cleaner than the front half.

---

## Credit discipline

- Frontload generation; iterate the EDIT for free.
- Do not regenerate what post can fix.
- Audio off for silent scenes; generate only the length you need.
- Hero / face scenes are worth the re-rolls; establishers and B-roll are not.
