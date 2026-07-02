import os, json, base64, urllib.request, urllib.error

API = os.environ["ELEVENLABS_API_KEY"]
BASE = "https://api.elevenlabs.io/v1"
OUT = "generated/vo_design"
os.makedirs(OUT, exist_ok=True)


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST",
        headers={"xi-api-key": API, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        raise


# role: (voice description, preview text in character — 100-1000 chars)
chars = {
    "probiotic": (
        "A casual American man in his late twenties, warm and a little sheepish, like he is quietly confessing something he is embarrassed about. Conversational and natural, gentle, slightly rueful. Not deep, not an announcer.",
        "I'm the probiotic you take every morning. Can I be honest with you? About seventy percent of me dies in your stomach before I ever reach your gut. The few that survive are supposed to move in and stay. We don't."),
    "woman": (
        "A grounded American woman in her mid thirties, warm but weary, like a friend quietly admitting she is frustrated and a little defeated. Natural and real, soft and conversational, not polished or corporate.",
        "I eat clean. I train. And I'm still bloated by dinner. I started to think it was me. That maybe, after everything, it really was my own fault all along."),
    "postbiotic": (
        "A warm, confident, reassuring American voice, calm and self assured, finally delivering good news. Friendly, modern and grounded. Not a deep movie trailer voice, not breathy.",
        "You were never the problem. The delivery was. I'm a postbiotic, exactly what those bacteria were always supposed to make. Already made. Already active. Your gut finally gets what it's been waiting for."),
}

manifest = {}
for role, (desc, text) in chars.items():
    res = post("/text-to-voice/create-previews", {"voice_description": desc, "text": text})
    manifest[role] = []
    for i, p in enumerate(res.get("previews", []), 1):
        b = base64.b64decode(p["audio_base_64"])
        fn = f"{role}__d{i}.mp3"
        open(os.path.join(OUT, fn), "wb").write(b)
        manifest[role].append({"file": fn, "gen_id": p["generated_voice_id"]})
        print(f"  {role} d{i}: {p['generated_voice_id']}  ({len(b)} bytes)")
open(os.path.join(OUT, "manifest.json"), "w").write(json.dumps(manifest, indent=2))
print("DONE")
