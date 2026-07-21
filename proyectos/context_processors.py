from .models import MensajePrivado, Notificacion, SoftwareConfiguracion


def chat_no_leidos(request):
    if not request.user.is_authenticated:
        return {"chat_no_leidos": 0}
    return {
        "chat_no_leidos": MensajePrivado.objects.filter(
            destinatario=request.user,
            leido=False,
        ).count()
    }


def notificaciones_usuario(request):
    if not request.user.is_authenticated:
        return {
            "notificaciones_recientes": [],
            "notificaciones_no_leidas_count": 0,
        }
    return {
        "notificaciones_recientes": request.user.notificaciones.all()[:5],
        "notificaciones_no_leidas_count": request.user.notificaciones.filter(leido=False).count(),
    }


def software_estandar(request):
    if not request.user.is_authenticated:
        return {}
    # Se filtra por organizacion: el menu no debe mostrar el software de otra empresa.
    from .views import software_de_organizacion

    return {
        'software_estandar_list': software_de_organizacion(request.user)
    }
