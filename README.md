# Frame Works Prints

Clean production working copy of the iOS print-shop project.

## Layout

- `frontend/` — Expo SDK 54 / React Native 0.81 app using Expo Router
- `backend/` — FastAPI API with MongoDB, Stripe payments, and Prodigi fulfillment
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

## Prodigi catalog and fulfillment

- The Store catalog maps each selectable frame and size to an approved Prodigi SKU.
- When `PRODIGI_API_KEY` is configured, the API enriches the Store response with live
  `GET /v4.0/products/{sku}` details and uses `POST /v4.0/quotes` for server-side pricing.
- After a verified Stripe payment, the API submits the artwork and recipient to
  `POST /v4.0/orders` with an idempotency key and a public HTTPS asset URL.
- Prodigi callbacks are handled at `/api/webhooks/prodigi`; the handler re-fetches the order
  through the authenticated API before changing local status or tracking data.
- Keep `PRODIGI_SUBMIT_ORDERS=false` until sandbox testing and public asset delivery are ready.
  Never commit a Prodigi API key or webhook secret.

## Low-cost AI testing

The app no longer applies any AI style transforms to a customer's photo — the original image a
customer takes or uploads is what gets cropped, printed, and shipped, so nothing can make a
customer feel their photo was altered without consent.

The only AI-assisted feature left is the **Room Preview**, which composites the customer's
unmodified photo into a sample room scene purely for scale/visualization; it never changes the
artwork itself, and the saved/printed image always stays the customer's original crop.

The API defaults to `AI_DEMO_MODE=true`. In this mode, room previews are created locally with
Pillow, so no cloud API call or charge is made.

To deliberately test cloud image editing for the room preview:

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
Prodigi fulfillment, account deletion, and restore/error scenarios have been verified end-to-end.


- `comfy-studio/` — Pinokio ComfyUI Studio launcher
