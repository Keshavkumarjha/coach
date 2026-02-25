# apps/accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"  # The full folder path
    label = "accounts"      # The nickname Django uses for AUTH_USER_MODEL

