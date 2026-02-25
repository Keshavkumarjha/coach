from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class IdCardTemplate(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="idcard_templates")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="idcard_templates")

    name = models.CharField(max_length=120, db_index=True)
    layout_json = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="idcard_templates_created")

    class Meta:
        db_table = "idc_template"
        indexes = [models.Index(fields=["organisation", "created_at"])]


class GeneratedIdCard(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    template = models.ForeignKey(IdCardTemplate, on_delete=models.PROTECT, related_name="generated_cards")

    student = models.ForeignKey("academics.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="id_cards")
    teacher = models.ForeignKey("academics.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="id_cards")

    pdf_file = models.FileField(upload_to="idcards/", null=True, blank=True)

    class Meta:
        db_table = "idc_generated"
        indexes = [
            models.Index(fields=["template", "created_at"]),
            models.Index(fields=["student", "created_at"]),
            models.Index(fields=["teacher", "created_at"]),
        ]