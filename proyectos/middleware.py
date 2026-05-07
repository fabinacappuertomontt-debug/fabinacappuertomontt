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
