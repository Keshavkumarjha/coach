"""
apps/api/urls.py  — COMPLETE UPDATED VERSION

Wires all endpoints: router, auth, profile, dashboard, student dashboard,
subscription usage, attendance reports, parent links, and standalone APIViews.

New additions vs previous version:
  - /api/student-dashboard/          StudentDashboardView
  - /api/subscription/usage/         SubscriptionUsageView
  (router auto-registers the new @action endpoints below — no extra paths needed)
    /api/invoices/my/
    /api/homework/my-submissions/
    /api/tests/my-results/
    /api/attendance/{id}/correct/
    /api/wa-campaigns/{id}/send/
    /api/timetable/ now role-aware for students
"""
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from .routers import router

# ── Auth ──────────────────────────────────────────────────────────────────────
from apps.accounts.api.views import (
    OrgSignupView, LoginView, BranchJoinRequestView,
    ForgotPasswordView, ResetPasswordView,
)
from apps.accounts.api.views_profile import ProfileMeView, ChangePasswordView, LogoutView

# ── Org ───────────────────────────────────────────────────────────────────────
from apps.orgs.api.views import OrganisationMeView, BranchViewSet
from apps.orgs.api.urls import urlpatterns as org_urlpatterns

# ── Dashboard (admin) ─────────────────────────────────────────────────────────
from apps.dashboard.api.views import AdminDashboardView




# ── Attendance reports ────────────────────────────────────────────────────────
from apps.attendance.api.views import (
    AttendanceReportView, StudentAttendanceSummaryView,
)

# ── Subscription ──────────────────────────────────────────────────────────────
from apps.billing.api.views_subscription import (
    SubscriptionDetailView,
    SubscriptionPlanListView,
    SubscriptionUsageView,        # NEW
)

# ── Parent links (non-ViewSet) ────────────────────────────────────────────────
from apps.academics.api.views_parents import (
    StudentParentsView, LinkParentView, UnlinkParentView,
)

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path("auth/org-signup/",OrgSignupView.as_view()),
    path("auth/login/",LoginView.as_view()),
    path("auth/branch-join/",BranchJoinRequestView.as_view()),
    path("auth/forgot-password/",ForgotPasswordView.as_view()),
    path("auth/reset-password/",ResetPasswordView.as_view()),
    path("auth/token/refresh/",TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/change-password/",ChangePasswordView.as_view()),
    path("auth/logout/",LogoutView.as_view()),

    # ── Profile ───────────────────────────────────────────────────────────────
    path("profile/me/",ProfileMeView.as_view()),

    # ── Org & Branch ──────────────────────────────────────────────────────────
    path("", include("apps.orgs.api.urls")),

    # ── Admin Dashboard ───────────────────────────────────────────────────────
    path("dashboard/",AdminDashboardView.as_view(),name="admin-dashboard"),
    path("dashboard/attendance-summary/",AttendanceSummaryDashboardView.as_view(), name="dashboard-attendance"),
    path("dashboard/fee-collection/",FeeCollectionDashboardView.as_view(),name="dashboard-fees"),

    # ── Student Dashboard (NEW) ───────────────────────────────────────────────
    path("student-dashboard/",StudentDashboardView.as_view(),name="student-dashboard"),

    # ── Attendance reports ────────────────────────────────────────────────────
    path("attendance/report/",AttendanceReportView.as_view(),name="attendance-report"),
    path("attendance/student-summary/",StudentAttendanceSummaryView.as_view(),name="attendance-student-summary"),

    # ── Subscription ──────────────────────────────────────────────────────────
    path("subscription/",SubscriptionDetailView.as_view(),name="subscription-detail"),
    path("subscription/plans/",SubscriptionPlanListView.as_view(),name="subscription-plans"),
    path("subscription/usage/",SubscriptionUsageView.as_view(),name="subscription-usage"),   # NEW

    # ── Parent links (per-student, uses public_id) ────────────────────────────
    path("students/<str:public_id>/parents/",
         StudentParentsView.as_view(),  name="student-parents"),
    path("students/<str:public_id>/link-parent/",
         LinkParentView.as_view(),      name="student-link-parent"),
    path("students/<str:public_id>/unlink-parent/<int:parent_id>/",
         UnlinkParentView.as_view(),    name="student-unlink-parent"),

    # ── All ViewSet CRUD (router) ─────────────────────────────────────────────
    # The following @action endpoints auto-register via the router:
    #   GET  /api/invoices/my/                 (FeeInvoiceViewSet)
    #   GET  /api/homework/my-submissions/     (HomeworkViewSet)
    #   GET  /api/tests/my-results/            (TestViewSet)
    #   PATCH /api/attendance/{id}/correct/    (StudentAttendanceViewSet)
    #   POST  /api/wa-campaigns/{id}/send/     (WhatsAppCampaignViewSet)
    #   GET/POST /api/timetable/               (now role-aware for students)
    path("", include(router.urls)),
]
