from django.urls import include, path
from .routers import router
from apps.accounts.api.urls import urlpatterns as auth_urls

urlpatterns = [
    # path("", include(auth_urls)),
    # path("", include(router.urls)),
    path("auth/", include("apps.accounts.api.urls")),     # APIViews
    path("", include("apps.orgs.api.urls")),              # mix
    path("", include(router.urls)),                       # routers for CRUD
]
