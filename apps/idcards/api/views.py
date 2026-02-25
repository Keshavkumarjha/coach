from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.idcards.models import IdCardTemplate, GeneratedIdCard
from apps.academics.models import StudentProfile, TeacherProfile


class IdCardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdCardTemplate
        fields = ["id", "name", "layout_json", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)
        return IdCardTemplate.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )


class GenerateIdCardSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    student_public_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    teacher_public_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    @transaction.atomic
    def create(self, vd):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        tpl = IdCardTemplate.objects.filter(
            id=vd["template_id"],
            organisation=ctx.organisation,
        ).first()
        if not tpl:
            raise serializers.ValidationError({"template_id": "Invalid template."})

        created = 0

        stu_ids = vd.get("student_public_ids") or []
        if stu_ids:
            students = StudentProfile.objects.filter(
                organisation=ctx.organisation, branch=ctx.branch, public_id__in=stu_ids
            )
            GeneratedIdCard.objects.bulk_create(
                [GeneratedIdCard(template=tpl, student=s) for s in students],
                ignore_conflicts=True,
            )
            created += students.count()

        tch_ids = vd.get("teacher_public_ids") or []
        if tch_ids:
            teachers = TeacherProfile.objects.filter(
                organisation=ctx.organisation, branch=ctx.branch, public_id__in=tch_ids
            )
            GeneratedIdCard.objects.bulk_create(
                [GeneratedIdCard(template=tpl, teacher=t) for t in teachers],
                ignore_conflicts=True,
            )
            created += teachers.count()

        return {"created": created}


class GeneratedIdCardSerializer(serializers.ModelSerializer):
    student_public_id = serializers.CharField(source="student.public_id", read_only=True)
    teacher_public_id = serializers.CharField(source="teacher.public_id", read_only=True)

    class Meta:
        model = GeneratedIdCard
        fields = ["id", "template", "student_public_id", "teacher_public_id", "pdf_file", "created_at"]
        read_only_fields = fields