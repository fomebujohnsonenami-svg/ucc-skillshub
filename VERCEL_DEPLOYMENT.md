# UCC Skillshub — one-project Vercel deployment

This repository keeps the existing HTML/CSS/JavaScript UI and Django REST Framework API together. **Choose Django** as the framework and **./** as the root directory. Vercel detects `manage.py`, runs Django using its WSGI entry point, and collects approved frontend assets to its CDN.

The existing frontend page routes are preserved; the landing page is available at `/`. Existing links such as `/ucc_skillshub_sign_in/code.html` remain valid, and API endpoints remain under `/api/v1/`. The application uses Supabase for its PostgreSQL database and private uploads, including generated certificate PDFs on Vercel.

## Vercel environment variables

Add these in Vercel > Project > Settings > Environment Variables. **Do not** upload a filled-in `.env` file or add it to Git.

- `DJANGO_SECRET_KEY`: a strong random private key
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`: your exact assigned `*.vercel.app` domain (host only; no protocol)
- `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://your-site.vercel.app`
- `DJANGO_CORS_ALLOWED_ORIGINS`: `https://your-site.vercel.app` if necessary; same-origin traffic does not require CORS
- `FRONTEND_URL=https://your-site.vercel.app/ucc_skillshub_sign_in/code.html`
- `BACKEND_URL=https://your-site.vercel.app`
- `DATABASE_URL`: Supabase PostgreSQL **session pooler** connection URI, including URL-encoded password
- `DATABASE_CONN_MAX_AGE=0` (avoid holding idle database connections across serverless invocations)
- `DATABASE_USE_TRANSACTION_POOLER=False` for the session pooler
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PROFILE_BUCKET`, `SUPABASE_PROJECT_BUCKET`, `SUPABASE_COURSE_BUCKET`, `SUPABASE_APPLICATION_BUCKET`, `SUPABASE_SIGNED_URL_TTL`
- `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`

The four named Supabase Storage buckets must exist and be **private**. Certificates share the configured course-resources bucket under `certificates/`. Keep the service-role key server-side only. Use the exact production hostname Vercel assigns; for preview deployments, Django also accepts Vercel's own `VERCEL_URL` if available.

## Database migrations (one-time and when models change)

Do not run migrations automatically on every build or preview deployment. From a trusted local terminal, configure your private `.env` with the **production** Supabase database connection, review migrations first, and execute:

```bash
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate
```

Create an admin with `python manage.py createsuperuser` if one does not yet exist. Ensure backups and approval before migrating an existing populated database.

## Verify after deploying

1. Load `/`, the sign-in page, the courses page, and the student dashboard.
2. Inspect browser Network requests: API traffic must go to `https://your-site.vercel.app/api/v1/...`, **not localhost**.
3. Check `/api/v1/docs/` and `/admin/`.
4. Test registration, verification email, login, enrolment and certificate download using test accounts.
5. Confirm uploaded images and certificate PDFs remain accessible after a new deployment.

**Known caveats:** Google/LinkedIn OAuth is not implemented in the current application. The existing UI's Google button remains disabled. Browser-loaded Tailwind CDN and other third-party resources require internet access. Serverless request duration, memory and outbound SMTP availability must be tested on your Vercel plan. This branch changes deployment wiring, not those unimplemented product features.
