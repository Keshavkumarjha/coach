from __future__ import annotations

import secrets
from django.core.cache import cache
from django.utils import timezone

OTP_TTL_SECONDS = 5 * 60  # 5 minutes
OTP_RESEND_COOLDOWN = 60  # 1 minute

def _otp_key(mobile: str) -> str:
    return f"otp:{mobile}"

def _cooldown_key(mobile: str) -> str:
    return f"otp_cd:{mobile}"

def generate_otp(mobile: str) -> str:
    # 6-digit numeric
    return f"{secrets.randbelow(1_000_000):06d}"

def send_otp_sms(mobile: str, otp: str) -> None:
    """
    Integrate with SMS provider here.
    Keep this function side-effect only.
    """
    # TODO: call provider API
    # Never log OTP in production logs.
    return

def request_password_reset_otp(mobile: str) -> None:
    if cache.get(_cooldown_key(mobile)):
        return  # silently ignore for security

    otp = generate_otp(mobile)
    cache.set(_otp_key(mobile), otp, timeout=OTP_TTL_SECONDS)
    cache.set(_cooldown_key(mobile), "1", timeout=OTP_RESEND_COOLDOWN)
    send_otp_sms(mobile, otp)

def verify_otp(mobile: str, otp: str) -> bool:
    saved = cache.get(_otp_key(mobile))
    if not saved:
        return False
    if str(saved) != str(otp):
        return False
    cache.delete(_otp_key(mobile))
    return True