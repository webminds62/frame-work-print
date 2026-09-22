# Frame Works Node backend

NestJS backend for Supabase auth/storage, Prodigi catalog/orders, and Cloudinary media.

Source layout:

```text
src/
	modules/upload/   # Cloudinary photo uploads
	modules/mockup/   # Cloudinary mockup URLs
	modules/frames/   # Store catalog, Prodigi products, quotes
	modules/orders/   # Supabase orders, Prodigi submission, tracking
	common/           # Prodigi and Cloudinary clients
```

## Setup

```bash
cd backend-node
cp .env.example .env
npm install
npm run dev
```

Build for production with `npm run build`, then run `npm start`.

Main routes:

- `GET /api/catalog/store` and `GET /api/catalog/prodigi/:sku`
- `POST /api/upload/photo` and `POST /api/mockups`
- `POST /api/prodigi/quote` and `POST /api/orders/submit`
- `GET /api/orders` and `GET /api/orders/:id/tracking`
- `POST /api/webhooks/prodigi?token=...`

Use `https://api.sandbox.prodigi.com` with a sandbox key while testing. Change
`PRODIGI_BASE_URL` to `https://api.prodigi.com` only for live fulfillment.

Run `supabase/schema.sql` in the Supabase SQL editor before creating orders.
Never expose `SUPABASE_SERVICE_ROLE_KEY`, `PRODIGI_API_KEY`, or the Cloudinary secret to Expo.
