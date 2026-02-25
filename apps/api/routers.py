from rest_framework.routers import DefaultRouter
from apps.orgs.api.views import BranchViewSet
from apps.academics.api.views import BatchViewSet, StudentViewSet, TeacherViewSet, TimeTableSlotViewSet
from apps.attendance.api.views import ClassSessionViewSet, StudentAttendanceViewSet
from apps.billing.api.views import PaymentSettingsViewSet, FeeInvoiceViewSet, PaymentTransactionViewSet
# from apps.comms.api.views import AnnouncementViewSet
from apps.marketing.api.views import WhatsAppCampaignViewSet
from apps.reviews.api.views import ReviewViewSet
# from apps.idcards.api.views import IdCardTemplateViewSet, GeneratedIdCardViewSet
from apps.assessments.api.views import StudyMaterialViewSet, HomeworkViewSet, TestViewSet
from apps.marketing.api.views import WhatsAppCampaignViewSet
from apps.reviews.api.views import ReviewViewSet
# from apps.idcards.api.views import IdCardTemplateViewSet, GeneratedIdCardViewSet
from apps.accounts.api.views_admin import JoinRequestAdminViewSet

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branches")
router.register(r"batches", BatchViewSet, basename="batches")
router.register(r"students", StudentViewSet, basename="students")
router.register(r"teachers", TeacherViewSet, basename="teachers")
router.register(r"timetable", TimeTableSlotViewSet, basename="timetable")
# router.register(r"subjects", SubjectViewSet, basename="subjects")
router.register(r"sessions", ClassSessionViewSet, basename="sessions")
router.register(r"attendance", StudentAttendanceViewSet, basename="attendance")

router.register(r"payment-settings", PaymentSettingsViewSet, basename="payment-settings")
router.register(r"invoices", FeeInvoiceViewSet, basename="invoices")
router.register(r"transactions", PaymentTransactionViewSet, basename="transactions")

# router.register(r"announcements", AnnouncementViewSet, basename="announcements")
router.register(r"wa-campaigns", WhatsAppCampaignViewSet, basename="wa-campaigns")
router.register(r"reviews", ReviewViewSet, basename="reviews")

# router.register(r"idcard-templates", IdCardTemplateViewSet, basename="idcard-templates")
# router.register(r"idcards", GeneratedIdCardViewSet, basename="idcards")
# Assessments
router.register(r"materials", StudyMaterialViewSet, basename="materials")
router.register(r"homework", HomeworkViewSet, basename="homework")
router.register(r"tests", TestViewSet, basename="tests")

# Marketing
# router.register(r"wa-campaigns", WhatsAppCampaignViewSet, basename="wa-campaigns")

# Reviews
router.register(r"reviews", ReviewViewSet, basename="reviews")

# ID Cards
# router.register(r"idcard-templates", IdCardTemplateViewSet, basename="idcard-templates")
# router.register(r"idcards", GeneratedIdCardViewSet, basename="idcards")

router.register(r"join-requests", JoinRequestAdminViewSet, basename="join-requests")