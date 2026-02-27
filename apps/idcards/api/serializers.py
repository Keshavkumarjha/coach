"""
idcards/api/serializers.py  — COMPLETE VERSION

IdCardTemplate CRUD serializer + GenerateIdCardSerializer that produces real PDFs.

PDF generation uses WeasyPrint if available (pip install weasyprint).
Falls back to a minimal stub PDF if WeasyPrint is not installed so the endpoint
doesn't break in development.
"""
from __future__ import annotations

import io
from django.core.files.base import ContentFile
from rest_framework import serializers

from apps.idcards.models import IdCardTemplate, GeneratedIdCard
from apps.academics.models import StudentProfile, TeacherProfile
from apps.common.tenant import get_tenant_context


class IdCardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdCardTemplate
        fields = [
            "id",
            "name",
            "layout_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GeneratedIdCardSerializer(serializers.ModelSerializer):
    student_name  = serializers.SerializerMethodField()
    teacher_name  = serializers.SerializerMethodField()
    pdf_url       = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = GeneratedIdCard
        fields = [
            "id",
            "template",
            "template_name",
            "student",
            "student_name",
            "teacher",
            "teacher_name",
            "pdf_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj) -> str | None:
        return obj.student.user.full_name if obj.student else None

    def get_teacher_name(self, obj) -> str | None:
        return obj.teacher.user.full_name if obj.teacher else None

    def get_pdf_url(self, obj) -> str | None:
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None


class GenerateIdCardSerializer(serializers.Serializer):
    """
    Bulk generate ID cards as PDFs.

    Body:
        template_id            int   required
        student_public_ids     list  optional  ["STU-26-0000001", ...]
        teacher_public_ids     list  optional  ["TCH-26-0000001", ...]
    """
    template_id         = serializers.IntegerField()
    student_public_ids  = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, default=list
    )
    teacher_public_ids  = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, default=list
    )

    def validate(self, attrs):
        if not attrs.get("student_public_ids") and not attrs.get("teacher_public_ids"):
            raise serializers.ValidationError(
                "Provide at least one of student_public_ids or teacher_public_ids."
            )
        return attrs

    def save(self) -> dict:
        request = self.context["request"]
        ctx     = get_tenant_context(request)
        vd      = self.validated_data

        template = IdCardTemplate.objects.filter(
            id=vd["template_id"],
            organisation=ctx.organisation,
        ).first()
        if not template:
            raise serializers.ValidationError({"template_id": "Template not found for this organisation."})

        created  = 0
        failed   = 0
        card_urls = []

        # Students
        for pub_id in vd.get("student_public_ids", []):
            student = StudentProfile.objects.select_related("user", "branch").filter(
                public_id=pub_id, organisation=ctx.organisation
            ).first()
            if not student:
                failed += 1
                continue
            try:
                pdf_bytes = self._generate_pdf(template, student=student)
                card      = GeneratedIdCard.objects.create(
                    template=template,
                    student=student,
                )
                filename = f"idcards/{ctx.organisation.id}/{pub_id}.pdf"
                card.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
                if card.pdf_file:
                    card_urls.append(card.pdf_file.url)
                created += 1
            except Exception:
                failed += 1

        # Teachers
        for pub_id in vd.get("teacher_public_ids", []):
            teacher = TeacherProfile.objects.select_related("user", "branch").filter(
                public_id=pub_id, organisation=ctx.organisation
            ).first()
            if not teacher:
                failed += 1
                continue
            try:
                pdf_bytes = self._generate_pdf(template, teacher=teacher)
                card      = GeneratedIdCard.objects.create(
                    template=template,
                    teacher=teacher,
                )
                filename = f"idcards/{ctx.organisation.id}/{pub_id}.pdf"
                card.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
                if card.pdf_file:
                    card_urls.append(card.pdf_file.url)
                created += 1
            except Exception:
                failed += 1

        return {"created": created, "failed": failed, "card_urls": card_urls}

    # ── PDF generation ────────────────────────────────────────────────────────

    def _generate_pdf(
        self,
        template: IdCardTemplate,
        student: StudentProfile | None = None,
        teacher: TeacherProfile | None = None,
    ) -> bytes:
        html = self._render_html(template, student=student, teacher=teacher)
        return self._html_to_pdf(html)

    def _render_html(self, template: IdCardTemplate, **kwargs) -> str:
        layout = template.layout_json
        bg     = layout.get("background_color", "#ffffff")
        logo   = layout.get("logo_url", "")
        fields = layout.get("fields", [])

        profile = kwargs.get("student") or kwargs.get("teacher")
        user    = profile.user if profile else None
        org     = template.organisation

        # Build field values from person data
        def _field_value(field_name: str) -> str:
            mapping = {
                "name":         user.full_name if user else "",
                "mobile":       user.mobile    if user else "",
                "admission_no": getattr(profile, "admission_no", ""),
                "roll_no":      getattr(profile, "roll_no", ""),
                "employee_id":  getattr(profile, "employee_id", ""),
                "designation":  getattr(profile, "designation", ""),
                "public_id":    profile.public_id if profile else "",
                "batch":        _get_batch(profile),
                "branch":       profile.branch.name if profile and hasattr(profile, "branch") and profile.branch else "",
                "org":          org.name,
            }
            return mapping.get(field_name, field_name)

        # Overlay fields as positioned text
        fields_html = ""
        for f in fields:
            val   = _field_value(f.get("name", ""))
            x     = f.get("x", 0)
            y     = f.get("y", 0)
            fsize = f.get("font_size", 12)
            color = f.get("color", "#000000")
            fields_html += (
                f'<div style="position:absolute;left:{x}px;top:{y}px;'
                f'font-size:{fsize}px;color:{color}">{val}</div>\n'
            )

        logo_html = f'<img src="{logo}" style="max-height:50px;margin-bottom:8px"/>' if logo else ""

        return f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"/>
<style>
  body {{ margin: 0; padding: 0; }}
  .card {{ width: 300px; height: 200px; background: {bg}; position: relative;
           border: 1px solid #ccc; font-family: Arial, sans-serif; padding: 16px; box-sizing: border-box; }}
  h2 {{ margin: 0 0 4px 0; font-size: 14px; }}
  p  {{ margin: 2px 0; font-size: 11px; }}
</style>
</head><body>
<div class="card">
  {logo_html}
  <h2>{org.name}</h2>
  <p><b>Name:</b> {user.full_name if user else ""}</p>
  <p><b>ID:</b> {profile.public_id if profile else ""}</p>
  <p><b>Mobile:</b> {user.mobile if user else ""}</p>
  {fields_html}
</div>
</body></html>"""

    @staticmethod
    def _html_to_pdf(html: str) -> bytes:
        try:
            from weasyprint import HTML
            return HTML(string=html).write_pdf()
        except ImportError:
            # Stub minimal PDF if WeasyPrint not installed
            return (
                b"%PDF-1.4\n1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
                b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 200 100]>>endobj\n"
                b"xref\n0 4\n0000000000 65535 f\n"
                b"trailer<</Size 4 /Root 1 0 R>>\n%%EOF\n"
            )


def _get_batch(profile) -> str:
    if profile is None:
        return ""
    try:
        from apps.academics.models import BatchEnrollment, EnrollmentStatus
        enrollment = BatchEnrollment.objects.filter(
            student=profile, status=EnrollmentStatus.ACTIVE
        ).select_related("batch").first()
        return enrollment.batch.name if enrollment else ""
    except Exception:
        return ""
