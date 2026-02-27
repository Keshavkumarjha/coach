"""
attendance/api/serializers.py  — COMPLETE VERSION
"""
from __future__ import annotations

from rest_framework import serializers

from apps.attendance.models import (
    ClassSession,
    StudentAttendance,
    AttendanceStatus,
)
from apps.academics.models import StudentProfile
from apps.common.tenant import get_tenant_context


class ClassSessionSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = ClassSession
        fields = [
            "id",
            "batch",
            "batch_name",
            "session_date",
            "start_time",
            "end_time",
            "status",
            "allow_student_self_mark",
            "max_self_mark_distance_m",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "batch_name"]


class AttendanceRecordInputSerializer(serializers.Serializer):
    """Single row in teacher bulk mark."""
    student_public_id = serializers.CharField()
    status            = serializers.ChoiceField(choices=AttendanceStatus.choices)


class TeacherBulkMarkSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    records    = AttendanceRecordInputSerializer(many=True, min_length=1)


class StudentGeoMarkSerializer(serializers.Serializer):
    """
    Student self-marks attendance with GPS coords.
    Validates the session is open and student is within geo-fence.
    Sets _session, _student, _distance_m on validated_data.
    """
    session_id = serializers.IntegerField()
    lat        = serializers.FloatField()
    lng        = serializers.FloatField()
    status     = serializers.ChoiceField(
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )

    def validate(self, attrs):
        request = self.context["request"]
        ctx     = get_tenant_context(request)

        session = ClassSession.objects.select_related("batch", "batch__branch").filter(
            id=attrs["session_id"],
            organisation=ctx.organisation,
        ).first()
        if not session:
            raise serializers.ValidationError({"session_id": "Session not found."})

        from apps.attendance.models import SessionStatus
        if session.status != SessionStatus.OPEN:
            raise serializers.ValidationError({"session_id": "Session is not open for self-marking."})
        if not session.allow_student_self_mark:
            raise serializers.ValidationError({"session_id": "Self-marking is not enabled for this session."})

        student = StudentProfile.objects.filter(
            user=request.user,
            organisation=ctx.organisation,
        ).first()
        if not student:
            raise serializers.ValidationError({"detail": "Student profile not found."})

        # Basic distance check using branch geo-center (without PostGIS)
        import math
        branch = session.batch.branch if hasattr(session.batch, "branch") else ctx.branch
        distance_m = 0

        if branch and hasattr(branch, "geo_center_lat") and branch.geo_center_lat:
            lat1 = float(branch.geo_center_lat)
            lng1 = float(branch.geo_center_lng)
            lat2 = attrs["lat"]
            lng2 = attrs["lng"]

            # Haversine
            R = 6371000
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            d_phi = math.radians(lat2 - lat1)
            d_lam = math.radians(lng2 - lng1)
            a     = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
            distance_m = int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

            if distance_m > session.max_self_mark_distance_m:
                raise serializers.ValidationError({
                    "detail": f"You are {distance_m}m from the branch. Max allowed: {session.max_self_mark_distance_m}m."
                })

        attrs["_session"]    = session
        attrs["_student"]    = student
        attrs["_distance_m"] = distance_m
        return attrs


class StudentAttendanceSerializer(serializers.ModelSerializer):
    session_date       = serializers.DateField(source="session.session_date", read_only=True)
    batch_name         = serializers.CharField(source="batch.name",          read_only=True)
    student_public_id  = serializers.CharField(source="student.public_id",   read_only=True)
    student_name       = serializers.CharField(source="student.user.full_name", read_only=True)

    class Meta:
        model = StudentAttendance
        fields = [
            "id",
            "session",
            "session_date",
            "batch",
            "batch_name",
            "student",
            "student_public_id",
            "student_name",
            "status",
            "marked_by_type",
            "marked_at",
        ]
        read_only_fields = fields
