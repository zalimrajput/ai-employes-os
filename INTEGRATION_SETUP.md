# Integration Setup Guide — Callback URLs & Webhook URLs

Everything you need to paste into each provider's developer console so the
OAuth + webhook flows work. **The callback paths below are the ONLY ones the
backend exposes** — register exactly these, or connects will 404.

> Replace `https://api.yourdomain.com` with your real API domain. For local
> development use `http://localhost:8000` exactly as written in the
> localhost column.

---

## 1. One-glance URL table

| Service | Type | Localhost (dev) | Production (replace domain) |
|---|---|---|---|
| **Google — Gmail, Calendar, Drive, Sheets** (ONE URL for all 4) | OAuth redirect | `http://localhost:8000/api/v1/integrations/oauth/callback/google` | `https://api.yourdomain.com/api/v1/integrations/oauth/callback/google` |
| **Microsoft — Outlook, M365, OneDrive/Excel** (ONE URL for all 3) | OAuth redirect | `http://localhost:8000/api/v1/integrations/oauth/callback/microsoft` | `https://api.yourdomain.com/api/v1/integrations/oauth/callback/microsoft` |
| **Slack** | OAuth redirect | `http://localhost:8000/api/v1/integrations/oauth/callback/slack` | `https://api.yourdomain.com/api/v1/integrations/oauth/callback/slack` |
| **Zoho CRM** | OAuth redirect | `http://localhost:8000/api/v1/integrations/oauth/callback/zoho` | `https://api.yourdomain.com/api/v1/integrations/oauth/callback/zoho` |
| **Xero** | OAuth redirect | `http://localhost:8000/api/v1/integrations/oauth/callback/xero` | `https://api.yourdomain.com/api/v1/integrations/oauth/callback/xero` |

> **Troubleshooting — provider-side OAuth errors.** These all mean the URL
> registered in the provider's app console does NOT match the string above
> (exact match required: scheme, host, port, path, no trailing slash):
>
> - **Slack / Zoho: “invalid redirect URI”** → in the provider dashboard add the
>   exact localhost URL from the table above. If you previously registered the
>   ngrok URL, either register the localhost URL too, or change the backend
>   `*_REDIRECT_URI` values to the public URL.
> - **Google: “access denied” / “Access blocked”** → the OAuth client is in
>   **Testing** mode. In Google Cloud Console → APIs & Services → OAuth consent
>   screen, add your Google account under **Test users** (or click **Publish**),
>   and make sure `gmail.readonly` / `drive.file` / `calendar.events` scopes are
>   listed. Then retry — you must click **Allow**, not Cancel.
> - **Xero / Microsoft: “redirect_uri mismatch”** → same fix: register the exact
>   URL from the table.
| **WhatsApp / Meta** | Webhook (GET verify + POST) | `http://localhost:8000/api/v1/whatsapp/webhook` | `https://api.yourdomain.com/api/v1/whatsapp/webhook` |
| **Stripe — invoice payments** | Webhook | `http://localhost:8000/api/v1/invoices/stripe-webhook` | `https://<ngrok>/api/v1/invoices/stripe-webhook` |
| **Stripe — subscriptions** | Webhook | `http://localhost:8000/api/v1/billing/stripe/webhook` | `https://<ngrok>/api/v1/billing/stripe/webhook` |

> 💡 **How one URL serves a family:** the backend encodes the actual provider
> (e.g. `gmail` vs `google-drive`) inside the OAuth `state` token, so the
> shared `/callback/google` URL knows which provider to exchange the code for.
> You register **one** redirect URI in each console and all services in that
> family work.

---

## 2. Google — Gmail + Calendar + Drive + Sheets (ONE callback URL)

**Console:** https://console.cloud.google.com/apis/credentials → **Create OAuth
2.0 Client ID** (Web application)

1. **Authorized redirect URIs** — add **just ONE**:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/google`
   - (+ the `https://api.yourdomain.com/...` equivalent when deploying)
2. **Enable APIs** (APIs & Services → Library): Gmail API, Google Calendar API, Google Drive API, Google Sheets API
3. **`.env`** (backend) — one client id for all four, and the SAME redirect URI:
   ```
   GMAIL_CLIENT_ID=<client id>
   GMAIL_CLIENT_SECRET=<client secret>
   GOOGLE_CAL_CLIENT_ID=<same client id>
   GOOGLE_CAL_CLIENT_SECRET=<client secret>
   GMAIL_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google
   GOOGLE_CAL_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google
   GOOGLE_DRIVE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google
   GOOGLE_SHEETS_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google
   ```
   Each service requests its own scope at connect time; the callback URL is shared.

---

## 3. Microsoft — Outlook + M365 + OneDrive/Excel (ONE callback URL)

**Console:** https://portal.azure.com → **App registrations** → New registration

1. **Redirect URI (Web platform)** — add **just ONE**:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/microsoft`
2. **API permissions (Delegated)**:
   - Outlook: `Mail.Read`, `Mail.Send`
   - Microsoft 365: `Calendars.ReadWrite`, `Mail.ReadWrite`, `Tasks.ReadWrite`
   - OneDrive/Excel: `Files.ReadWrite`
3. Create a **client secret** (Certificates & secrets → New client secret).
4. **`.env`** — one app + one redirect URI for all three:
   ```
   OUTLOOK_CLIENT_ID=<application (client) id>
   OUTLOOK_CLIENT_SECRET=<secret value>
   MICROSOFT_CLIENT_ID=<application (client) id>
   MICROSOFT_CLIENT_SECRET=<secret value>
   OUTLOOK_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/microsoft
   MICROSOFT_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/microsoft
   ONEDRIVE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/microsoft
   ```

---

## 4. Slack (works today)

**Console:** https://api.slack.com/apps → Your app → **OAuth & Permissions**

1. **Redirect URLs** → *Add New Redirect URL*:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/slack`
2. **Scopes (Bot Token Scopes)**: `channels:read`, `chat:write`
3. Install the app to your workspace to get the tokens.
4. **`.env`**:
   ```
   SLACK_CLIENT_ID=<client id>
   SLACK_CLIENT_SECRET=<client secret>
   SLACK_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/slack
   ```

---

## 5. WhatsApp Business Cloud API — Meta (works today)

**Console:** https://developers.facebook.com/apps → your app → WhatsApp → API Setup → Configuration

1. **Webhook URL:** `http://localhost:8000/api/v1/whatsapp/webhook`
   (production: `https://api.yourdomain.com/api/v1/whatsapp/webhook`)
2. **Verify token:** any secret string you choose — must equal `WHATSAPP_VERIFY_TOKEN`.
3. Subscribe to the **`messages`** webhook field.
4. **`.env`**:
   ```
   WHATSAPP_API_TOKEN=<system user access token>
   WHATSAPP_PHONE_ID=<whatsapp business phone number id>
   WHATSAPP_VERIFY_TOKEN=<any random string, must match the console>
   ```

---

## 6. Stripe (works today)

**Console:** https://dashboard.stripe.com/webhooks → **Add endpoint**

1. **Endpoint URLs** (create two):
   - `http://localhost:8000/api/v1/invoices/stripe-webhook` — `checkout.session.completed` (marks invoices paid + fires the paid-workflow chain)
   - `http://localhost:8000/api/v1/billing/stripe/webhook` — `customer.subscription.*` (subscriptions + billing transactions)

   **Two webhooks = two signing secrets.** Stripe gives every endpoint its own
   `whsec_…` secret:

   ```
   STRIPE_WEBHOOK_SECRET=whsec_...          # from the /invoices/stripe-webhook endpoint
   STRIPE_BILLING_WEBHOOK_SECRET=whsec_...  # from the /billing/stripe/webhook endpoint
   ```

   If you only need invoice payments (payment links), register just the
   `/invoices/stripe-webhook` endpoint and leave `STRIPE_BILLING_WEBHOOK_SECRET`
   empty.

   > **ngrok caveat:** free ngrok URLs (e.g. `xxx.ngrok-free.dev`) change on
   > every restart. If the URL changes, re-save it in Stripe/Meta and re-copy
   > the new signing secret (the old `whsec_…` stops working).
2. **Events to send:**
   - Billing: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Invoices: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`
3. Reveal the **Signing secret** for each endpoint.
4. **`.env`**:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...   (billing endpoint secret)
   ```
   > The invoice endpoint reuses `STRIPE_WEBHOOK_SECRET`; if you created two
   > endpoints with different secrets, set the invoice one too (add
   > `STRIPE_INVOICE_WEBHOOK_SECRET` support in `config.py` if needed).

---

## 7. Zoho CRM (new — works now)

**Console:** https://api-console.zoho.com → Client → *Create a self client* (or OAuth client)

1. **Authorized redirect URIs** — add:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/zoho`
2. **Scopes**: `ZohoCRM.modules.leads.ALL`, `ZohoCRM.modules.contacts.ALL`, `ZohoCRM.modules.deals.ALL`
3. **`.env`**:
   ```
   ZOHO_CLIENT_ID=<client id>
   ZOHO_CLIENT_SECRET=<client secret>
   ZOHO_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/zoho
   ```
4. (Non-`zoho.com` region? Set `ZOHO_API_BASE_URL=https://www.zohoapis.eu/crm/v2` etc. and use that region's accounts URL.)

**AI usage**: `zoho_create_lead` / `zoho_list_leads` tools — "Add John as a lead" creates the lead internally **and** in Zoho when connected.

---

## 8. Xero (new — works now)

**Console:** https://developer.xero.com/app/manage → *New app* → **OAuth 2.0**

1. **Redirect URI** — add:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/xero`
2. **Scopes**: `openid profile email accounting.transactions accounting.contacts accounting.settings offline_access`
3. Generate a **client secret**, then **`.env`**:
   ```
   XERO_CLIENT_ID=<client id>
   XERO_CLIENT_SECRET=<client secret>
   XERO_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/xero
   ```

> Xero's token endpoint uses HTTP Basic auth, and every Accounting API call
> needs the `Xero-Tenant-Id` header — the backend resolves the tenant
> automatically from the /connections endpoint and caches it, so no setup is
> needed beyond connecting.

**AI usage**: `xero_create_invoice` / `xero_list_invoices` tools — invoices are stored internally and pushed to Xero when connected.

---

## 9. Google Drive + Google Sheets (new — reuse your Google OAuth client)

**Console:** https://console.cloud.google.com/apis/credentials → your existing **OAuth 2.0 Client ID**

1. **Add these redirect URIs** to the same client:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/google-drive`
   - `http://localhost:8000/api/v1/integrations/oauth/callback/google-sheets`
2. **Enable APIs**: Google Drive API + Google Sheets API (APIs & Services → Library)
3. **`.env`** — same client as Gmail; only the redirects are new:
   ```
   GOOGLE_DRIVE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google-drive
   GOOGLE_SHEETS_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/google-sheets
   ```

**AI usage**: `drive_upload_file`, `sheets_append_row` tools.

---

## 10. OneDrive + Excel (new — reuse your Microsoft app)

**Console:** https://portal.azure.com → App registrations → your existing app

1. **Add redirect URI (Web platform)**:
   - `http://localhost:8000/api/v1/integrations/oauth/callback/onedrive`
2. **API permission (Delegated)**: `Files.ReadWrite`
3. **`.env`**:
   ```
   ONEDRIVE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/oauth/callback/onedrive
   ```

**AI usage**: `onedrive_upload_file`, `onedrive_append_excel` tools.

---

## 11. Cloud storage — AWS S3 / Cloudflare R2 (new — works now)

No code to register — just keys. Files are written locally **and** mirrored to
the bucket when configured (write-through), so existing PDF downloads keep working.

**Cloudflare R2** (dashboard.r2.cloudflarestorage.com):
```
STORAGE_PROVIDER=r2
S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=<r2 access key id>
S3_SECRET_ACCESS_KEY=<r2 secret access key>
S3_BUCKET=<bucket name>
S3_REGION=auto
```

**AWS S3**: same keys, `STORAGE_PROVIDER=s3`, `S3_ENDPOINT_URL=https://s3.<region>.amazonaws.com`, `S3_REGION=<region>`.

**AI usage**: invoice/quotation PDFs + payment QR codes are mirrored to the bucket automatically (visible in `storage_files.storage_provider`).

> ⚠️ The object URL recorded in `storage_files.url` is the raw bucket URL. For
> **private** buckets it won't be publicly downloadable — either make the
> bucket (or objects) public-read, or wire a presigned-URL endpoint before
> exposing those URLs to end users.

---

## 12. What happens after you register (the automatic flow)

```
Frontend (Settings → Integrations → Connect)
   │  GET /api/v1/integrations/oauth/connect/gmail   (JWT auth)
   ▼
Backend returns { authorize_url }  (state = <org_id>:<random>)
   │  window.location = authorize_url
   ▼
Google consent page  →  user approves
   │  302 redirect to the registered callback URL with ?code=...&state=...
   ▼
GET /api/v1/integrations/oauth/callback/gmail
   │  exchanges code → tokens, encrypts & stores per-org
   ▼
302 redirect → http://localhost:3000/dashboard/settings?tab=integrations&status=connected&provider=gmail
   │  Settings page shows "Connected" toast — no manual step
   ▼
AI employees can now call Gmail / Calendar / etc. using the stored tokens
```

---

## 13. Checks before going live

- [ ] Every `*_REDIRECT_URI` in `backend/.env` **matches the console exactly** (scheme, host, port, trailing path).
- [ ] `FRONTEND_ORIGIN` in `backend/.env` is your real frontend domain — the OAuth flow redirects the browser back there.
- [ ] `ENCRYPTION_KEY` is set (tokens are Fernet-encrypted at rest).
- [ ] `ENVIRONMENT=production` disables `/docs` and Swagger.
- [ ] For a deployed API: change all redirect URIs to `https://api.yourdomain.com/...` in **both** the provider console **and** `backend/.env`.
- [ ] After first connect, verify the row exists in the `integrations` table with `connected=true` (tokens are encrypted — never visible in plain text).
