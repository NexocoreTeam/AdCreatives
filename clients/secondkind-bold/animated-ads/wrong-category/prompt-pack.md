# SK Bold "Wrong Category" — Higgsfield Prompt Pack

Everything to generate this ad yourself in Higgsfield. Claude owns the script + these prompts; you generate/curate the clips, the VO, and the music in the tool. Pairs with `concept-v3.md`.

---

## Global settings & rules

**Image:** Nano Banana Pro (or Nano Banana 2), 9:16, 2k, 2–3 variations per prompt, pick best.
**Video:** Kling 3.0, 9:16, ~5s, **AUDIO OFF** (toggle the audio-off button — every clip is silent). Decline the "IN THE DARK" preset if it pops up.

**Minimal-prompt approach:** the per-scene prompts below are deliberately bare — just the core action. Let Higgsfield fill in the framing, lighting, and motion. The style tag + hard rules carry the brand look; the **keep** notes are the only non-negotiables (each is a past failure point, not art direction — drop them and the bottle stretches tall, the capsule starts talking, the bloat shows bare skin, etc.).

**Hard rules (every scene):**
- Characters **never talk / no lip-sync** — mouths closed. It's a single narrator VO. (The only voice line is the army cry in scene 2, a separate voice, no on-screen mouth needed.)
- **Consistency:** always feed the character's reference image. For motion with two states (charge→wipeout, closed→open), use **start frame + end frame**. For a single state, start frame only.
- Warm palette only, no cool blue-grey. Sentence case, no em/en dashes anywhere on screen.
- **No infomercial reveals** — the product is never "introduced"; it arrives as the answer.

**Style tag (paste into every image prompt):**
> Pixar animation style, high-end 3D render, soft ambient lighting, cinematic depth of field, rounded soft geometry, subtle subsurface scattering, studio-quality; SecondKind editorial palette: warm snow-white (#fefcf6) background, muted stone and charcoal neutrals, a single marigold (#fcb348) accent; clean minimal premium, refined not cartoonish; 9:16 vertical.

After scene 1, append to image prompts: *"lighting and palette matching the prior shot, warm tones, no cool blue-grey."*

---

## Cast / reference anchors

Re-roll from these (they're in your Higgsfield history) or regenerate. The refs carry the character design so the prompts don't have to.

- **Blue probiotic capsule-soldiers** — pale-blue translucent gel capsule, tiny charcoal helmet, big eager eyes. Master ref: the army-out-of-the-bottle frame (job `e6278467`).
- **Coral gut character** — rounded coral-pink gut-lining creature, little grey boots. Ref: job `594ae42e`.
- **Woman (Danielle)** — Pixar woman late 30s, brown shoulder-length hair, a long cream cardigan that fully covers her belly. Refs: salad `cd48b5b2`, pizza `c2797b54`.
- **Real Gut Balance bottle** — the real product, plain, no face, accurate **short squat** amber jar + real label. Ref image: `https://secondkind.com/cdn/shop/files/gut-balanace-product-img-5926.png`.
- **Gold postbiotic capsule character** — cream + golden-amber gel capsule, sculpted 3D face. Ref: job `66e9ba7f` (bottle + capsule together).
- **"Back door" door** — plain door with a small sign reading **back door**.

---

## Scene 1 — the army marches off · ~9s · start-only
**VO:** "every morning, billions of probiotics wake up, suit up, and march off to save your gut. they think they're the heroes. they think they're gonna make it. bless them."
**Prompt:** Six capsules march out of the bottle toward camera.
**Generate:** Establisher still (no ref), then animate (start-only). This frame becomes your army anchor (`e6278467`).

## Scene 2 — the charge and the wipeout · ~11s · bookend
**Army cry (separate gung-ho voice):** "we've got it this time, boys!"
**VO:** "they do not have it this time. they hit your stomach acid, and about seventy percent just… dissolve. gone. never saw it coming. brave little idiots."
**Prompt:** START — the capsules charge toward a pool of acid. END — most have dissolved, one survivor remains.
**Generate:** Bookend start (`8a29c313`) → end (`c33a5621`).
**Keep:** capsules stay blue until they touch the acid (or just have them plunge under and vanish).

## Scene 3 — the survivors ghost · ~9s · start-only
**VO:** "the few that survive are supposed to move into your gut and build a life there. instead they take one look around and bail. ghosted. by your own supplement."
**Prompt:** Two capsules stand in the gut, lose interest, and wander off.
**Generate:** Start-only, ref `e6278467` (gut-chamber frame `245a0631`).
**Keep:** the two capsules out of sync (in-sync twins look uncanny).

## Scene 4 — the bored gut · ~10s · start-only
**VO:** "and your gut? it's been down here for years, just waiting. like someone who keeps getting stood up but still shows up to the restaurant. it's a little sad, honestly."
**Prompt:** The gut character kicks a pebble in an empty tunnel.
**Generate:** Still (no ref), then animate (start-only). Becomes your gut anchor (`594ae42e`).

## Scene 5 — salad vs pizza, the bloat · ~10s · two clips (A/B cut in post)
**VO:** "meanwhile you do everything right. the salad. the water. the little walk. and your body looks at all that effort and goes: nope. three months pregnant by seven. it was never you."
**Prompt:** She eats (salad, then pizza); after she eats, her belly bloats and she throws her hands up.
**Generate:** Salad start-only (`cd48b5b2`); pizza start-only (`c2797b54`). Post: full-frame salad → hard cut → full-frame pizza.
**Keep:** her belly stays covered — the bloat happens under her top, and only after she eats.

## Scene 6 — the pill's "idea" · ~10s · start-only
**VO:** "so how do you get the good stuff in, if it dies the second it goes down? well. there is technically one other entrance. …you know the one."
**Prompt:** The lone capsule gets an idea and looks over at a door marked "back door."
**Generate:** Start-only, ref `e6278467`. Produces the signed-door frame (`66faf6e7`).
**Keep:** the "back door" sign legible and still.

## Scene 7 — "nope," and the answer arrives · ~6s · bookend
**VO:** "no. nope. we're not doing that. nobody wants that. so instead, we skip the whole circus."
**Prompt:** START — the capsule cringes "nope." END — the real bottle and the gold capsule slide in.
**Generate:** Bookend start (`66faf6e7`) → end (`4ae2378e`); build the end with the product character (`66e9ba7f`).
**Keep:** the real bottle accurate (short, squat, real label); the sign legible.

## Scene 8 — the capsule opens, three compounds · ~10s · bookend
**VO:** "and go straight to what those little guys were trying to make before they died. postbiotics. already made, already working. no survival required, no ghosting, no dramatic death scene."
**Prompt:** The gold capsule opens and three glowing pieces float out, next to the bottle.
**Generate:** Bookend start product character (`66e9ba7f`) → end opened-capsule (`cd5105ff`).
**Keep:** the real bottle accurate; the capsule's mouth stays closed (no talking).

## Scene 9 — the gut's payoff · ~9s · bookend
**VO:** "no surviving, no colonizing, no heroic quest. it just shows up, on time, like a functional adult, and does the one job your gut's been begging for."
**Prompt:** A gold light flows into the gut and it perks up.
**Generate:** Bookend start gut (`594ae42e`) → end perked-up (`8748f1b4`).

## Scene 10 — the CTA · ~7s · start-only
**VO:** "try it for sixty days. if your gut feels nothing, you don't pay a cent. go to secondkind.com."
**Prompt:** The bottle and the gold capsule; the capsule gives a thumbs-up, with space at the bottom for the CTA.
**Generate:** Start-only, ref `66e9ba7f` (or the CTA hero `0dcb5c33`).
**Keep:** the real bottle accurate.
**Captions (last):** burn in the CTA — "try it for 60 days. if your gut feels nothing, you don't pay a cent." plus secondkind.com. (Optional small proof: "84-day study: less bloating, less stress.")

---

## Audio (your step in Higgsfield)
- **Narrator VO:** one consistent voice for all 10 lines (read script in `concept-v3.md`, stats spelled out).
- **Army cry:** one separate gung-ho voice: "we've got it this time, boys!"
- **Suno bed:** *Instrumental, ~80–95s (match the final cut), ~95 BPM. Playful, mischievous, whimsical comedic underscore. Light plucky strings and pizzicato, a cheeky bassoon or tuba being goofy, soft marimba, warming into a hopeful turn in the final third. Bright, characterful, premium. No vocals, no big drop. Leave space in the mids for a voiceover.*

## Edit / finish (Claude can do this part if you want)
Time each silent scene to its VO line, light warm grade + film grain, mix VO ~-5dB over the bed ~-25dB, captions LAST. The `_polish_silent.py` / assembly scripts in this folder already do the trim+grade+grain.
