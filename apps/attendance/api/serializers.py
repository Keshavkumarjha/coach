from __future__ import annotations

import math
from django.utils import timezone
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.attendance.models import ClassSession, StudentAttendance, AttendanceStatus, MarkedBy
from apps.academics.models import Batch, StudentProfile, BatchEnrollment, EnrollmentStatus


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    # distance in meters
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(r * c)


class ClassSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassSession
        fields = [
            "id",
            "session_date",
            "start_time",
            "end_time",
            "status",
            "allow_student_self_mark",
            "max_self_mark_distance_m",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TeacherBulkMarkSerializer(serializers.Serializer):
    """
    Teacher marks attendance for a session in one call.
    payload example:
    {
      "session_id": 12,
      "records": [
        {"student_public_id": "STU-26-0000001", "status": "PRESENT"},
        {"student_public_id": "STU-26-0000002", "status": "ABSENT"}
      ]
    }
    """
    session_id = serializers.IntegerField()
    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate(self, attrs):
        # basic validation of statuses
        for r in attrs["records"]:
            if "student_public_id" not in r or "status" not in r:
                raise serializers.ValidationError("Each record requires student_public_id and status.")
            if r["status"] not in AttendanceStatus.values:
                raise serializers.ValidationError({"status": f"Invalid status {r['status']}"})
        return attrs


class StudentGeoMarkSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    status = serializers.ChoiceField(choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT)

    def validate(self, attrs):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        session = ClassSession.objects.filter(
            id=attrs["session_id"],
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).select_related("batch").first()

        if not session:
            raise serializers.ValidationError({"session_id": "Invalid session."})

        if session.status != "OPEN":
            raise serializers.ValidationError({"session_id": "Session is not open."})

        if not session.allow_student_self_mark:
            raise serializers.ValidationError({"detail": "Student self mark disabled for this session."})

        # Must be enrolled in session.batch
        student = getattr(request.user, "student_profile", None)
        if not student or student.branch_id != ctx.branch.id or student.organisation_id != ctx.organisation.id:
            raise serializers.ValidationError({"detail": "Student profile not found/invalid."})

        enrolled = BatchEnrollment.objects.filter(
            student=student, batch=session.batch, status=EnrollmentStatus.ACTIVE
        ).exists()
        if not enrolled:
            raise serializers.ValidationError({"detail": "Student is not enrolled in this batch."})

        # Branch geo center
        branch = ctx.branch
        radius = int(session.max_self_mark_distance_m or branch.geo_radius_m or 50)

        # If using PointField, you should calculate distance via PostGIS in service layer.
        # Here we support the non-PostGIS lat/lng fallback:
        if hasattr(branch, "geo_center_lat") and branch.geo_center_lat is not None and branch.geo_center_lng is not None:
            d = haversine_m(float(branch.geo_center_lat), float(branch.geo_center_lng), attrs["lat"], attrs["lng"])
        else:
            # If you haven't stored geo_center_lat/lng, you must set it in branch.
            raise serializers.ValidationError({"detail": "Branch geo center is not configured."})

        attrs["_session"] = session
        attrs["_student"] = student
        attrs["_distance_m"] = d
        attrs["_radius_m"] = radius

        if d > radius:
            raise serializers.ValidationError({"detail": f"Outside allowed radius. Distance={d}m, Allowed={radius}m."})

        return attrs