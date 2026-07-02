import os, json, sys, urllib.request

API = os.environ["ELEVENLABS_API_KEY"]
BASE = "https://api.elevenlabs.io/v1"
OUT = sys.argv[1] if len(sys.argv) > 1 else "generated/vo_v2"
VOICE = sys.argv[2] if len(sys.argv) > 2 else "Brian"   # one consistent brand narrator (swappable)
os.makedirs(OUT, exist_ok=True)


def get(p):
    req = urllib.request.Request(BASE + p, headers={"xi-api-key": API})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def tts(vid, text, out):
    body = json.dumps({
        "text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(f"{BASE}/text-to-speech/{vid}", data=body, method="POST",
                                 headers={"xi-api-key": API, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(out, "wb").write(r.read())


voices = get("/voices")["voices"]
byname = {}
for v in voices:
    byname.setdefault(v["name"].split(" - ")[0].strip().split()[0].lower(), v["voice_id"])
vid = byname.get(VOICE.lower()) or voices[0]["voice_id"]
print("VOICE:", VOICE, vid)

lines = [
    "I'm the probiotic you take every morning. Time for the truth.",
    "About seventy percent of me dies in your stomach before I reach your gut.",
    "The few that survive are supposed to move in and stay. We don't.",
    "You eat clean. You train. You're still bloated by seven. And you blame yourself.",
    "It was never you. It was the delivery.",
    "I'm a postbiotic. What those bacteria were supposed to make.",
    "Already made. Already active. Nothing to survive, nothing to move into.",
    "Your gut finally gets what it's been waiting for.",
    "Eighty-four day study. Less bloating. Less stress.",
    "Gut Balance. Sixty days. Feel the difference, or you don't pay.",
]
for i, t in enumerate(lines, 1):
    out = os.path.join(OUT, f"V{i:02d}.mp3")
    tts(vid, t, out)
    print("wrote", out, os.path.getsize(out))
print("DONE")
