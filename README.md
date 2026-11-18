# UCC SKILLSHUB backend

Django REST Framework API foundation for UCC SKILLSHUB. The existing HTML frontend remains in place. API routes use `/api/v1/`; Django ORM and migrations manage the single application database in Supabase PostgreSQL.

## Local setup (Windows PowerShell)

1. Install Python 3.12 or newer and PostgreSQL connectivity to your Supabase project.
2. Create and activate a virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`. Set `DJANGO_SECRET_KEY` (generate one with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`), `DATABASE_URL`, and Supabase storage settings. Set `DJANGO_DEBUG=True` for local development.
4. In Supabase, use the PostgreSQL **session pooler** connection string (recommended for Django) or the direct PostgreSQL connection string, with `sslmode=require`. Put that URL in `DATABASE_URL`; URL-encode special characters in the database password. If using the transaction pooler, set `DATABASE_USE_TRANSACTION_POOLER=True`.
5. Create private Supabase Storage buckets named by `SUPABASE_PROFILE_BUCKET`, `SUPABASE_PROJECT_BUCKET`, and `SUPABASE_COURSE_BUCKET` (defaults: `profile-photos`, `project-attachments`, `course-resources`). Keep them private. Only the Django server uses `SUPABASE_SERVICE_ROLE_KEY`; never place it in frontend code or expose it in an API response.
6. Apply migrations and create the first administrator:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

   Registration starts a short-lived onboarding flow. Students must select Student, provide an exact `@ucc.edu.gh` address, and confirm the six-digit email code before activation. Facilitator and Recruiter requests remain pending until an administrator approves them.
7. Start the API with `python manage.py runserver`. Serve the existing static HTML through a local web server (for example, VS Code Live Server on port 5500); configure its origin in `DJANGO_CORS_ALLOWED_ORIGINS`. The sign-in page defaults to `http://127.0.0.1:8000/api/v1`; deployments can set `window.SKILLSHUB_API_BASE_URL` before its inline authentication script.

Configure SMTP (`DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and TLS settings) before production use; verification codes are sent only to the supplied UCC student email and are never returned by the API or logged. Set `FRONTEND_URL` to the existing sign-in page. The existing sign-in page provides registration, role selection, student verification, legacy account verification, and password reset without replacing its design.

Google and LinkedIn sign-in are enabled only when the corresponding client ID and secret are configured. Register these exact callback URLs with the providers:

- `https://<your-api-host>/api/v1/auth/oauth/google/callback/`
- `https://<your-api-host>/api/v1/auth/oauth/linkedin/callback/`

Set `BACKEND_URL` to the API origin and `FRONTEND_URL` to the sign-in page URL. OAuth uses server-side code exchange, signed identity tokens, nonce/state validation, and PKCE. Provider credentials remain on the Django server.

## API documentation

- Swagger UI: `/api/v1/docs/`
- ReDoc: `/api/v1/redoc/`
- OpenAPI schema: `/api/v1/schema/`
- Django administration: `/admin/`

## Authentication and authorization

- Login uses email and password. Access tokens expire after 10 minutes; refresh tokens expire after one day, rotate, and are blacklisted after logout/rotation.
- Registration never accepts a client-supplied role. A signed, time-limited onboarding token permits only role selection and email verification; it is not an API access token.
- Student addresses are trimmed, normalized to lowercase, and must use the exact `@ucc.edu.gh` domain (subdomains are not accepted). Student accounts stay inactive until a six-digit code is confirmed. Codes expire after 10 minutes, allow five failed attempts, and can be resent after a 60-second cooldown.
- Existing student accounts that have not yet verified a UCC address can start verification from the sign-in page using their account password. Student course, pathway, and profile access requires a verified address.
- Facilitator and Recruiter accounts remain pending until an administrator approves them through the role-approval API. The system does not connect to the official UCC portal or claim institutional verification beyond control of the supplied email address.
- Password reset requests return the same response whether or not an active email exists. Reset confirmation uses the one-time UID/token sent by email.
- Student profile endpoints are restricted to the authenticated owner. Role and account status are read-only in `/users/me/`; administrators alone may change account status.
- Uploaded profile images are type-checked, size-limited, stored in the private profile bucket, and served through expiring signed URLs. The storage service also supports private project-attachment and course-resource buckets for later modules.
- Google and LinkedIn buttons are disabled until server-side OAuth credentials and callback URLs are configured. Provider identity is not auto-linked to an existing password account by email.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/register/` | Create an account and receive a scoped onboarding token |
| POST | `/api/v1/auth/role-selection/` | Select Student, Facilitator, or Recruiter and start verification/approval |
| POST | `/api/v1/auth/student-email/start/` | Start verification for a legacy active Student account |
| POST | `/api/v1/auth/student-email/verify/` | Confirm a six-digit UCC student email code |
| POST | `/api/v1/auth/student-email/resend/` | Resend a code after the cooldown |
| POST | `/api/v1/auth/login/` | Obtain JWT access and refresh tokens using email/password |
| POST | `/api/v1/auth/logout/` | Blacklist the authenticated user's refresh token |
| POST | `/api/v1/auth/token/refresh/` | Rotate refresh token and obtain an access token |
| POST | `/api/v1/auth/password-reset/` | Request a password-reset email |
| POST | `/api/v1/auth/password-reset/confirm/` | Confirm a reset with UID, token, and new password |
| POST | `/api/v1/auth/change-password/` | Change the authenticated user's password |
| GET, PATCH | `/api/v1/users/me/` | Read or update the authenticated user's name/username |
| POST | `/api/v1/users/me/profile-photo/` | Upload or replace a private profile photo |
| GET, PATCH | `/api/v1/students/me/profile/` | Read or update the authenticated student's profile |
| PATCH | `/api/v1/admin/users/{uuid}/status/` | Administrator activation, suspension, or deactivation |
| GET | `/api/v1/admin/role-approvals/` | List pending Facilitator and Recruiter requests |
| POST | `/api/v1/admin/role-approvals/{uuid}/decision/` | Approve or reject a role request |
| GET | `/api/v1/auth/oauth/providers/` | Report which OAuth providers are configured |
| GET | `/api/v1/auth/oauth/google/` | Begin Google OAuth sign-in |
| GET | `/api/v1/auth/oauth/google/callback/` | Validate Google response and return to the sign-in page |
| GET | `/api/v1/auth/oauth/linkedin/` | Begin LinkedIn OAuth sign-in |
| GET | `/api/v1/auth/oauth/linkedin/callback/` | Validate LinkedIn response and return to the sign-in page |

## Course catalogue and learning

The existing static pages are connected to the course API: the catalogue loads published records and filters from the server, course details/curriculum and student reviews come from the API, enrolled students can open lessons and record completion, and the dashboard reads course counts and resume state from the signed-in student's enrollments.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/courses/` | Search, filter, sort, and paginate published courses |
| GET, POST | `/api/v1/courses/categories/` | List active categories and published-course counts; create a category (lecturer/administrator) |
| GET | `/api/v1/courses/{id}/` | Read published course details, curriculum, and recent reviews |
| POST | `/api/v1/courses/{id}/enroll/` | Enroll the active student; repeated enrollment is idempotent |
| GET | `/api/v1/courses/my-courses/` | List the signed-in student's enrollments and progress |
| GET | `/api/v1/courses/{id}/modules/` | Read the course curriculum |
| GET | `/api/v1/lessons/{id}/` | Read a preview or enrolled lesson and its signed resource links |
| POST | `/api/v1/lessons/{id}/complete/` | Mark an enrolled student's lesson complete and recalculate progress |
| GET, POST | `/api/v1/courses/{id}/reviews/` | List reviews or submit a review as an enrolled student |
| GET, POST | `/api/v1/courses/manage/` | List manageable courses or create a draft course (lecturer/administrator) |
| GET, PATCH | `/api/v1/courses/manage/{id}/` | Read or update a manageable course |
| GET, POST | `/api/v1/courses/manage/{id}/modules/` | List or add course modules |
| PATCH, DELETE | `/api/v1/courses/manage/modules/{id}/` | Update or remove a module |
| GET, POST | `/api/v1/courses/manage/modules/{id}/lessons/` | List or add lessons to a module |
| PATCH, DELETE | `/api/v1/courses/manage/lessons/{id}/` | Update or remove a lesson |
| POST | `/api/v1/courses/manage/lessons/{id}/resources/` | Upload a private course resource |
| POST | `/api/v1/courses/manage/{id}/thumbnail/` | Upload a course thumbnail to private storage |
| GET | `/api/v1/courses/manage/{id}/statistics/` | View course enrollment and completion statistics |

Catalogue filters accept `search`, `category` (slug or ID), `difficulty`, `duration` (`short`, `medium`, `long`), `certificate` (`true`/`false`), and `sort` (`popular`, `rated`, `newest`, `duration`). Global pagination returns 12 records per page.

Lecturers can manage only courses they created or are assigned to; administrators can manage all courses and assign instructors. Students cannot access course-management endpoints. Lesson content requires enrollment unless it is marked as a preview. Uploaded course materials and thumbnails remain in private Supabase Storage.

## Skill pathways

The Skill Pathways catalogue and student dashboard use published pathway records from the API; no demo pathways or progress are hardcoded. Lecturers create and publish pathways through the management endpoints, while students' progress is calculated from their completed pathway steps.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/pathway-categories/` | List active pathway categories |
| GET | `/api/v1/skills/` | List active skills; optional `category` slug or ID |
| GET | `/api/v1/pathways/` | Search, filter, and paginate published pathways |
| GET | `/api/v1/pathways/{id}/` | Read a published pathway, ordered steps, courses, and required skills |
| POST | `/api/v1/pathways/{id}/enroll/` | Enroll the active student; repeated enrollment is idempotent |
| GET | `/api/v1/pathways/my-pathways/` | List the signed-in student's enrollments and calculated progress |
| GET | `/api/v1/pathways/{id}/progress/` | Read the student's progress and each step's completion state |
| POST | `/api/v1/pathway-steps/{id}/complete/` | Complete an enrolled step and update pathway completion |
| GET, POST | `/api/v1/pathways/manage/categories/` | List or create categories (lecturer/administrator) |
| GET, POST | `/api/v1/pathways/manage/skills/` | List or create skills (lecturer/administrator) |
| GET, POST | `/api/v1/pathways/manage/` | List manageable pathways or create a draft |
| GET, PATCH | `/api/v1/pathways/manage/{id}/` | Read or update a manageable pathway |
| GET, POST | `/api/v1/pathways/manage/{id}/steps/` | List or add ordered learning steps |
| PATCH, DELETE | `/api/v1/pathways/manage/steps/{id}/` | Update or remove a pathway step |
| POST | `/api/v1/pathways/manage/{id}/steps/reorder/` | Reorder all pathway steps using `step_ids` |
| POST | `/api/v1/pathways/manage/{id}/thumbnail/` | Upload a private pathway thumbnail |
| GET | `/api/v1/pathways/manage/{id}/statistics/` | View enrollment and completion counts |

Catalogue filters accept `search`, `category` (slug or ID), and `difficulty` (`beginner`, `intermediate`, `advanced`, `all`). Results use the global 12-record pagination. Lecturer management is limited to pathways created by that lecturer; administrators can manage all pathways. Student enrollment and progress endpoints are restricted to the active authenticated student. Thumbnails use private Supabase Storage and short-lived signed URLs.

## Tests

The automated API tests use an in-memory SQLite database only when `DJANGO_TESTING=1` is set; normal application settings require the Supabase PostgreSQL `DATABASE_URL` and never fall back to another database.

```powershell
$env:DJANGO_SECRET_KEY = "test-only-key-that-is-at-least-thirty-two-bytes"
$env:DJANGO_TESTING = "1"
python manage.py test
```

The course API tests can be run alone with `python manage.py test courses.tests -v 1`.
The pathway API tests can be run alone with `python manage.py test pathways.tests -v 1`.

For a live database check and migration, configure the actual Supabase URL and credentials in `.env`, then run `python manage.py check` and `python manage.py migrate`.
