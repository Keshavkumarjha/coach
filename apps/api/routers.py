"""
apps/api/routers.py  — COMPLETE FINAL VERSION

Registers all ViewSets across every app.
"""
from rest_framework.routers import DefaultRouter

from apps.orgs.api.views import BranchViewSet
from apps.academics.api.views import (
    BatchViewSet,
    StudentViewSet,
    TeacherViewSet,
    SubjectViewSet,
    TimeTableSlotViewSet,
)
# from apps.academics.api.views_parents import ParentProfileViewSet
from apps.attendance.api.views import ClassSessionViewSet, StudentAttendanceViewSet
from apps.billing.api.views import (
    PaymentSettingsViewSet,
    FeeInvoiceViewSet,
    PaymentTransactionViewSet,
)
# from apps.billing.api.views_fee_plans import FeePlanViewSet
from apps.comms.api.views import AnnouncementViewSet
# from apps.comms.api.views_notifications import NotificationViewSet
from apps.marketing.api.views import WhatsAppCampaignViewSet
from apps.reviews.api.views import ReviewViewSet
from apps.idcards.api.views import IdCardTemplateViewSet, GeneratedIdCardViewSet
from apps.assessments.api.views import StudyMaterialViewSet, HomeworkViewSet, TestViewSet
from apps.accounts.api.views_admin import JoinRequestAdminViewSet

router = DefaultRouter()

# ── Org & Branch ──────────────────────────────────────────────────────────────
router.register(r"branches", BranchViewSet, basename="branches")

# ── Academics ─────────────────────────────────────────────────────────────────
router.register(r"batches",   BatchViewSet,         basename="batches")
router.register(r"subjects",  SubjectViewSet,       basename="subjects")
router.register(r"students",  StudentViewSet,       basename="students")
router.register(r"teachers",  TeacherViewSet,       basename="teachers")
router.register(r"timetable", TimeTableSlotViewSet, basename="timetable")

# ── Parents ───────────────────────────────────────────────────────────────────
# router.register(r"parents", ParentProfileViewSet, basename="parents")

# ── Attendance ────────────────────────────────────────────────────────────────
router.register(r"sessions",   ClassSessionViewSet,      basename="sessions")
router.register(r"attendance", StudentAttendanceViewSet,  basename="attendance")

# ── Billing ───────────────────────────────────────────────────────────────────
router.register(r"payment-settings", PaymentSettingsViewSet,    basename="payment-settings")
# router.register(r"fee-plans",        FeePlanViewSet,            basename="fee-plans")
router.register(r"invoices",         FeeInvoiceViewSet,         basename="invoices")
router.register(r"transactions",     PaymentTransactionViewSet, basename="transactions")

# ── Comms ─────────────────────────────────────────────────────────────────────
router.register(r"announcements", AnnouncementViewSet, basename="announcements")
# router.register(r"notifications", NotificationViewSet, basename="notifications")

# ── Assessments ───────────────────────────────────────────────────────────────
router.register(r"materials", StudyMaterialViewSet, basename="materials")
router.register(r"homework",  HomeworkViewSet,       basename="homework")
router.register(r"tests",     TestViewSet,           basename="tests")

# ── Marketing ─────────────────────────────────────────────────────────────────
router.register(r"wa-campaigns", WhatsAppCampaignViewSet, basename="wa-campaigns")

# ── Reviews ───────────────────────────────────────────────────────────────────
router.register(r"reviews", ReviewViewSet, basename="reviews")

# ── ID Cards ──────────────────────────────────────────────────────────────────
router.register(r"idcard-templates", IdCardTemplateViewSet,  basename="idcard-templates")
router.register(r"idcards",          GeneratedIdCardViewSet, basename="idcards")

# ── Admin: Join Requests ──────────────────────────────────────────────────────
router.register(r"join-requests", JoinRequestAdminViewSet, basename="join-requests")
