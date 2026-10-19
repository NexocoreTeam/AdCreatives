# Pinterest Ads API OAuth

Use Pinterest API v5 for API-based ad account, campaign, ad group, pin, and ad
management. Start with read-only verification before adding launch/write flows.

## Pinterest App Setup

In the Pinterest developer console:

- Open `https://developers.pinterest.com/apps/`.
- Use the existing AdCreatives app.
- Save the App ID / Client ID and App secret locally. Do not commit the secret.
- Add this local redirect URI:
  - `http://127.0.0.1:8787/pinterest/oauth/callback`

Recommended internal setup scopes:

```text
ads:read,ads:write,boards:read,pins:read,pins:write
```

Add these only when the workflow requires them:

```text
boards:write
catalogs:read,catalogs:write
billing:read
biz_access:read
```

Avoid `billing:write` and broad business-access writes unless there is a
specific automation need.

## Local Env

Add credentials to local `.env`:

```env
PINTEREST_CLIENT_ID=...
PINTEREST_CLIENT_SECRET=...
PINTEREST_REDIRECT_URI=http://127.0.0.1:8787/pinterest/oauth/callback
PINTEREST_SCOPES=ads:read,ads:write,boards:read,pins:read,pins:write
PINTEREST_CONTINUOUS_REFRESH=true
```

If the app was created after September 25, 2025, Pinterest automatically uses
continuous refresh tokens. Keeping `PINTEREST_CONTINUOUS_REFRESH=true` is safe
for older apps and helps avoid legacy one-year refresh tokens.

## Test OAuth

Generate the approval URL:

```powershell
cd C:\AdCreatives
py -3 cli.py pinterest auth-url
```

Start the callback server in another terminal:

```powershell
cd C:\AdCreatives
py -3 cli.py pinterest callback-server --port 8787
```

Open the printed URL and approve the app. Pinterest should redirect to:

```text
http://127.0.0.1:8787/pinterest/oauth/callback
```

On success, the CLI writes tokens to `.env` without printing their contents:

```env
PINTEREST_ACCESS_TOKEN=...
PINTEREST_REFRESH_TOKEN=...
PINTEREST_GRANTED_SCOPES=...
```

## Refresh Tokens

When the access token expires:

```powershell
cd C:\AdCreatives
py -3 cli.py pinterest refresh-token
```

## Read-Only Verification

Check local env/token/scope status:

```powershell
py -3 cli.py pinterest status
```

Read the connected Pinterest user:

```powershell
py -3 cli.py pinterest user
```

List accessible ad accounts:

```powershell
py -3 cli.py pinterest ad-accounts
```

List campaigns for one account:

```powershell
py -3 cli.py pinterest campaigns <ad_account_id>
```

## Launch Safety

Write actions should be added only after read-only account discovery is proven.
Campaign, ad group, pin, and ad creation should require an explicit confirmation
flag and print a dry-run payload first.
