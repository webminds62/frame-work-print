# Prodigi API setup

Frame Works uses **Prodigi** (not Printful) for print fulfillment.

## 1. Get a sandbox API key

1. Create an account: https://www.prodigi.com/
2. Open the **Sandbox** dashboard / API settings
3. Copy your **API key** (header: `X-API-Key`)

## 2. Put it in `backend/.env`

```bash
PRODIGI_API_KEY=paste_sandbox_key_here
PRODIGI_BASE_URL=https://api.sandbox.prodigi.com
PRODIGI_MARKUP=1.6
PRODIGI_DEFAULT_SHIPPING=Budget
PRODIGI_SUBMIT_ORDERS=false
PUBLIC_BASE_URL=https://YOUR_PUBLIC_HTTPS_API_HOST
```

- Keep `PRODIGI_SUBMIT_ORDERS=false` until artwork URLs are publicly reachable over **HTTPS**.
- Sandbox does **not** charge or ship real orders.

## 3. Restart the API

```bash
cd backend
# stop old process, then:
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## 4. Verify

```bash
curl -s http://127.0.0.1:8000/api/prodigi/status
# expect: "configured": true

python3 tools/prodigi_sku_probe.py
# lists US wall-art SKUs into tools/out/
```

## 5. What uses Prodigi

| Feature | Endpoint / code |
|---------|------------------|
| Status | `GET /api/prodigi/status` |
| Store catalog (gallery + SKU hints) | `GET /api/catalog/store` |
| Live cost | `POST /api/prodigi/quote` |
| After Stripe payment | `submit_prodigi_order()` when `PRODIGI_SUBMIT_ORDERS=true` |
| Status webhooks | `POST /api/webhooks/prodigi` |

Room preview does **not** need Prodigi — it composites your frame locally.

## 6. Enable real sandbox order submit

Only when:

1. `PRODIGI_API_KEY` is set  
2. `PUBLIC_BASE_URL` is `https://...` and Prodigi can `GET`  
   `{PUBLIC_BASE_URL}/api/public/project/{project_id}`  
3. You set `PRODIGI_SUBMIT_ORDERS=true`

Never commit real keys to git.
