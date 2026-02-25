from django.urls import include, path
from .routers import router
from apps.accounts.api.urls import urlpatterns as auth_urls

urlpatterns = [
    path("", include(auth_urls)),
    path("", include(router.urls)),
]