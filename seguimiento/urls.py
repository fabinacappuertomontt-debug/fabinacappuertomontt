from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "pro/login/",
        auth_views.LoginView.as_view(template_name="registration/login_pro.html"),
        name="login_pro",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("proyectos.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
