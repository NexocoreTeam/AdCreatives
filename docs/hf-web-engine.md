# `adc remix-images --engine hf-web`

Routes image generation through Higgsfield's **web backend**
(`fnf.higgsfield.ai/jobs/v2/nano_banana_flash`) — the same edit model
behind cloud.higgsfield.ai's UI and the official Higgsfield MCP server.
Verified to produce reference-faithful edits on complex multi-panel
references (us-vs-them comparisons, lifestyle hero shots, etc.) where
the public REST API path (`platform.higgsfield.ai`, used by the
`higgsfield` CLI) does not.

## When to use it

- You want to remix a reference ad and have the output preserve the
  source's layout, typography, decorative marks, and composition while
  swapping in your brand's product + copy.
- You're out of fal credits or want to avoid them.
- You don't have a trained Higgs Field Soul Character but still want the
  same edit-model output.

For simple "fresh ad inspired by reference" generation, the existing
`--engine nb2` (fal NB2) is fine and faster to set up.

## One-time setup (~30 seconds)

The web backend uses your browser's Higgsfield session cookies — the
same auth as cloud.higgsfield.ai. **Easiest path: use the helper script.**

### Recommended: run the extraction script

```bash
# One-time install of the cookie-reading lib (~5 sec)
py -3.14 -m pip install browser-cookie3

# Make sure you're logged into cloud.higgsfield.ai in Chrome, then:
py -3.14 scripts/extract_hf_cookies.py
```

The script reads Chrome's local cookie database (already on your
machine, encrypted with DPAPI on Windows / Keychain on macOS) and
writes `HIGGSFIELD_CLERK_CLIENT` + `HIGGSFIELD_JWT` to `.env` for you.

Common options:

```bash
py -3.14 scripts/extract_hf_cookies.py --browser edge        # use Edge
py -3.14 scripts/extract_hf_cookies.py --browser brave       # use Brave
py -3.14 scripts/extract_hf_cookies.py --profile "Profile 1" # second Chrome profile
py -3.14 scripts/extract_hf_cookies.py --dry-run             # preview without writing
```

If Chrome is still running when you run the script, Windows locks the
cookie database. Close all Chrome windows (including any in the system
tray) and retry. macOS/Linux don't have this lock.

### Fallback: manual extraction via DevTools

If the script can't read your browser for some reason, you can copy the
cookies by hand:

1. Open <https://cloud.higgsfield.ai> in Chrome. Make sure you're logged
   in.
2. Open dev tools: `F12` (Windows) or `Cmd-Opt-I` (macOS). If F12 doesn't
   open them, try the Chrome menu → **More tools** → **Developer tools**.
3. In DevTools, click the **>>** overflow arrow if you don't see
   "Application" — depending on window width, it can be hidden. Then
   switch to the **Application** tab.
4. Left sidebar: **Cookies** → `https://cloud.higgsfield.ai`.
5. Find these two cookies in the table:
   - **`__client`** — long-lived (~7 days). Click the row, then the
     **Cookie Value** field at the bottom — Ctrl+A then Ctrl+C copies it.
   - **`__session`** — short-lived (~1 min). Same copy procedure. *Optional.*
6. Paste into your `.env`:

```env
HIGGSFIELD_CLERK_CLIENT=<paste __client value here>
HIGGSFIELD_JWT=<paste __session value here>   # optional
```

`HIGGSFIELD_JWT` is optional — if unset, the client will mint a fresh
JWT from your `__client` cookie on each call.

## Refresh schedule

- **`__session` (JWT)** expires every ~1 minute. The client auto-refreshes
  it from your `__client` cookie. You typically never touch this.
- **`__client`** expires every ~7 days. When it does, you'll see this
  error:

  ```
  HF-web auth failed: Clerk session discovery failed (401). The
  HIGGSFIELD_CLERK_CLIENT cookie has likely expired (~7 day lifetime).
  Re-extract from cloud.higgsfield.ai's __client cookie and re-paste
  into .env.
  ```

  Re-run the extraction script:

  ```
  py -3.14 scripts/extract_hf_cookies.py
  ```

## How the auth flow works

```
                        ┌─────────────────────────────┐
                        │  cloud.higgsfield.ai (login) │
                        └──────────────┬──────────────┘
                                       │ sets cookies
                                       ▼
   .env: HIGGSFIELD_CLERK_CLIENT  ←──  __client  (~7d)
         HIGGSFIELD_JWT (optional) ←─  __session (~60s)
                                       │
   ┌───────────────────────────────────┴──────────────────────────────────┐
   │                                                                      │
   │  1. _get_fresh_jwt():                                                │
   │       if env JWT not expired → use it                                │
   │       else if cached JWT not expired → use it                        │
   │       else:                                                          │
   │         GET  clerk.higgsfield.ai/v1/client (cookie __client)         │
   │              → response.last_active_session_id                       │
   │         POST clerk.higgsfield.ai/v1/client/sessions/{sid}/tokens     │
   │              → fresh JWT (~60s TTL)                                  │
   │                                                                      │
   │  2. submit_nano_banana_edit():                                       │
   │       POST fnf.higgsfield.ai/jobs/v2/nano_banana_flash               │
   │            Authorization: Bearer <jwt>                               │
   │            body: { params: { prompt, aspect_ratio, resolution,       │
   │                              input_image_urls: [...] },              │
   │                    use_unlim: false, use_free_gens: false }          │
   │       → request_id                                                   │
   │                                                                      │
   │  3. wait_for_result_url():                                           │
   │       GET fnf.higgsfield.ai/jobs?size=100, filter by request_id      │
   │       → result_url (CloudFront URL of the generated image)           │
   │                                                                      │
   └──────────────────────────────────────────────────────────────────────┘
```

## Where the image inputs come from

`hf-web` takes the same inputs as the other engines:

- The reference ad (from the run's `reference.<ext>` file)
- Your product image (from the product YAML's `image_path` or
  `image_url`)

Both are uploaded to `platform.higgsfield.ai/files/generate-upload-url`
(the existing `generators/higgsfield_client.upload_image` path) to
get public CloudFront URLs, which then go into `input_image_urls` on the
fnf submission. The upload step uses `HF_API_KEY`/`HF_API_SECRET` from
`.env` — different auth from the Clerk JWT used for the submission.
Yes, you need both.

URLs are cached in the run directory (`.reference_url.txt`,
`.product_url.txt`) so re-fires don't re-upload.

## Why not just use the `higgsfield` CLI?

The CLI (`npm i -g @higgsfield/cli`) talks to `platform.higgsfield.ai`,
the public REST API. `platform.higgsfield.ai` accepts submissions for
model `nano_banana_2` but routes them to a backend that doesn't produce
reference-faithful edits — verified empirically against the us-vs-them
PetLab reference (2026-05-22). The real edit-capable model lives at
`fnf.higgsfield.ai`, which is the path the web UI and the official MCP
use. Different host, different auth, different model behavior.

## Cost

~$0.10/brief in Higgsfield credits (one `nano_banana_flash` 1k call).
Check current rates at <https://platform.higgsfield.ai/billing>.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `HIGGSFIELD_CLERK_CLIENT is not set` | .env missing the cookie | Extract from browser, paste into .env |
| `Clerk session discovery failed (401)` | `__client` cookie expired (~7d) | Re-extract from cloud.higgsfield.ai |
| `__client cookie is for a logged-out browser` | You logged out / cleared cookies | Re-login at cloud.higgsfield.ai, extract again |
| `HF-web could not upload reference/product` | `HF_API_KEY` / `HF_API_SECRET` issue | Check those values in .env |
| `Timed out waiting for request_id` after 10 min | Generation hung or HF backend slow | Re-fire; check status at platform.higgsfield.ai/billing for credit issues |
