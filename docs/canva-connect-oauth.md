# Canva Connect OAuth

Use Canva Connect for API access. This is an OAuth flow, not a single API key.

## Portal Setup

In the Canva Developer Portal:

- Choose Connect API version `2026-02-02`.
- Create or use the AdCreatives integration.
- Save the Client ID and Client secret. Do not commit the secret.
- Set the default redirect URL to:
  - `https://adcreatives.nexocore.ca/canva/oauth/callback`
- Add the local dev redirect if Canva allows more than one redirect:
  - `http://127.0.0.1:8787/canva/oauth/callback`

Start with the smallest scopes that Canva's authentication guide confirms:

```text
asset:read asset:write
design:meta:read
folder:read
```

Add broader design/folder write scopes later only after Canva accepts them in
the integration portal. Skip comments, permissions, and `collaboration:event`
webhooks until a workflow requires them.

## Local Env

Add the credentials to local `.env`:

```env
CANVA_CLIENT_ID=...
CANVA_CLIENT_SECRET=...
CANVA_REDIRECT_URI=http://127.0.0.1:8787/canva/oauth/callback
CANVA_SCOPES=asset:read asset:write design:meta:read folder:read
CANVA_API_VERSION=2026-02-02
```

For local OAuth testing, `CANVA_REDIRECT_URI` must exactly match the local
redirect registered in the Canva portal. For production/tunnel testing, set it
to the HTTPS redirect instead.

## Test OAuth

Generate the approval URL:

```powershell
cd C:\AdCreatives
py -3 cli.py canva auth-url
```

Then start the callback server in another terminal:

```powershell
cd C:\AdCreatives
py -3 cli.py canva callback-server --port 8787
```

Open the printed URL, approve the app, and Canva should redirect to:

```text
http://127.0.0.1:8787/canva/oauth/callback
```

If successful, the CLI writes these values to local `.env` without printing
their contents:

```env
CANVA_ACCESS_TOKEN=...
CANVA_REFRESH_TOKEN=...
```

## Refresh Tokens

When the access token expires:

```powershell
cd C:\AdCreatives
py -3 cli.py canva refresh-token
```

## Internal API Utilities

These commands use the saved OAuth tokens. They do not print token values.

Check token/env/scope status:

```powershell
cd C:\AdCreatives
py -3 cli.py canva status
```

List recent design metadata:

```powershell
py -3 cli.py canva designs --limit 25
```

Upload a local image/video as a Canva asset:

```powershell
py -3 cli.py canva upload-asset path\to\image.png --name "SecondKind HF Output"
```

Read an uploaded asset by ID:

```powershell
py -3 cli.py canva asset <asset_id>
```

List items in a known folder ID:

```powershell
py -3 cli.py canva folder-items <folder_id>
```

### Proven With Current Scopes

- Refresh expired OAuth access tokens.
- List design metadata and edit URLs.
- Upload HF/local outputs as Canva assets.
- Read uploaded asset records.
- List known folder contents when the folder ID is available.

### Blocked Until Scopes Are Expanded

- `profile:read` for profile/account lookup.
- `design:content:read` for export/read design content.
- `design:content:write` for creating/updating design content.
- `folder:write` for creating folders or moving/organizing items.
- `brandtemplate:meta:read` for brand template discovery.

Keep comments, permissions, webhooks, and brand templates off until a workflow
actually needs them.

Magic Text does not appear to be exposed as a Canva Connect endpoint. Treat it
as a Canva UI/browser-assisted step for now: API can get assets/design metadata
into place, then the UI handles Magic Text.

## Submission Incomplete Error

Canva shows "Submission incomplete" when the OAuth flow has not been tested.
The fix is not another scope or redirect format change. The integration must
successfully complete the approval and callback exchange at least once.

If Canva only accepts the HTTPS redirect for testing, use a tunnel or small
HTTPS callback route that forwards to the local AdCreatives callback while the
integration is being verified.
