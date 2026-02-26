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




List View: For listing all items or creating a new one.
Detail View: For retrieving, updating, or deleting a specific item (using {id}).
Resource
List URL (GET, POST)
Detail URL (GET, PUT, DELETE)
Branches	/api/branches/	/api/branches/{id}/
Batches	/api/batches/	/api/batches/{id}/
Students	/api/students/	/api/students/{id}/
Teachers	/api/teachers/	/api/teachers/{id}/
Subjects	/api/subjects/	/api/subjects/{id}/
Timetable	/api/timetable/	/api/timetable/{id}/

2. Attendance & Sessions
Resource
List URL
Detail URL
Sessions	/api/sessions/	/api/sessions/{id}/
Attendance	/api/attendance/	/api/attendance/{id}/

3. Finance & Billing
Resource
List URL
Detail URL
Payment Settings	/api/payment-settings/	/api/payment-settings/{id}/
Invoices	/api/invoices/	/api/invoices/{id}/
Transactions	/api/transactions/	/api/transactions/{id}/

4. Academics & Assessments
Resource
List URL
Detail URL
Study Materials	/api/materials/	/api/materials/{id}/
Homework	/api/homework/	/api/homework/{id}/
Tests	/api/tests/	/api/tests/{id}/

5. Communication & Marketing
Resource
List URL
Detail URL
Announcements	/api/announcements/	/api/announcements/{id}/
WA Campaigns	/api/wa-campaigns/	/api/wa-campaigns/{id}/

6. ID Cards & Admin
Resource
List URL
Detail URL
ID Templates	/api/idcard-templates/	/api/idcard-templates/{id}/
Generated IDs	/api/idcards/	/api/idcards/{id}/
Reviews	/api/reviews/	/api/reviews/{id}/
Join Requests	/api/join-requests/	/api/join-requests/{id}/

HTTP Methods Allowed by Default
For each of the URLs above, the router maps HTTP methods to ViewSet actions:

GET /api/students/ → List all students (paginated).
POST /api/students/ → Create a new student.
GET /api/students/{id}/ → Retrieve a specific student.
PUT /api/students/{id}/ → Full Update a student.
PATCH /api/students/{id}/ → Partial Update a student.
DELETE /api/students/{id}/ → Delete a student.