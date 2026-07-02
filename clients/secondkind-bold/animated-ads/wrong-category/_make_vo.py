import os, json, sys, urllib.request

API = os.environ["ELEVENLABS_API_KEY"]
BASE = "https://api.elevenlabs.io/v1"
OUT = sys.argv[1] if len(sys.argv) > 1 else "generated/vo"
os.makedirs(OUT, exist_ok=True)


def get(path):
    req = urllib.request.Request(BASE + path, headers={"xi-api-key": API})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def tts(voice_id, text, out_path):
    body = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/text-to-speech/{voice_id}", data=body, method="POST",
        headers={"xi-api-key": API, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)


voices = get("/voices")["voices"]
byname = {}
for v in voices:
    key = v["name"].split(" - ")[0].strip().split()[0].lower()  # leading first-name token
    byname.setdefault(key, v["voice_id"])
print("AVAILABLE:", ", ".join(sorted(v["name"] for v in voices)))


def pick(prefs, used):
    for p in prefs:
        vid = byname.get(p.lower())
        if vid and vid not in used:
            used.add(vid); return p, vid
    for v in voices:
        if v["voice_id"] not in used:
            used.add(v["voice_id"]); return v["name"], v["voice_id"]
    return None, None


used = set()
hn, hero = pick(["Brian", "Eric", "George", "Daniel", "Bill", "Sarah"], used)   # calm, comforting, confident hero
pn, prob = pick(["Will", "Chris", "Liam", "Callum", "Sam"], used)               # relaxed, sheepish probiotic
gn, gutv = pick(["River", "Matilda", "Mark", "Antoni", "Thomas"], used)         # flat, weary, deadpan gut
print(f"HERO={hn}  PROBIOTIC={pn}  GUT={gn}")

lines = [
    ("V01", prob, "I'm the probiotic you've taken every morning for two years."),
    ("V02", prob, "Here's what I never told you. Roughly 70 percent of me dies in your stomach before I reach your gut."),
    ("V03", prob, "The trip is brutal. Most of us don't survive it."),
    ("V04", prob, "The few who make it are supposed to move in and stay. We almost never do."),
    ("V05", gutv, "I'm her gut. I've been waiting years for these guys to actually make something."),
    ("V06", gutv, "Still waiting."),
    ("V07", gutv, "She eats clean. She trains. She still feels bloated and uncomfortable by dinner."),
    ("V08", gutv, "And she's started to think it's her fault."),
    ("V09", hero, "It was never her fault. It was the delivery."),
    ("V10", hero, "I'm a postbiotic. I'm what those bacteria were supposed to make in the first place."),
    ("V11", hero, "Already made. Already active. Nothing to survive on the way down. Nothing to move into."),
    ("V12", hero, "Your gut finally gets what it was waiting for."),
    ("V13", hero, "In an eighty-four day study, people reported less bloating, less stress, better days."),
    ("V14", hero, "You weren't wrong to keep trying. You were just handed the wrong category."),
    ("V15", hero, "Try Gut Balance for sixty days. If your gut doesn't feel different, you don't pay."),
]

for name, vid, text in lines:
    out = os.path.join(OUT, name + ".mp3")
    tts(vid, text, out)
    print("wrote", name, os.path.getsize(out), "bytes")
print("DONE")
