"""
apps/api/urls.py  — COMPLETE FINAL VERSION

Wires:
  - Auth endpoints
  - Org/Branch endpoints
  - Dashboard (admin)
  - Student dashboard
  - Subscription endpoints
  - Attendance reports
  - Student-parent link views
  - All ViewSet-registered endpoints via router
"""
from django.urls import include, path

from .routers import router

# Auth
from apps.accounts.api.views import (
    OrgSignupView,
    LoginView,
    BranchJoinRequestView,
    ForgotPasswordView,
    ResetPasswordView,
)
# from apps.accounts.api.views_profile import (
#     ProfileMeView,
#     ChangePasswordView,
#     LogoutView,
# )
from rest_framework_simplejwt.views import TokenRefreshView

# Org/Branch
from apps.orgs.api.views import OrganisationMeView

# Dashboards

from apps.attendance.api.attendance__api__views_reports import (
    AttendanceReportView, StudentAttendanceSummaryView,
)
from apps.dashboard.api.api__student_dashboard__views import StudentDashboardView
from apps.dashboard.api.views import AdminDashboardView

# Subscription
from apps.subscription.api.views import (
    SubscriptionDetailView,
    SubscriptionPlanListView,
    SubscriptionUsageView,
)

# Attendance reports
from apps.attendance.api.attendance__api__views_reports import (AttendanceReportView,StudentAttendanceSummaryView)

# Student-Parent links
# from apps.academics.api.views_parents import (
#     StudentParentsView,
#     LinkParentView,
#     UnlinkParentView,
# )

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path("auth/org-signup/",       OrgSignupView.as_view(),         name="org-signup"),
    path("auth/login/",            LoginView.as_view(),             name="login"),
    path("auth/branch-join/",      BranchJoinRequestView.as_view(), name="branch-join"),
    path("auth/forgot-password/",  ForgotPasswordView.as_view(),    name="forgot-password"),
    path("auth/reset-password/",   ResetPasswordView.as_view(),     name="reset-password"),
    path("auth/token/refresh/",    TokenRefreshView.as_view(),      name="token-refresh"),
    # path("auth/change-password/",  ChangePasswordView.as_view(),    name="change-password"),
    # path("auth/logout/",           LogoutView.as_view(),            name="logout"),

    # ── Profile ───────────────────────────────────────────────────────────────
    # path("profile/me/", ProfileMeView.as_view(), name="profile-me"),

    # ── Org ───────────────────────────────────────────────────────────────────
    path("org/me/", OrganisationMeView.as_view(), name="org-me"),

    # ── Admin Dashboards ──────────────────────────────────────────────────────
    path("dashboard/",                        AdminDashboardView.as_view(),              name="admin-dashboard"),
    # path("dashboard/attendance-summary/",     AttendanceSummaryDashboardView.as_view(),  name="dashboard-attendance"),
    # path("dashboard/fee-collection/",         FeeCollectionDashboardView.as_view(),      name="dashboard-fees"),

    # ── Student Dashboard ─────────────────────────────────────────────────────
    path("student-dashboard/", StudentDashboardView.as_view(), name="student-dashboard"),

    # ── Subscription ──────────────────────────────────────────────────────────
    path("subscription/",        SubscriptionDetailView.as_view(),    name="subscription"),
    path("subscription/plans/",  SubscriptionPlanListView.as_view(),  name="subscription-plans"),
    path("subscription/usage/",  SubscriptionUsageView.as_view(),     name="subscription-usage"),

    # ── Attendance Reports ────────────────────────────────────────────────────
    path("attendance/report/",          AttendanceReportView.as_view(),          name="attendance-report"),
    path("attendance/student-summary/", StudentAttendanceSummaryView.as_view(),  name="attendance-summary"),

    # ── Student-Parent Links ──────────────────────────────────────────────────
    # path("students/<str:public_id>/parents/",                StudentParentsView.as_view(), name="student-parents"),
    # path("students/<str:public_id>/link-parent/",            LinkParentView.as_view(),     name="link-parent"),
    # path("students/<str:public_id>/unlink-parent/<int:parent_id>/", UnlinkParentView.as_view(), name="unlink-parent"),

    # ── All ViewSets (Router-generated CRUD + custom actions) ─────────────────
    path("", include(router.urls)),
]
