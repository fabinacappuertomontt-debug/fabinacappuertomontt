from .models import MensajePrivado


def chat_no_leidos(request):
    if not request.user.is_authenticated:
        return {"chat_no_leidos": 0}
    return {
        "chat_no_leidos": MensajePrivado.objects.filter(
            destinatario=request.user,
            leido=False,
        ).count()
    }
