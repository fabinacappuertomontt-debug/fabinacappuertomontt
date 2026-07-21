from datetime import timedelta

from django.shortcuts import redirect
from django.utils import timezone


class UltimaActividadMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = timezone.now()
            ultima = request.user.ultima_actividad
            if not ultima or ahora - ultima > timedelta(minutes=1):
                request.user.ultima_actividad = ahora
                request.user.save(update_fields=["ultima_actividad"])
        return self.get_response(request)


class CambioPasswordObligatorioMiddleware:
    """Obliga a cambiar la contraseña temporal antes de usar la plataforma.

    Las credenciales que genera el superadmin viajan por correo, así que dejan de
    ser secretas apenas se envían: solo valen para entrar una vez y elegir una propia.
    """

    # Rutas que siguen accesibles mientras la contraseña sigue siendo temporal.
    RUTAS_PERMITIDAS = (
        "/cuenta/cambiar-clave/",
        "/logout",
        "/accounts/logout",
        "/control/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            usuario is not None
            and usuario.is_authenticated
            and getattr(usuario, "debe_cambiar_password", False)
            and not request.path.startswith(self.RUTAS_PERMITIDAS)
        ):
            return redirect("cambiar_password_obligatorio")
        return self.get_response(request)


class TemaMiddleware:
    """
    Detecta si la petición entra por /pro/ y activa el tema comercial (TrackFlow).
    El tema se guarda en sesión para persistir tras el login.
    Expone request.tema = 'pro' | 'base' para usarlo en templates.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si la URL empieza con /pro/, activar tema y guardarlo en sesión
        if request.path.startswith("/pro/"):
            request.session["tema"] = "pro"

        # Leer tema desde la sesión (persiste luego del login)
        request.tema = request.session.get("tema", "base")

        return self.get_response(request)
