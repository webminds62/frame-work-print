# Frame Works Prints

Clean production working copy of the iOS print-shop project.

## Layout

- `frontend/` — Expo SDK 54 / React Native 0.81 app using Expo Router
- `backend/` — FastAPI API with MongoDB, Stripe payments, and Printful fulfillment
- `test_reports/` — historical reports from the source archive (some mention the removed PayPal flow)
- `memory/` — historical product notes from the source archive

The untouched source archive remains one level up at `../Printstore1-main.zip`.

## Local setup

1. Copy `backend/.env.example` to `backend/.env` and use test/development values.
2. Copy `frontend/.env.example` to `frontend/.env`.
3. Install frontend dependencies with `npx expo install` so Expo selects compatible native versions.
4. Run the API with Uvicorn and the app with Expo.

## Stripe test setup

- Put a Stripe `sk_test_...` key only in `backend/.env`.
- Put its matching `pk_test_...` key in `frontend/.env`.
- In Stripe Workbench, create a webhook endpoint at
  `https://YOUR_API_HOST/api/webhooks/stripe` for `payment_intent.succeeded`.
- Put that endpoint's test signing secret (`whsec_...`) in `STRIPE_WEBHOOK_SECRET`.
- Use Stripe test cards only. No live keys are required for development.

Payment amounts are calculated by the API. The app receives only a PaymentIntent client secret,
and the API retrieves the intent from Stripe before creating an order. The signed webhook provides
recovery if the app closes after payment but before the completion request returns.

## Printful catalog and fulfillment

- The app syncs product and variant data from Printful's public Catalog API by default
  (`PRINTFUL_CATALOG_MODE=live_public`). Tests and offline development can use the bundled,
  verified snapshot with `PRINTFUL_CATALOG_MODE=snapshot`.
- Every selectable finish and size maps to an exact Printful variant ID. That ID is saved with
  the project, quote, payment, order, and fulfillment item; mismatches are rejected instead of
  silently substituting another product.
- `PRINTFUL_TOKEN` is required only for private store actions such as mockups and draft orders.
  Use a development/private token with only the permissions needed by those endpoints. If the
  token is account-level, also set `PRINTFUL_STORE_ID`; a store-level token supplies its context.
- `PUBLIC_BASE_URL` must be a public HTTPS API URL so Printful can retrieve the artwork file.
  Set `PRINTFUL_WEBHOOK_SECRET` and register
  `https://YOUR_API_HOST/api/webhooks/printful?token=YOUR_SECRET` in the selected Printful store.
- The current order call creates a draft by omitting `confirm=true`. Keep it that way during
  testing so no Printful order is charged or submitted to production.
- Webhook payloads are treated as untrusted. Before changing an order or sending a status email,
  the API fetches `GET /orders/{id}` with the private token and verifies the order ID, store,
  external local-order ID (for newly created orders), lifecycle status, and shipment ID. Tracking
  links are copied only from that authenticated response. Failed provider checks return HTTP 503
  so Printful can retry instead of silently losing the event.

Never commit a Printful token or webhook secret. Catalog product images are official Printful CDN
images; generated mockup URLs are temporary and must not be treated as durable app assets.

## Low-cost AI testing

The API defaults to `AI_DEMO_MODE=true`. In this mode, artwork styles and room previews are
created locally with Pillow, so no cloud API call or charge is made. The Style screen also runs
a local print-quality check for resolution, blur, brightness, and recommended sizes.

To deliberately test cloud image editing:

1. Keep `AI_IMAGE_QUALITY=low` and set a small `AI_DAILY_CLOUD_LIMIT` (the default is 3).
2. Put an OpenAI API key only in `backend/.env` as `OPENAI_API_KEY`.
3. Set `AI_DEMO_MODE=false` and restart the API.

Identical cloud requests are cached for 24 hours by default and do not consume another generation.
Never put the server API key in the Expo environment or commit it to GitHub.

## Before an App Store build

- Replace the inherited bundle ID in `frontend/app.json` with an identifier owned by your Apple team.
- Add the app in App Store Connect and configure signing/provisioning in EAS or Xcode.
- Configure Sign in with Apple for that bundle ID and set `APPLE_AUDIENCES` to match.
- Supply public HTTPS API/CORS origins and production database/hosting.
- Complete App Store privacy, export-compliance, support URL, privacy-policy URL, screenshots, and review metadata.
- If enabling Apple Pay, create an Apple Merchant ID and payment-processing certificate in Stripe,
  then configure StripeProvider, the Expo Stripe plugin, and PaymentSheet with that merchant ID.
- Perform a physical-device test build. Stripe's native Apple Pay path cannot be validated in Expo Go.

Do not publish or switch to Stripe live mode until test-mode payments, webhook retries, refunds,
Printful fulfillment, account deletion, and restore/error scenarios have been verified end-to-end.


- `comfy-studio/` — Pinokio ComfyUI Studio launcher
