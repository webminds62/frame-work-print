Nest modules own the application flow:

- upload: authenticated photo upload to Cloudinary
- mockup: Cloudinary mockup URL generation
- frames: Store catalog, Prodigi products, and quotes
- orders: Supabase order records, Prodigi submission, and tracking

Provider clients live in `../common/`.
