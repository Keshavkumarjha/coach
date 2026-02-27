# coachmaster

its saas project for coaching and tuistions

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

License: MIT

## Settings

Moved to [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:

      uv run python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Type checks

Running type checks with mypy:

    uv run mypy coachmaster

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    uv run coverage run -m pytest
    uv run coverage html
    uv run open htmlcov/index.html

#### Running tests with pytest

    uv run pytest

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally.html#using-webpack-or-gulp).

### Celery

This app comes with Celery.

To run a celery worker:

```bash
cd coachmaster
uv run celery -A config.celery_app worker -l info
```

Please note: For Celery's import magic to work, it is important _where_ the celery commands are run. If you are in the same folder with _manage.py_, you should be right.

To run [periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html), you'll need to start the celery beat scheduler service. You can start it as a standalone process:

```bash
cd coachmaster
uv run celery -A config.celery_app beat
```

or you can embed the beat service inside a worker with the `-B` option (not recommended for production use):

```bash
cd coachmaster
uv run celery -A config.celery_app worker -B -l info
```

## Deployment

The following details how to deploy this application.




# Coach Backend — Complete Fix & Install Guide

## What Was Fixed and Built

This package contains **13 production-ready files** that replace broken or missing
code in the Coach backend. Every file was audited against the actual Django models.

---

## Bug Summary

| # | File | Bug | Fix Applied |
|---|------|-----|-------------|
| 1 | `accounts/api/serializers_admin.py` | Used `review_note` / `reviewed_by` but model has `rejection_reason` / `decided_by` → `AttributeError` | Fixed field names in all `save()` + `update_fields` |
| 2 | `accounts/api/serializers_admin.py` | `ParentProfile` used but never imported → `NameError` | Added import |
| 3 | `accounts/api/serializers_admin.py` | Handled `JoinRole.TEACHER` which doesn't exist in the enum | Removed dead branch |
| 4 | `attendance/api/views.py` | `MarkedBy.STUDENT` doesn't exist; should be `MarkedBy.STUDENT_GEO` → `AttributeError` | Fixed to `STUDENT_GEO` |
| 5 | `api/student_dashboard/views.py` | `r.score` → field is `marks_obtained` | Fixed |
| 6 | `api/student_dashboard/views.py` | `r.test.max_score` → field is `total_marks` | Fixed |
| 7 | `api/student_dashboard/views.py` | `r.test.test_date` / `test__test_date` → field is `scheduled_on` | Fixed |
| 8 | `api/student_dashboard/views.py` | `ClassSession` has no `subject` FK — tried to access `.subject.name` | Removed |
| 9 | `attendance/api/views_reports.py` | `batchenrollment__batch` / `batchenrollment__status` wrong related_name; correct is `enrollments__` | Fixed |
| 10 | `api/urls.py` | Missing subscription, student-dashboard, attendance-report, and student-parent link URLs | Rewired completely |
| 11 | `marketing/api/views.py` | `send()` action monkey-patched outside class — unreliable with some DRF versions | Moved inside class |

---

## Install Instructions

Replace each file at the destination path shown:

```
OUTPUT FILE                                    DESTINATION
─────────────────────────────────────────────────────────────────────────────────
accounts__api__serializers_admin.py         → apps/accounts/api/serializers_admin.py
accounts__api__urls.py                      → apps/accounts/api/urls.py
academics__api__views.py                    → apps/academics/api/views.py
assessments__api__views.py                  → apps/assessments/api/views.py
assessments__api__serializers.py            → apps/assessments/api/serializers.py
attendance__api__views.py                   → apps/attendance/api/views.py
attendance__api__serializers.py             → apps/attendance/api/serializers.py
attendance__api__views_reports.py           → apps/attendance/api/views_reports.py
billing__api__views.py                      → apps/billing/api/views.py
billing__api__serializers.py               → apps/billing/api/serializers.py
idcards__api__serializers.py                → apps/idcards/api/serializers.py
marketing__api__views.py                    → apps/marketing/api/views.py
api__routers.py                             → apps/api/routers.py
api__urls.py                                → apps/api/urls.py
api__student_dashboard__views.py            → apps/api/student_dashboard/views.py
```

---

## Complete API Endpoint Reference

After installing, these are all the endpoints available at `/api/`:

### Auth (no token required)
```
POST  /api/auth/org-signup/
POST  /api/auth/login/
POST  /api/auth/branch-join/
POST  /api/auth/forgot-password/
POST  /api/auth/reset-password/
POST  /api/auth/token/refresh/
POST  /api/auth/change-password/     ← requires token
POST  /api/auth/logout/              ← requires token
GET   /api/profile/me/
PATCH /api/profile/me/
```

### Org & Branch
```
GET   /api/org/me/
PATCH /api/org/me/
GET/POST      /api/branches/
GET/PATCH/DEL /api/branches/{id}/
```

### Join Requests (admin)
```
GET  /api/join-requests/
GET  /api/join-requests/{id}/
POST /api/join-requests/{id}/approve/
POST /api/join-requests/{id}/reject/
```

### Academics
```
GET/POST      /api/batches/
GET/PATCH/DEL /api/batches/{id}/
GET/POST      /api/subjects/
GET/PATCH/DEL /api/subjects/{id}/
GET/POST      /api/teachers/
GET/PATCH/DEL /api/teachers/{id}/
GET/POST      /api/students/
GET/PATCH/DEL /api/students/{id}/
GET           /api/students/{id}/enrollments/
POST          /api/students/{id}/enroll/
POST          /api/students/{id}/unenroll/
GET           /api/students/{id}/parents/
POST          /api/students/{id}/link-parent/
DEL           /api/students/{id}/unlink-parent/{parent_id}/
GET           /api/parents/
GET           /api/timetable/                  ← students see own batches only
GET/POST/DEL  /api/timetable/{id}/
```

### Attendance
```
GET/POST  /api/sessions/
POST      /api/sessions/{id}/open/
POST      /api/sessions/{id}/close/
GET       /api/attendance/
POST      /api/attendance/teacher-bulk-mark/
POST      /api/attendance/student-geo-mark/
PATCH     /api/attendance/{id}/correct/
GET       /api/attendance/report/
GET       /api/attendance/student-summary/
```

### Billing
```
GET/POST      /api/payment-settings/
GET/PATCH/DEL /api/payment-settings/{id}/
GET/POST      /api/fee-plans/
GET/PATCH/DEL /api/fee-plans/{id}/
GET           /api/invoices/
GET           /api/invoices/{id}/
POST          /api/invoices/generate/       ← bulk generate for batch+period
GET           /api/invoices/my/             ← student: own invoices
GET/POST      /api/transactions/
POST          /api/transactions/{id}/approve/
POST          /api/transactions/{id}/reject/
GET           /api/subscription/
GET           /api/subscription/plans/
GET           /api/subscription/usage/
```

### Assessments
```
GET/POST      /api/materials/
GET/PATCH/DEL /api/materials/{id}/
GET/POST      /api/homework/
GET/PATCH/DEL /api/homework/{id}/
GET           /api/homework/my-submissions/  ← student: own submission history
GET/POST      /api/tests/
GET/PATCH/DEL /api/tests/{id}/
GET           /api/tests/my-results/         ← student: report card
```

### Comms
```
GET/POST      /api/announcements/
GET/PATCH/DEL /api/announcements/{id}/
GET           /api/notifications/
GET           /api/notifications/{id}/
POST          /api/notifications/{id}/read/
POST          /api/notifications/read-all/
GET           /api/notifications/unread-count/
```

### Marketing
```
GET/POST  /api/wa-campaigns/
GET/DEL   /api/wa-campaigns/{id}/
GET       /api/wa-campaigns/{id}/logs/
POST      /api/wa-campaigns/{id}/send/      ← trigger send
```

### Reviews
```
GET  /api/reviews/
POST /api/reviews/public-submit/      ← no auth needed
POST /api/reviews/{id}/approve/
POST /api/reviews/{id}/reject/
```

### ID Cards
```
GET/POST      /api/idcard-templates/
GET/PATCH/DEL /api/idcard-templates/{id}/
GET           /api/idcards/
POST          /api/idcards/generate/        ← bulk PDF generation
```

### Dashboards
```
GET /api/dashboard/                       ← admin dashboard (full payload)
GET /api/dashboard/attendance-summary/    ← batch attendance bar chart
GET /api/dashboard/fee-collection/        ← fee collection gauge
GET /api/student-dashboard/               ← student home screen
```

---

## Optional: WeasyPrint for ID Card PDFs

```bash
pip install weasyprint
```

Without WeasyPrint the generate endpoint still works but returns a stub PDF.

---

## Required Headers for All Authenticated Endpoints

```
Authorization: Bearer <access_token>
X-Org:         ORG-26-XXXXXX
X-Branch:      BR-26-XXXXXX   (optional for some org-level endpoints)
```
