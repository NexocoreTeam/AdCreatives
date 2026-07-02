import os, json, urllib.request

API = os.environ["ELEVENLABS_API_KEY"]
BASE = "https://api.elevenlabs.io/v1"
OUT = "generated/vo_samples"
os.makedirs(OUT, exist_ok=True)


def get(p):
    req = urllib.request.Request(BASE + p, headers={"xi-api-key": API})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def tts(vid, text, out):
    body = json.dumps({
        "text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(f"{BASE}/text-to-speech/{vid}", data=body, method="POST",
                                 headers={"xi-api-key": API, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(out, "wb").write(r.read())


voices = get("/voices")["voices"]
byname = {}
for v in voices:
    byname.setdefault(v["name"].split(" - ")[0].strip().split()[0].lower(), (v["voice_id"], v["name"]))
print("AVAILABLE:", ", ".join(sorted(n for n in byname)))

roles = {
    # role: (candidate first-names in priority order, sample line in character)
    "probiotic": (["will", "liam", "callum", "chris", "sam", "brian"],
                  "I'm the probiotic you take every morning. Can I be honest with you?"),
    "woman":     (["matilda", "sarah", "alice", "lily", "charlotte", "jessica"],
                  "I eat clean. I train. And I'm still bloated by dinner. I started to think it was me."),
    "postbiotic": (["sarah", "charlotte", "eric", "river", "george", "jessica"],
                   "You were never the problem. The delivery was. I'm a postbiotic."),
}

made = {}
for role, (prefs, line) in roles.items():
    made[role] = []
    for p in prefs:
        if p in byname and len(made[role]) < 3:
            vid, nm = byname[p]
            out = os.path.join(OUT, f"{role}__{p}.mp3")
            tts(vid, line, out)
            made[role].append((p, nm))
            print(f"  {role}: {p}  ({nm})")
print("MADE:", json.dumps(made))
print("DONE")
