from datetime import timedelta

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


class TemaMiddleware:
    """
    Detecta si la petición entra por /pro/ y activa el tema comercial (TrackFlow).
    El tema se guarda en sesión para persistir tras el login.
    Expone request.tema = 'pro' | 'inacap' para usarlo en templates.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si la URL empieza con /pro/, activar tema y guardarlo en sesión
        if request.path.startswith("/pro/"):
            request.session["tema"] = "pro"

        # Leer tema desde la sesión (persiste luego del login)
        request.tema = request.session.get("tema", "inacap")

        return self.get_response(request)
