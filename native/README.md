# Native clients

These clients are added alongside the existing Expo app during migration.

## Shared flow

1. Select a photo on-device.
2. Upload it as multipart to `POST /api/uploads/photo`; the Node backend stores it in Cloudinary.
3. Request a mockup from `POST /api/mockups`.
4. Choose a Store variant from `GET /api/catalog/store`.
5. Submit the order through `POST /api/prodigi/orders`.
6. Refresh `GET /api/orders/{id}/tracking` to show Prodigi status and shipment tracking.

Both clients require a Supabase access token and never contain Prodigi, Cloudinary, or Supabase service-role secrets.
