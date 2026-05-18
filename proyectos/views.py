from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.core import signing
from django.utils.text import slugify
from django.views.generic import CreateView, ListView, UpdateView
from datetime import datetime, timedelta
from urllib.parse import urlencode
import json
import secrets

from .forms import (
    AjusteStockForm,
    AvanceForm,
    CodigoVerificacionForm,
    EstadoProyectoForm,
    EvidenciaForm,
    FaseProyectoForm,
    ItemInventarioForm,
    LectorCodigoBarraForm,
    MensajePrivadoForm,
    ObservacionForm,
    PerfilUsuarioForm,
    ProyectoForm,
    RegistroPublicoForm,
    TareaForm,
    UsoInventarioForm,
    UsuarioRegistroForm,
    UsuarioUpdateForm,
)
from .models import ACTIVIDAD_FASES, GENERAL_FASES, TRL_DEFINICIONES, TRL_DESCRIPCIONES, Avance, FaseProyecto, IndicadorResultado, ItemInventario, MensajePrivado, ObjetivoEspecifico, Proyecto, ResultadoEsperado, Tarea, UsoInventario, Usuario
LAB_ADMIN_EMAILS = {"fabinacappuertomontt@gmail.com"}


def usuario_es_admin_laboratorio(user):
    return bool(
        user.is_authenticated
        and (
            getattr(user, "rol", "") == Usuario.Rol.ADMINISTRADOR
            or (user.email and user.email.lower() in LAB_ADMIN_EMAILS)
        )
    )


def usuario_puede_gestionar_inventario(user):
    return bool(user.is_authenticated)


def usuario_puede_eliminar_proyecto(user):
    return bool(user.is_authenticated and user.email and user.email.lower() in LAB_ADMIN_EMAILS)


def usuario_puede_editar_proyecto(user, proyecto):
    return bool(
        usuario_es_admin_laboratorio(user)
        or proyecto.responsables.filter(pk=user.pk).exists()
    )


def exigir_permiso_edicion_proyecto(request, proyecto):
    if usuario_puede_editar_proyecto(request.user, proyecto):
        return True
    messages.error(request, "Solo el administrador o un responsable del proyecto puede modificarlo.")
    return False


def sede_usuario(user):
    return getattr(user, "sede", "puerto_montt")


def filtrar_por_sede(queryset, user, campo="sede"):
    return queryset.filter(**{campo: sede_usuario(user)})


def proyectos_de_sede(user):
    return filtrar_por_sede(Proyecto.objects.all(), user)


def inventario_de_sede(user):
    return filtrar_por_sede(ItemInventario.objects.all(), user)


def usuarios_de_sede(user):
    return filtrar_por_sede(Usuario.objects.all(), user)


def mensajes_no_leidos(user):
    if not user.is_authenticated:
        return 0
    return user.mensajes_recibidos.filter(leido=False).count()


def estado_presencia(usuario):
    if not usuario.ultima_actividad:
        return {
            "en_linea": False,
            "texto": "Sin actividad reciente",
        }
    diferencia = timezone.now() - usuario.ultima_actividad
    if diferencia <= timedelta(minutes=5):
        return {
            "en_linea": True,
            "texto": "En línea",
        }
    minutos = int(diferencia.total_seconds() // 60)
    if minutos < 60:
        return {
            "en_linea": False,
            "texto": f"Activo hace {minutos} min",
        }
    horas = minutos // 60
    if horas < 24:
        return {
            "en_linea": False,
            "texto": f"Activo hace {horas} h",
        }
    dias = horas // 24
    return {
        "en_linea": False,
        "texto": f"Activo hace {dias} d",
    }


def url_retorno_segura(request, fallback):
    url = request.POST.get("next") or request.GET.get("next")
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return fallback


def generar_codigo_verificacion():
    return f"{secrets.randbelow(1000000):06d}"


def enviar_codigo_verificacion(request, usuario):
    usuario.codigo_verificacion = generar_codigo_verificacion()
    usuario.codigo_verificacion_expira = timezone.now() + timedelta(minutes=10)
    usuario.save(update_fields=["codigo_verificacion", "codigo_verificacion_expira"])
    verificar_url = request.build_absolute_uri(reverse("verificar_correo", kwargs={"pk": usuario.pk}))
    mensaje = (
        f"Hola {usuario.nombre or usuario.username},\n\n"
        f"Tu código de confirmación es: {usuario.codigo_verificacion}\n\n"
        f"Este código vence en 10 minutos.\n"
        f"Confirmar correo: {verificar_url}\n\n"
        f"FAB INACAP"
    )
    return enviar_correo_simple(
        "Código de confirmación FAB INACAP",
        [usuario.email],
        mensaje,
    )


def token_aprobacion_usuario(usuario, accion):
    return signing.dumps({"usuario_id": usuario.pk, "accion": accion}, salt="aprobacion-usuario")


def enviar_solicitud_aprobacion_externa(request, usuario):
    admin_email = next(iter(LAB_ADMIN_EMAILS), "")
    if not admin_email:
        return False
    aprobar_url = request.build_absolute_uri(
        reverse("registro_resolver", kwargs={"token": token_aprobacion_usuario(usuario, "aprobar")})
    )
    rechazar_url = request.build_absolute_uri(
        reverse("registro_resolver", kwargs={"token": token_aprobacion_usuario(usuario, "rechazar")})
    )
    mensaje = (
        "Nueva solicitud de usuario externo.\n\n"
        f"Nombre: {usuario.nombre}\n"
        f"Correo: {usuario.email}\n"
        f"Institución/empresa: {usuario.institucion or 'No indicada'}\n"
        f"Sede solicitada: {usuario.get_sede_display()}\n\n"
        f"Aprobar: {aprobar_url}\n"
        f"Rechazar: {rechazar_url}\n"
    )
    return enviar_correo_simple(
        "Solicitud de acceso externo FAB INACAP",
        [admin_email],
        mensaje,
    )


def enviar_resultado_aprobacion(usuario, aprobado):
    if aprobado:
        asunto = "Cuenta aprobada FAB INACAP"
        mensaje = (
            f"Hola {usuario.nombre or usuario.username},\n\n"
            "Tu cuenta fue aprobada. Ya puedes iniciar sesión en el sistema FAB INACAP.\n\n"
            "FAB INACAP"
        )
    else:
        asunto = "Solicitud de cuenta rechazada FAB INACAP"
        mensaje = (
            f"Hola {usuario.nombre or usuario.username},\n\n"
            "Tu solicitud de acceso fue rechazada. Si crees que es un error, contacta al equipo FAB INACAP.\n\n"
            "FAB INACAP"
        )
    return enviar_correo_simple(asunto, [usuario.email], mensaje)


def registro_publico(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistroPublicoForm()
    if request.method == "POST":
        form = RegistroPublicoForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            if usuario.estado_registro == Usuario.EstadoRegistro.PENDIENTE_APROBACION:
                enviar_solicitud_aprobacion_externa(request, usuario)
                return redirect("registro_pendiente", pk=usuario.pk)
            elif enviar_codigo_verificacion(request, usuario):
                messages.success(request, "Te enviamos un código de confirmación al correo.")
            else:
                messages.warning(request, "Cuenta creada, pero no se pudo enviar el correo. Revisa la configuración SMTP.")
            return redirect("verificar_correo", pk=usuario.pk)
    return render(request, "registration/register.html", {"form": form})


def registro_pendiente(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk, estado_registro=Usuario.EstadoRegistro.PENDIENTE_APROBACION)
    return render(request, "registration/pending_approval.html", {"usuario": usuario})


def registro_resolver(request, token):
    try:
        datos = signing.loads(token, salt="aprobacion-usuario", max_age=60 * 60 * 24 * 7)
    except signing.BadSignature:
        messages.error(request, "El enlace de aprobación no es válido o venció.")
        return redirect("login")

    usuario = get_object_or_404(Usuario, pk=datos.get("usuario_id"))
    accion = datos.get("accion")
    if usuario.estado_registro != Usuario.EstadoRegistro.PENDIENTE_APROBACION:
        messages.info(request, "Esta solicitud ya fue resuelta.")
        return redirect("login")

    if accion == "aprobar":
        usuario.estado_registro = Usuario.EstadoRegistro.APROBADO
        usuario.correo_verificado = True
        usuario.is_active = True
        usuario.save(update_fields=["estado_registro", "correo_verificado", "is_active"])
        enviar_resultado_aprobacion(usuario, True)
        messages.success(request, f"Cuenta aprobada: {usuario.email}")
    elif accion == "rechazar":
        usuario.estado_registro = Usuario.EstadoRegistro.RECHAZADO
        usuario.is_active = False
        usuario.save(update_fields=["estado_registro", "is_active"])
        enviar_resultado_aprobacion(usuario, False)
        messages.warning(request, f"Solicitud rechazada: {usuario.email}")
    else:
        messages.error(request, "Acción no válida.")
    return redirect("login")


def verificar_correo(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk, correo_verificado=False)
    form = CodigoVerificacionForm()
    if request.method == "POST":
        if "reenviar" in request.POST:
            if enviar_codigo_verificacion(request, usuario):
                messages.success(request, "Te enviamos un nuevo código.")
            else:
                messages.error(request, "No se pudo enviar el código. Revisa la configuración del correo.")
            return redirect("verificar_correo", pk=usuario.pk)

        form = CodigoVerificacionForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data["codigo"]
            expira = usuario.codigo_verificacion_expira
            if not usuario.codigo_verificacion or not expira or timezone.now() > expira:
                form.add_error("codigo", "El código venció. Solicita uno nuevo.")
            elif codigo != usuario.codigo_verificacion:
                form.add_error("codigo", "El código no coincide.")
            else:
                usuario.correo_verificado = True
                usuario.is_active = True
                usuario.estado_registro = Usuario.EstadoRegistro.APROBADO
                usuario.codigo_verificacion = ""
                usuario.codigo_verificacion_expira = None
                usuario.save(update_fields=["correo_verificado", "is_active", "estado_registro", "codigo_verificacion", "codigo_verificacion_expira"])
                login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Correo confirmado. Ya puedes trabajar en tu sede.")
                return redirect("dashboard")
    return render(request, "registration/verify_email.html", {"form": form, "usuario": usuario})


def fase_desde_request(request, proyecto):
    fase_id = request.POST.get("fase") or request.GET.get("fase")
    if not fase_id:
        return None
    return proyecto.fases.filter(pk=fase_id).first()


@login_required
def dashboard(request):
    proyectos = proyectos_de_sede(request.user).prefetch_related("responsables", "tareas", "avances")
    contexto = {
        "total_proyectos": proyectos.count(),
        "tareas_pendientes": Tarea.objects.filter(proyecto__sede=sede_usuario(request.user)).exclude(estado=Tarea.Estado.COMPLETADA).count(),
        "proyectos_riesgo": [proyecto for proyecto in proyectos if proyecto.nivel_alerta in {"riesgo", "advertencia"}][:3],
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "total_inventario": inventario_de_sede(request.user).filter(activo=True).count(),
    }
    return render(request, "proyectos/bienvenida.html", contexto)


def puntaje_panel_proyecto(proyecto, avance, tareas_pendientes_proyecto, tareas_total, ultimo_avance):
    penalizaciones = []
    dias_sin_avance = None
    puntaje = avance
    tareas_ratio = (tareas_pendientes_proyecto / tareas_total) if tareas_total else 0

    if proyecto.esta_atrasado:
        puntaje -= 35
        penalizaciones.append("Atrasado")
    elif proyecto.dias_restantes is not None and proyecto.dias_restantes <= 7 and avance < 80:
        puntaje -= 15
        penalizaciones.append("Vence pronto")

    if tareas_pendientes_proyecto:
        penalizacion_tareas = min(25, round(tareas_ratio * 25))
        puntaje -= penalizacion_tareas
        penalizaciones.append(f"{tareas_pendientes_proyecto} tareas pendientes")

    if ultimo_avance:
        dias_sin_avance = (timezone.localdate() - ultimo_avance.fecha).days
        if dias_sin_avance > 14 and avance < 100:
            puntaje -= 10
            penalizaciones.append("Sin avances recientes")
    elif avance < 100:
        puntaje -= 8
        penalizaciones.append("Sin avances registrados")

    nivel = proyecto.nivel_alerta
    puntaje = max(0, min(100, puntaje))
    if proyecto.estado == Proyecto.Estado.FINALIZADO:
        puntaje = 100
        nivel = "ok"
    return puntaje, nivel, penalizaciones, dias_sin_avance


def construir_serie_panel_proyecto(proyecto, semanas, puntaje_actual, avance_actual, ultimo_avance):
    hoy = timezone.localdate()
    fecha_inicio = proyecto.fecha_inicio or hoy
    dias_desde_inicio = max((hoy - fecha_inicio).days, 0)
    semanas_totales = len(semanas)
    semanas_activas = max(1, min(semanas_totales, (dias_desde_inicio // 7) + 1))
    factor_inicio = 0.28 if proyecto.usa_trl else 0.38
    valor_inicial = 0 if dias_desde_inicio < 7 else round(puntaje_actual * factor_inicio)
    primera_semana_activa = max(0, semanas_totales - semanas_activas)
    serie = []

    for indice in range(semanas_totales):
        if indice < primera_semana_activa:
            progreso = 0
        else:
            progreso = (indice - primera_semana_activa) / max(semanas_activas - 1, 1)
        valor = valor_inicial + ((puntaje_actual - valor_inicial) * progreso)
        if ultimo_avance and indice >= primera_semana_activa and ultimo_avance.fecha >= hoy - timedelta(days=(semanas_totales - 1 - indice) * 7):
            valor += 3
        serie.append(max(0, min(100, round(valor))))

    serie[-1] = puntaje_actual
    return serie


@login_required
def panel_general(request):
    proyectos_qs = proyectos_de_sede(request.user).prefetch_related("responsables", "tareas", "avances")
    proyectos = list(proyectos_qs)
    for proyecto in proyectos:
        sincronizar_trl_desde_resultados(proyecto)
        sincronizar_avance_simple_desde_objetivos(proyecto)
    proyectos_ordenados = sorted(
        proyectos,
        key=lambda proyecto: (
            0 if proyecto.nivel_alerta == "riesgo" else 1 if proyecto.nivel_alerta == "advertencia" else 2,
            proyecto.fecha_fin is None,
            proyecto.fecha_fin or timezone.localdate() + timedelta(days=3650),
            proyecto.nombre.lower(),
        ),
    )
    conteo_salud = {"ok": 0, "advertencia": 0, "riesgo": 0}
    chart_colors = {"ok": "#16a34a", "advertencia": "#d97706", "riesgo": "#dc2626"}
    iconos_panel = ["people", "pc-display", "box-seam", "calendar-week", "robot", "heart-pulse", "leaf", "kanban"]
    hoy = timezone.localdate()
    semanas = []
    for indice_semana in range(7):
        inicio = hoy - timedelta(days=(6 - indice_semana) * 7)
        fin = inicio + timedelta(days=6)
        semanas.append({
            "label": f"Semana {indice_semana + 1}",
            "rango": f"{inicio.strftime('%d/%m')} - {fin.strftime('%d/%m')}",
            "es_hoy": indice_semana == 4,
        })

    proyectos_chart = []
    for indice, proyecto in enumerate(proyectos_ordenados):
        tareas_total = proyecto.tareas.count()
        tareas_pendientes_proyecto = proyecto.tareas.exclude(estado=Tarea.Estado.COMPLETADA).count()
        avance = max(0, min(100, proyecto.porcentaje_avance or 0))
        ultimo_avance = next(iter(proyecto.avances.all()), None)
        puntaje_salud, nivel, penalizaciones, dias_sin_avance = puntaje_panel_proyecto(
            proyecto,
            avance,
            tareas_pendientes_proyecto,
            tareas_total,
            ultimo_avance,
        )
        conteo_salud[nivel] = conteo_salud.get(nivel, 0) + 1

        serie = construir_serie_panel_proyecto(
            proyecto,
            semanas,
            puntaje_salud,
            avance,
            ultimo_avance,
        )

        nombre = proyecto.nombre
        proyectos_chart.append({
            "proyecto": proyecto,
            "orden": indice + 1,
            "nivel": nivel,
            "avance": avance,
            "salud": puntaje_salud,
            "serie": serie,
            "tareas_total": tareas_total,
            "tareas_pendientes": tareas_pendientes_proyecto,
            "dias_restantes": proyecto.dias_restantes,
            "responsables": proyecto.responsables.all(),
            "ultimo_avance": ultimo_avance,
            "dias_sin_avance": dias_sin_avance,
            "penalizaciones": penalizaciones,
            "color": chart_colors.get(nivel, "#64748b"),
            "nombre_corto": nombre[:18] + "..." if len(nombre) > 18 else nombre,
            "area": proyecto.get_tipo_proyecto_display() if hasattr(proyecto, "get_tipo_proyecto_display") else proyecto.get_estado_display(),
            "icono": iconos_panel[indice % len(iconos_panel)],
        })

    proyectos_visibles = proyectos_chart[:7]
    proyectos_extra = max(0, len(proyectos_chart) - len(proyectos_visibles))

    # Build JSON-safe data for Chart.js
    semanas_labels = [s["label"] for s in semanas]
    semanas_rangos = [s["rango"] for s in semanas]
    hoy_index = next((i for i, s in enumerate(semanas) if s["es_hoy"]), None)
    chart_datasets = []
    for item in proyectos_visibles:
        chart_datasets.append({
            "id": item["proyecto"].pk,
            "nombre": item["nombre_corto"],
            "nombre_completo": item["proyecto"].nombre,
            "area": item["area"],
            "nivel": item["nivel"],
            "color": item["color"],
            "serie": item["serie"],
            "salud": item["salud"],
            "avance": item["avance"],
            "tareas_pendientes": item["tareas_pendientes"],
            "tareas_total": item["tareas_total"],
            "dias_restantes": item["dias_restantes"],
            "fecha_fin": item["proyecto"].fecha_fin.strftime("%d/%m/%Y") if item["proyecto"].fecha_fin else "Sin fecha",
            "estado": item["proyecto"].get_estado_display(),
            "penalizaciones": item["penalizaciones"],
            "url": item["proyecto"].get_absolute_url(),
        })
    chart_data_json = json.dumps({
        "labels": semanas_labels,
        "rangos": semanas_rangos,
        "hoy_index": hoy_index,
        "datasets": chart_datasets,
    }, ensure_ascii=False)

    proyectos_prioritarios = sorted(
        proyectos_chart,
        key=lambda item: (
            item["salud"],
            item["proyecto"].fecha_fin is None,
            item["proyecto"].fecha_fin or hoy + timedelta(days=3650),
            item["proyecto"].nombre.lower(),
        ),
    )[:4]

    proyectos_riesgo = [
        proyecto for proyecto in proyectos
        if proyecto.nivel_alerta in {"riesgo", "advertencia"}
    ]
    proyectos_atrasados = [
        proyecto for proyecto in proyectos
        if proyecto.esta_atrasado
    ]
    resumen_estados = [
        {
            "value": value,
            "label": label,
            "total": proyectos_qs.filter(estado=value).count(),
        }
        for value, label in Proyecto.Estado.choices
    ]
    contexto = {
        "total_proyectos": proyectos_qs.count(),
        "promedio_avance": proyectos_qs.aggregate(promedio=Avg("porcentaje_avance"))["promedio"] or 0,
        "tareas_pendientes": Tarea.objects.filter(proyecto__sede=sede_usuario(request.user)).exclude(estado=Tarea.Estado.COMPLETADA).count(),
        "proyectos_recientes": proyectos_qs[:5],
        "proyectos_riesgo": proyectos_riesgo[:5],
        "proyectos_atrasados": proyectos_atrasados[:5],
        "ultimos_avances": Avance.objects.filter(proyecto__sede=sede_usuario(request.user)).select_related("proyecto", "responsable")[:5],
        "tareas_por_responsable": usuarios_de_sede(request.user).annotate(
            pendientes=Count(
                "tareas_asignadas",
                filter=~Q(tareas_asignadas__estado=Tarea.Estado.COMPLETADA),
                distinct=True,
            )
        ).filter(pendientes__gt=0).order_by("-pendientes", "nombre")[:5],
        "resumen_estados": resumen_estados,
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "total_inventario": inventario_de_sede(request.user).filter(activo=True).count(),
        "alertas_inventario": inventario_de_sede(request.user).filter(
            activo=True,
            tipo=ItemInventario.Tipo.FUNGIBLE,
            cantidad__isnull=False,
            cantidad__lte=F("stock_minimo"),
        ).count(),
        "grafico_proyectos": proyectos_chart,
        "proyectos_chart": proyectos_visibles,
        "proyectos_extra": proyectos_extra,
        "semanas_chart": semanas,
        "chart_data_json": chart_data_json,
        "proyectos_prioritarios": proyectos_prioritarios,
        "proyectos_ok": conteo_salud["ok"],
        "proyectos_advertencia": conteo_salud["advertencia"],
        "proyectos_rojo": conteo_salud["riesgo"],
    }
    return render(request, "proyectos/dashboard.html", contexto)


class ProyectoListView(LoginRequiredMixin, ListView):
    model = Proyecto
    template_name = "proyectos/proyecto_lista.html"
    context_object_name = "proyectos"
    paginate_by = 10

    def get_queryset(self):
        queryset = proyectos_de_sede(self.request.user).prefetch_related("responsables", "fases").annotate(
            total_tareas=Count("tareas", distinct=True),
            tareas_completadas=Count("tareas", filter=Q(tareas__estado=Tarea.Estado.COMPLETADA), distinct=True),
        )
        estado = self.request.GET.get("estado")
        responsable = self.request.GET.get("responsable")
        busqueda = self.request.GET.get("q")
        if estado:
            queryset = queryset.filter(estado=estado)
        if responsable:
            queryset = queryset.filter(responsables__id=responsable)
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda)
            )
        return queryset.order_by("-actualizado_en", "nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for proyecto in context["proyectos"]:
            sincronizar_trl_desde_resultados(proyecto)
            sincronizar_avance_simple_desde_objetivos(proyecto)
            proyecto.puede_editar = usuario_puede_editar_proyecto(self.request.user, proyecto)
        context["estados"] = Proyecto.Estado.choices
        context["responsables"] = usuarios_de_sede(self.request.user).order_by("nombre", "username")
        context["estado_actual"] = self.request.GET.get("estado", "")
        context["responsable_actual"] = self.request.GET.get("responsable", "")
        context["busqueda"] = self.request.GET.get("q", "")
        context["es_admin_laboratorio"] = usuario_es_admin_laboratorio(self.request.user)
        context["puede_eliminar_proyectos"] = usuario_puede_eliminar_proyecto(self.request.user)
        return context


class UsuarioListView(LoginRequiredMixin, ListView):
    model = Usuario
    template_name = "proyectos/usuario_lista.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        return usuarios_de_sede(self.request.user).annotate(
            total_proyectos=Count("proyectos_responsable", distinct=True),
            tareas_pendientes=Count(
                "tareas_asignadas",
                filter=~Q(tareas_asignadas__estado=Tarea.Estado.COMPLETADA),
                distinct=True,
            ),
        ).order_by("rol", "nombre", "username")



class UsuarioCreateView(LoginRequiredMixin, CreateView):
    model = Usuario
    form_class = UsuarioRegistroForm
    template_name = "proyectos/usuario_form.html"
    success_url = "/usuarios/"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Solo un usuario administrador puede crear usuarios.")
            return redirect("usuario_lista")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not form.instance.sede:
            form.instance.sede = sede_usuario(self.request.user)
        messages.success(self.request, "Usuario creado correctamente.")
        return super().form_valid(form)




class UsuarioUpdateView(LoginRequiredMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "proyectos/usuario_form.html"
    success_url = "/usuarios/"

    def dispatch(self, request, *args, **kwargs):
        if not usuario_es_admin_laboratorio(request.user):
            messages.error(request, "Solo un administrador puede editar usuarios.")
            return redirect("usuario_lista")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return usuarios_de_sede(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado correctamente.")
        return super().form_valid(form)


@login_required
def perfil_editar(request):
    form = PerfilUsuarioForm(instance=request.user)
    if request.method == "POST":
        form = PerfilUsuarioForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("perfil_editar")
    return render(request, "proyectos/perfil_form.html", {"form": form})


@login_required
def usuario_detalle(request, pk):
    usuario = get_object_or_404(usuarios_de_sede(request.user), pk=pk)
    proyectos = usuario.proyectos_responsable.filter(sede=sede_usuario(request.user))[:8]
    tareas = usuario.tareas_asignadas.filter(proyecto__sede=sede_usuario(request.user)).exclude(estado=Tarea.Estado.COMPLETADA)[:8]
    return render(
        request,
        "proyectos/usuario_detalle.html",
        {
            "usuario_obj": usuario,
            "proyectos_usuario": proyectos,
            "tareas_usuario": tareas,
        },
    )


@login_required
def chat_privado(request, usuario_id=None):
    usuarios = usuarios_de_sede(request.user).filter(is_active=True).exclude(pk=request.user.pk).order_by("nombre", "username")
    destinatario = None
    mensajes_chat = MensajePrivado.objects.none()
    form = MensajePrivadoForm()

    if usuario_id:
        destinatario = get_object_or_404(usuarios, pk=usuario_id)
        mensajes_chat = MensajePrivado.objects.filter(
            Q(remitente=request.user, destinatario=destinatario)
            | Q(remitente=destinatario, destinatario=request.user)
        ).select_related("remitente", "destinatario")

        request.user.mensajes_recibidos.filter(remitente=destinatario, leido=False).update(leido=True)

        if request.method == "POST":
            form = MensajePrivadoForm(request.POST, request.FILES)
            if form.is_valid():
                mensaje = form.save(commit=False)
                mensaje.remitente = request.user
                mensaje.destinatario = destinatario
                mensaje.save()
                return redirect("chat_privado", usuario_id=destinatario.pk)

    conversaciones = []
    for usuario in usuarios:
        ultimo = MensajePrivado.objects.filter(
            Q(remitente=request.user, destinatario=usuario)
            | Q(remitente=usuario, destinatario=request.user)
        ).order_by("-creado_en").first()
        no_leidos = request.user.mensajes_recibidos.filter(remitente=usuario, leido=False).count()
        conversaciones.append({
            "usuario": usuario,
            "ultimo": ultimo,
            "no_leidos": no_leidos,
            "presencia": estado_presencia(usuario),
        })

    conversaciones.sort(
        key=lambda item: item["ultimo"].creado_en if item["ultimo"] else timezone.make_aware(datetime.min),
        reverse=True,
    )

    return render(
        request,
        "proyectos/chat_privado.html",
        {
            "conversaciones": conversaciones,
            "destinatario": destinatario,
            "mensajes_chat": mensajes_chat,
            "form": form,
            "total_no_leidos": mensajes_no_leidos(request.user),
            "destinatario_presencia": estado_presencia(destinatario) if destinatario else None,
        },
    )


@login_required
def usuario_eliminar(request, pk):
    if not usuario_es_admin_laboratorio(request.user):
        messages.error(request, "Solo un administrador puede eliminar usuarios.")
        return redirect("usuario_lista")

    usuario = get_object_or_404(usuarios_de_sede(request.user), pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes eliminar el usuario con el que estás conectado.")
        return redirect("usuario_lista")

    if request.method == "POST":
        nombre = usuario.nombre or usuario.username
        try:
            usuario.delete()
            messages.success(request, f"Usuario '{nombre}' eliminado correctamente.")
        except ProtectedError:
            usuario.is_active = False
            usuario.is_staff = False
            usuario.is_superuser = False
            usuario.save(update_fields=["is_active", "is_staff", "is_superuser"])
            messages.warning(
                request,
                f"'{nombre}' tiene historial asociado. La cuenta fue desactivada en vez de eliminarse.",
            )
        return redirect("usuario_lista")

    return render(request, "proyectos/usuario_confirm_delete.html", {"usuario_obj": usuario})


PALABRAS_ACTIVIDAD = {
    "charla", "reunion", "reunión", "conversacion", "conversación",
    "presentacion", "presentación", "capacitacion", "capacitación",
    "evento", "coordinacion", "coordinación", "jornada", "taller",
    "seminario", "clase", "induccion", "inducción",
}

PALABRAS_TECNOLOGIA = {
    "sistema", "web", "app", "movil", "móvil", "software", "plataforma",
    "prototipo", "sensor", "hardware", "ia", "inteligencia artificial",
    "dispositivo", "tecnologia", "tecnología", "herramienta digital",
    "validar", "automatizacion", "automatización", "producto innovador",
}


def detectar_tipo_proyecto(proyecto):
    texto = f"{proyecto.nombre} {proyecto.descripcion}".lower()
    if any(palabra in texto for palabra in PALABRAS_TECNOLOGIA):
        return Proyecto.TipoProyecto.TECNOLOGICO
    if any(palabra in texto for palabra in PALABRAS_ACTIVIDAD):
        return Proyecto.TipoProyecto.ACTIVIDAD
    return Proyecto.TipoProyecto.GENERAL


def fases_por_tipo(tipo_proyecto):
    if tipo_proyecto == Proyecto.TipoProyecto.TECNOLOGICO:
        return [
            (numero, nombre, f"Evidenciar el cumplimiento del {nombre.lower()}.")
            for numero, nombre in TRL_DEFINICIONES
        ]
    if tipo_proyecto == Proyecto.TipoProyecto.ACTIVIDAD:
        objetivos = {
            1: "Definir objetivo, público, fecha tentativa y responsables de la actividad.",
            2: "Preparar presentación, pauta, recursos y materiales necesarios.",
            3: "Coordinar sala, participantes, difusión y confirmaciones.",
            4: "Realizar la actividad y dejar registro de asistencia o evidencia.",
            5: "Registrar resultados, comentarios, aprendizajes y mejoras detectadas.",
            6: "Cerrar la actividad con evidencias, conclusiones y próximos pasos.",
        }
        return [(numero, nombre, objetivos[numero]) for numero, nombre in ACTIVIDAD_FASES]
    objetivos = {
        1: "Levantar necesidad, alcance inicial y responsables.",
        2: "Ordenar actividades, fechas, tareas y recursos disponibles.",
        3: "Ejecutar las tareas principales y registrar avances.",
        4: "Revisar resultados, evidencias y cumplimiento del objetivo.",
        5: "Cerrar el proyecto con conclusiones y pendientes documentados.",
    }
    return [(numero, nombre, objetivos[numero]) for numero, nombre in GENERAL_FASES]


def crear_fases_para_proyecto(proyecto):
    tipo_proyecto = Proyecto.TipoProyecto.TECNOLOGICO if proyecto.usa_trl else Proyecto.TipoProyecto.GENERAL
    if proyecto.tipo_proyecto != tipo_proyecto:
        proyecto.tipo_proyecto = tipo_proyecto
        proyecto.save(update_fields=["tipo_proyecto"])
    for numero, nombre, objetivo in fases_por_tipo(tipo_proyecto):
        fase, _ = FaseProyecto.objects.get_or_create(
            proyecto=proyecto,
            trl=numero,
            defaults={"nombre": nombre, "objetivo": objetivo},
        )
        if fase.nombre != nombre or fase.objetivo != objetivo:
            fase.nombre = nombre
            fase.objetivo = objetivo
            fase.save(update_fields=["nombre", "objetivo"])




def enviar_correo_simple(asunto, destinatarios, mensaje):
    destinatarios = [correo for correo in destinatarios if correo]
    if not destinatarios:
        return False
    try:
        enviados = send_mail(
            asunto,
            mensaje,
            None,
            destinatarios,
            fail_silently=False,
        )
    except Exception:
        return False
    return enviados > 0


def notificar_responsables_proyecto(request, proyecto):
    url = request.build_absolute_uri(proyecto.get_absolute_url())
    destinatarios = [usuario.email for usuario in proyecto.responsables.all()]
    mensaje = (
        f"Hola,\n\n"
        f"Fuiste asignado como responsable del proyecto '{proyecto.nombre}'.\n\n"
        f"Estado: {proyecto.get_estado_display()}\n"
        f"Avance: {proyecto.porcentaje_avance}%\n"
        f"Revisar proyecto: {url}\n\n"
        f"FAB INACAP Puerto Montt"
    )
    return enviar_correo_simple(
        f"Nuevo proyecto asignado: {proyecto.nombre}",
        destinatarios,
        mensaje,
    )


def notificar_tarea_asignada(request, tarea):
    if not tarea.responsable or not tarea.responsable.email:
        return False
    url = request.build_absolute_uri(tarea.proyecto.get_absolute_url())
    mensaje = (
        f"Hola {tarea.responsable.nombre or tarea.responsable.username},\n\n"
        f"Se te asignó la tarea '{tarea.nombre}' en el proyecto '{tarea.proyecto.nombre}'.\n\n"
        f"Estado: {tarea.get_estado_display()}\n"
        f"Revisar proyecto: {url}\n\n"
        f"FAB INACAP Puerto Montt"
    )
    return enviar_correo_simple(
        f"Nueva tarea asignada: {tarea.nombre}",
        [tarea.responsable.email],
        mensaje,
    )


def notificar_observacion(request, observacion):
    url = request.build_absolute_uri(observacion.proyecto.get_absolute_url())
    destinatarios = [usuario.email for usuario in observacion.proyecto.responsables.all()]
    mensaje = (
        f"Hola,\n\n"
        f"{observacion.usuario} agregó una observación al proyecto '{observacion.proyecto.nombre}'.\n\n"
        f"Observación:\n{observacion.comentario}\n\n"
        f"Revisar proyecto: {url}\n\n"
        f"FAB INACAP Puerto Montt"
    )
    return enviar_correo_simple(
        f"Nueva observación en {observacion.proyecto.nombre}",
        destinatarios,
        mensaje,
    )


TRL_ETAPAS = [
    {
        "slug": "inicio",
        "nombre": "Inicio",
        "rango": range(1, 4),
        "resumen": "Ideas, necesidad, planificación y prueba de concepto inicial.",
        "evidencias": ["Problema definido", "Objetivo claro", "Plan de trabajo", "Concepto o prueba inicial"],
    },
    {
        "slug": "validacion",
        "nombre": "Validación",
        "rango": range(4, 6),
        "resumen": "Validación técnica en laboratorio y revisión en entorno relevante.",
        "evidencias": ["Ensayos de laboratorio", "Resultados medibles", "Ajustes técnicos", "Validación del funcionamiento"],
    },
    {
        "slug": "pruebas",
        "nombre": "Pruebas",
        "rango": range(6, 8),
        "resumen": "Prototipo demostrado y probado fuera del escenario controlado.",
        "evidencias": ["Prototipo operativo", "Pruebas con usuarios o entorno real", "Registro de fallas", "Mejoras aplicadas"],
    },
    {
        "slug": "finalizacion",
        "nombre": "Finalización",
        "rango": range(8, 10),
        "resumen": "Sistema completo, validado y probado con éxito en entorno real.",
        "evidencias": ["Solución completa", "Documentación final", "Validación real", "Cierre técnico"],
    },
]



def trl_estimado_por_porcentaje(porcentaje):
    porcentaje = porcentaje or 0
    if porcentaje <= 0:
        return 0
    if porcentaje <= 15:
        return 1
    if porcentaje <= 25:
        return 2
    if porcentaje <= 35:
        return 3
    if porcentaje <= 45:
        return 4
    if porcentaje <= 55:
        return 5
    if porcentaje <= 65:
        return 6
    if porcentaje <= 75:
        return 7
    if porcentaje <= 90:
        return 8
    return 9


def estructura_trl_proyecto(proyecto):
    objetivos = proyecto.objetivos.prefetch_related("resultados__indicadores").all()
    return objetivos


def calcular_avance_por_objetivos(proyecto):
    resultados = list(ResultadoEsperado.objects.filter(objetivo__proyecto=proyecto).prefetch_related("indicadores"))
    if not resultados:
        return 0
    cumplidos = sum(1 for resultado in resultados if resultado.esta_cumplido)
    return round((cumplidos * 100) / len(resultados))


def resumen_objetivo_de_fase(proyecto, trl):
    resultados = ResultadoEsperado.objects.filter(
        objetivo__proyecto=proyecto,
        trl_objetivo=trl,
    ).order_by("objetivo__orden", "orden")
    if not resultados.exists():
        return f"Completar la evidencia requerida para alcanzar TRL {trl}."
    resumenes = [resultado.descripcion.strip() for resultado in resultados[:3] if resultado.descripcion.strip()]
    if resultados.count() > 3:
        resumenes.append(f"+{resultados.count() - 3} resultados mas")
    return " | ".join(resumenes)


def sincronizar_trl_desde_resultados(proyecto):
    if not proyecto.usa_trl:
        return
    for resultado in ResultadoEsperado.objects.filter(objetivo__proyecto=proyecto).prefetch_related("indicadores"):
        nuevo_estado = resultado.estado_calculado
        cambios_resultado = []
        if resultado.estado != nuevo_estado:
            resultado.estado = nuevo_estado
            cambios_resultado.append("estado")
        if nuevo_estado == ResultadoEsperado.Estado.CUMPLIDO and not resultado.fecha_cumplimiento:
            resultado.fecha_cumplimiento = timezone.localdate()
            cambios_resultado.append("fecha_cumplimiento")
        if nuevo_estado != ResultadoEsperado.Estado.CUMPLIDO and resultado.fecha_cumplimiento:
            resultado.fecha_cumplimiento = None
            cambios_resultado.append("fecha_cumplimiento")
        if cambios_resultado:
            resultado.save(update_fields=cambios_resultado)
    nivel_actual = proyecto.calcular_trl_desde_resultados()
    for fase in proyecto.fases.filter(
        trl__gte=proyecto.trl_inicial_efectivo,
        trl__lte=proyecto.trl_objetivo_efectivo,
    ):
        resultados = list(
            ResultadoEsperado.objects.filter(
                objetivo__proyecto=proyecto,
                trl_objetivo=fase.trl,
            ).prefetch_related("indicadores")
        )
        objetivo = resumen_objetivo_de_fase(proyecto, fase.trl)
        if fase.trl <= nivel_actual:
            estado = FaseProyecto.Estado.COMPLETADA
        elif resultados and any(resultado.estado_calculado != ResultadoEsperado.Estado.PENDIENTE for resultado in resultados):
            estado = FaseProyecto.Estado.EN_PROCESO
        else:
            estado = FaseProyecto.Estado.PENDIENTE
        cambios = []
        if fase.estado != estado:
            fase.estado = estado
            cambios.append("estado")
        if fase.objetivo != objetivo:
            fase.objetivo = objetivo
            cambios.append("objetivo")
        if cambios:
            fase.save(update_fields=[*cambios, "fecha_actualizacion"])
    porcentaje = calcular_avance_madurez(proyecto)
    resultados_qs = ResultadoEsperado.objects.filter(objetivo__proyecto=proyecto)
    hay_movimiento = resultados_qs.exclude(estado=ResultadoEsperado.Estado.PENDIENTE).exists()
    objetivo_cumplido = (
        proyecto.resultados_trl.exists()
        and proyecto.nivel_actual >= proyecto.trl_objetivo_efectivo
        and porcentaje >= 100
    )
    if objetivo_cumplido:
        nuevo_estado = Proyecto.Estado.FINALIZADO
    elif proyecto.estado == Proyecto.Estado.EN_PAUSA:
        nuevo_estado = Proyecto.Estado.EN_PAUSA
    elif porcentaje > 0 or hay_movimiento or proyecto.estado == Proyecto.Estado.EN_PROCESO:
        nuevo_estado = Proyecto.Estado.EN_PROCESO
    else:
        nuevo_estado = Proyecto.Estado.PENDIENTE
    cambios_proyecto = []
    if proyecto.porcentaje_avance != porcentaje:
        proyecto.porcentaje_avance = porcentaje
        cambios_proyecto.append("porcentaje_avance")
    if proyecto.estado != nuevo_estado:
        proyecto.estado = nuevo_estado
        cambios_proyecto.append("estado")
    if cambios_proyecto:
        proyecto.save(update_fields=[*cambios_proyecto, "actualizado_en"])


def sincronizar_avance_simple_desde_objetivos(proyecto):
    if proyecto.usa_trl:
        return
    porcentaje = calcular_avance_por_objetivos(proyecto)
    nuevo_estado = proyecto.estado
    if porcentaje >= 100 and proyecto.resultados_trl.exists():
        nuevo_estado = Proyecto.Estado.FINALIZADO
    elif porcentaje > 0 and proyecto.estado in {Proyecto.Estado.PENDIENTE, Proyecto.Estado.FINALIZADO}:
        nuevo_estado = Proyecto.Estado.EN_PROCESO
    elif porcentaje == 0 and proyecto.estado == Proyecto.Estado.FINALIZADO:
        nuevo_estado = Proyecto.Estado.EN_PROCESO
    cambios = []
    if proyecto.porcentaje_avance != porcentaje:
        proyecto.porcentaje_avance = porcentaje
        cambios.append("porcentaje_avance")
    if proyecto.estado != nuevo_estado:
        proyecto.estado = nuevo_estado
        cambios.append("estado")
    if cambios:
        proyecto.save(update_fields=[*cambios, "actualizado_en"])


def calcular_avance_madurez(proyecto):
    if proyecto.usa_trl:
        total = proyecto.trl_objetivo_efectivo - proyecto.trl_inicial_efectivo
        logrado = proyecto.nivel_actual - proyecto.trl_inicial_efectivo
        return round((logrado * 100) / total) if total > 0 else 100
    if proyecto.resultados_trl.exists():
        return calcular_avance_por_objetivos(proyecto)
    total = proyecto.total_fases_relevantes
    completadas = proyecto.fases_completadas_relevantes
    return round((completadas * 100) / total) if total else 0


def construir_detalle_etapas(proyecto):
    resultado = []
    for etapa in construir_tablero_trl(proyecto):
        if etapa["completa"]:
            estado = "completada"
            texto_estado = "Completada"
            mensaje = "Etapa completada en la mesa de trabajo."
        elif etapa["actual"]:
            estado = "actual"
            texto_estado = "Etapa actual"
            mensaje = "El equipo se encuentra trabajando principalmente en esta etapa."
        elif etapa["bloqueada"]:
            estado = "bloqueada"
            texto_estado = "Bloqueada"
            mensaje = "Se desbloquea al completar la etapa anterior."
        else:
            estado = "pendiente"
            texto_estado = "Pendiente"
            mensaje = "Pendiente de desarrollo."

        fases_etapa = [paso["fase"] for paso in etapa["pasos"]]
        filtro_etapa = Q(fase__in=fases_etapa)
        if etapa["slug"] == "inicio":
            filtro_etapa |= Q(fase__isnull=True)

        evidencias = proyecto.evidencias.filter(filtro_etapa) if fases_etapa else proyecto.evidencias.none()
        avances = proyecto.avances.filter(filtro_etapa) if fases_etapa else proyecto.avances.none()
        tareas = proyecto.tareas.filter(filtro_etapa) if fases_etapa else proyecto.tareas.none()
        observaciones = proyecto.observaciones.filter(filtro_etapa) if fases_etapa else proyecto.observaciones.none()

        resultado.append({
            "slug": etapa["slug"],
            "nombre": etapa["nombre"],
            "inicio": etapa["inicio"],
            "fin": etapa["fin"],
            "descripcion": etapa["resumen"],
            "estado": estado,
            "texto_estado": texto_estado,
            "mensaje": mensaje,
            "completadas": etapa["completadas"],
            "total": etapa["total"],
            "pasos": etapa["pasos"],
            "avances": avances,
            "tareas": tareas,
            "tareas_completadas": tareas.filter(estado=Tarea.Estado.COMPLETADA),
            "tareas_pendientes": tareas.exclude(estado=Tarea.Estado.COMPLETADA),
            "observaciones": observaciones,
            "evidencias": preparar_evidencias_detalle(evidencias),
        })
    return resultado


def preparar_evidencias_detalle(origen):
    evidencias = []
    extensiones_imagen = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    if hasattr(origen, "evidencias"):
        origen = origen.evidencias.all()
    for evidencia in origen:
        nombre_archivo = evidencia.archivo.name.lower()
        evidencias.append({
            "obj": evidencia,
            "es_imagen": any(nombre_archivo.endswith(extension) for extension in extensiones_imagen),
        })
    return evidencias


def fase_desbloqueada(fase):
    if not fase.proyecto.usa_trl:
        return True
    return not fase.proyecto.fases.filter(
        trl__gte=fase.proyecto.trl_inicial_efectivo,
        trl__lt=fase.trl,
    ).exclude(
        estado=FaseProyecto.Estado.COMPLETADA
    ).exists()


def recalcular_avance_por_tareas(proyecto):
    if proyecto.usa_trl:
        sincronizar_trl_desde_resultados(proyecto)
        return
    if not proyecto.usa_trl and proyecto.resultados_trl.exists():
        sincronizar_avance_simple_desde_objetivos(proyecto)
        return
    total = proyecto.tareas.count()
    completadas = proyecto.tareas.filter(estado=Tarea.Estado.COMPLETADA).count()
    porcentaje = round((completadas * 100) / total) if total else 0
    proyecto.porcentaje_avance = porcentaje
    if total and completadas == total:
        proyecto.estado = Proyecto.Estado.FINALIZADO
    elif proyecto.estado in {Proyecto.Estado.PENDIENTE, Proyecto.Estado.FINALIZADO}:
        proyecto.estado = Proyecto.Estado.EN_PROCESO
    proyecto.save(update_fields=["porcentaje_avance", "estado", "actualizado_en"])


def construir_tablero_trl(proyecto):
    if not proyecto.usa_trl:
        fases_etapas = list(proyecto.fases_relevantes)
        siguiente = proyecto.siguiente_fase
        tablero = []
        fase_anterior_completa = True

        for fase in fases_etapas:
            completa = fase.estado == FaseProyecto.Estado.COMPLETADA
            bloqueada = not fase_anterior_completa
            actual = bool(siguiente and fase.pk == siguiente.pk and not bloqueada)
            if completa:
                estado_visual = "completada"
            elif bloqueada:
                estado_visual = "bloqueada"
            elif actual:
                estado_visual = "actual"
            else:
                estado_visual = "disponible"

            tablero.append({
                "slug": slugify(f"fase-{fase.trl}-{fase.nombre}"),
                "nombre": fase.nombre,
                "resumen": fase.objetivo,
                "evidencias": [fase.objetivo],
                "inicio": fase.trl,
                "fin": fase.trl,
                "completadas": 1 if completa else 0,
                "total": 1,
                "bloqueada": bloqueada,
                "completa": completa,
                "actual": actual,
                "estado_visual": estado_visual,
                "pasos": [{
                    "fase": fase,
                    "desbloqueada": not bloqueada,
                    "actual": actual,
                }],
            })
            fase_anterior_completa = fase_anterior_completa and completa

        return tablero

    sincronizar_trl_desde_resultados(proyecto)
    fases = {
        fase.trl: fase
        for fase in proyecto.fases.filter(
            trl__gte=proyecto.trl_inicial_efectivo,
            trl__lte=proyecto.trl_objetivo_efectivo,
        )
    }
    siguiente = proyecto.siguiente_fase
    tablero = []
    etapa_anterior_completa = True

    for etapa in TRL_ETAPAS:
        fases_etapa = [fases[numero] for numero in etapa["rango"] if numero in fases]
        if not fases_etapa:
            continue
        total = len(fases_etapa)
        completadas = sum(1 for fase in fases_etapa if fase.estado == FaseProyecto.Estado.COMPLETADA)
        etapa_completa = total > 0 and completadas == total
        bloqueada = not etapa_anterior_completa
        actual = bool(siguiente and any(fase.pk == siguiente.pk for fase in fases_etapa))
        if etapa_completa:
            estado_visual = "completada"
        elif bloqueada:
            estado_visual = "bloqueada"
        elif actual:
            estado_visual = "actual"
        else:
            estado_visual = "disponible"

        pasos = []
        for fase in fases_etapa:
            desbloqueada = fase_desbloqueada(fase) and not bloqueada
            pasos.append({
                "fase": fase,
                "desbloqueada": desbloqueada,
                "actual": bool(siguiente and fase.pk == siguiente.pk),
            })

        tablero.append({
            "slug": etapa["slug"],
            "nombre": etapa["nombre"],
            "resumen": etapa["resumen"],
            "evidencias": etapa["evidencias"],
            "inicio": fases_etapa[0].trl,
            "fin": fases_etapa[-1].trl,
            "completadas": completadas,
            "total": total,
            "bloqueada": bloqueada,
            "completa": etapa_completa,
            "actual": actual,
            "estado_visual": estado_visual,
            "pasos": pasos,
        })
        etapa_anterior_completa = etapa_anterior_completa and etapa_completa

    return tablero

class ProyectoCreateView(LoginRequiredMixin, CreateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = "proyectos/proyecto_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["sede"] = sede_usuario(self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["es_admin_laboratorio"] = usuario_es_admin_laboratorio(self.request.user)
        return context

    def form_valid(self, form):
        form.instance.sede = sede_usuario(self.request.user)
        form.instance.estado = Proyecto.Estado.EN_PROCESO
        response = super().form_valid(form)
        crear_fases_para_proyecto(self.object)
        sincronizar_trl_desde_resultados(self.object)
        sincronizar_avance_simple_desde_objetivos(self.object)
        correo_enviado = notificar_responsables_proyecto(self.request, self.object)
        if correo_enviado:
            messages.success(self.request, "Proyecto creado correctamente.")
        else:
            messages.success(self.request, "Proyecto creado correctamente.")
        return response

class ProyectoUpdateView(LoginRequiredMixin, UpdateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = "proyectos/proyecto_form.html"

    def get_queryset(self):
        return proyectos_de_sede(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["sede"] = self.object.sede
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["es_admin_laboratorio"] = usuario_es_admin_laboratorio(self.request.user)
        return context

    def dispatch(self, request, *args, **kwargs):
        proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=kwargs["pk"])
        if not exigir_permiso_edicion_proyecto(request, proyecto):
            return redirect("proyecto_detalle", pk=proyecto.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        crear_fases_para_proyecto(self.object)
        sincronizar_trl_desde_resultados(self.object)
        sincronizar_avance_simple_desde_objetivos(self.object)
        messages.success(self.request, "Proyecto actualizado correctamente.")
        return response


@login_required
def proyecto_detalle(request, pk):
    proyecto = get_object_or_404(
        proyectos_de_sede(request.user).prefetch_related(
            "responsables",
            "avances__responsable",
            "tareas__responsable",
            "observaciones__usuario",
            "evidencias__usuario",
        ),
        pk=pk,
    )
    sincronizar_trl_desde_resultados(proyecto)
    sincronizar_avance_simple_desde_objetivos(proyecto)
    contexto = {
        "proyecto": proyecto,
        "tareas_pendientes": proyecto.tareas.exclude(estado=Tarea.Estado.COMPLETADA),
        "tareas_completadas": proyecto.tareas.filter(estado=Tarea.Estado.COMPLETADA),
        "timeline_items": construir_linea_temporal(proyecto),
        "tablero_trl": construir_tablero_trl(proyecto),
        "trl_estimado": proyecto.nivel_actual,
        "trl_estimado_texto": proyecto.nivel_actual_texto,
        "avance_madurez": calcular_avance_madurez(proyecto),
        "detalle_etapas": construir_detalle_etapas(proyecto),
        "evidencias_detalle": preparar_evidencias_detalle(proyecto),
        "objetivos_trl": estructura_trl_proyecto(proyecto),
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "puede_eliminar_proyecto": usuario_puede_eliminar_proyecto(request.user),
        "puede_editar_proyecto": usuario_puede_editar_proyecto(request.user, proyecto),
    }
    return render(request, "proyectos/proyecto_detalle.html", contexto)





@login_required
def proyecto_trabajo(request, pk):
    proyecto = get_object_or_404(
        proyectos_de_sede(request.user).prefetch_related(
            "responsables",
            "avances__responsable",
            "tareas__responsable",
            "observaciones__usuario",
            "evidencias__usuario",
            "fases",
        ),
        pk=pk,
    )
    sincronizar_trl_desde_resultados(proyecto)
    sincronizar_avance_simple_desde_objetivos(proyecto)
    contexto = {
        "proyecto": proyecto,
        "tareas_pendientes": proyecto.tareas.exclude(estado=Tarea.Estado.COMPLETADA),
        "tareas_completadas": proyecto.tareas.filter(estado=Tarea.Estado.COMPLETADA),
        "tablero_trl": construir_tablero_trl(proyecto),
        "avance_madurez": calcular_avance_madurez(proyecto),
        "usos_inventario": proyecto.usos_inventario.select_related("item", "usuario")[:6],
        "alertas_inventario": inventario_de_sede(request.user).filter(activo=True, tipo=ItemInventario.Tipo.FUNGIBLE, cantidad__isnull=False, cantidad__lte=F("stock_minimo"))[:5],
        "objetivos_trl": estructura_trl_proyecto(proyecto),
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "puede_editar_proyecto": usuario_puede_editar_proyecto(request.user, proyecto),
    }
    return render(request, "proyectos/proyecto_trabajo.html", contexto)


@login_required
def etapa_trabajo(request, pk, slug):
    proyecto = get_object_or_404(
        proyectos_de_sede(request.user).prefetch_related(
            "responsables",
            "avances__responsable",
            "tareas__responsable",
            "observaciones__usuario",
            "evidencias__usuario",
            "fases",
        ),
        pk=pk,
    )
    sincronizar_trl_desde_resultados(proyecto)
    sincronizar_avance_simple_desde_objetivos(proyecto)
    etapa = next((item for item in construir_tablero_trl(proyecto) if item["slug"] == slug), None)
    if not etapa:
        messages.error(request, "La etapa solicitada no existe en este proyecto.")
        return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    if etapa["bloqueada"]:
        messages.error(request, "Completa primero la etapa anterior para trabajar este bloque.")
        return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    fases_etapa = [paso["fase"] for paso in etapa["pasos"]]
    fase_activa = next((paso["fase"] for paso in etapa["pasos"] if paso["desbloqueada"] and not paso["fase"].completada), None)
    if not fase_activa and fases_etapa:
        fase_activa = fases_etapa[-1]
    filtro_etapa = Q(fase__in=fases_etapa)
    if etapa["slug"] == "inicio":
        filtro_etapa |= Q(fase__isnull=True)
    tareas_etapa = proyecto.tareas.filter(filtro_etapa) if fases_etapa else proyecto.tareas.none()
    avances_etapa = proyecto.avances.filter(filtro_etapa) if fases_etapa else proyecto.avances.none()
    evidencias_etapa = proyecto.evidencias.filter(filtro_etapa) if fases_etapa else proyecto.evidencias.none()
    observaciones_etapa = proyecto.observaciones.filter(filtro_etapa) if fases_etapa else proyecto.observaciones.none()
    contexto = {
        "proyecto": proyecto,
        "etapa": etapa,
        "fase_activa": fase_activa,
        "tareas_pendientes": tareas_etapa.exclude(estado=Tarea.Estado.COMPLETADA),
        "tareas_completadas": tareas_etapa.filter(estado=Tarea.Estado.COMPLETADA),
        "avances_etapa": avances_etapa,
        "observaciones_etapa": observaciones_etapa,
        "evidencias_detalle": preparar_evidencias_detalle(type("ProyectoEvidencias", (), {"evidencias": evidencias_etapa})()),
        "usos_etapa": proyecto.usos_inventario.filter(filtro_etapa).select_related("item", "usuario") if fases_etapa else proyecto.usos_inventario.none(),
        "next_url": request.path,
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "puede_editar_proyecto": usuario_puede_editar_proyecto(request.user, proyecto),
    }
    return render(request, "proyectos/etapa_trabajo.html", contexto)
def construir_linea_temporal(proyecto):
    items = [
        {
            "fecha": proyecto.fecha_inicio,
            "tipo": "Inicio",
            "titulo": "Inicio del proyecto",
            "descripcion": proyecto.nombre,
        }
    ]

    for avance in proyecto.avances.all():
        items.append({
            "fecha": avance.fecha,
            "tipo": "Avance",
            "titulo": avance.responsable,
            "descripcion": avance.descripcion,
        })

    for evidencia in proyecto.evidencias.all():
        items.append({
            "fecha": evidencia.fecha_subida.date(),
            "tipo": "Evidencia",
            "titulo": evidencia.nombre,
            "descripcion": evidencia.usuario,
        })

    for tarea in proyecto.tareas.all():
        items.append({
            "fecha": tarea.actualizada_en.date(),
            "tipo": "Tarea",
            "titulo": tarea.nombre,
            "descripcion": tarea.get_estado_display(),
        })

    for observacion in proyecto.observaciones.all():
        items.append({
            "fecha": observacion.fecha.date(),
            "tipo": "Observación",
            "titulo": observacion.usuario,
            "descripcion": observacion.comentario,
        })

    if proyecto.fecha_fin:
        items.append({
            "fecha": proyecto.fecha_fin,
            "tipo": "Cierre",
            "titulo": "Fecha de término",
            "descripcion": proyecto.get_estado_display(),
        })

    return sorted(items, key=lambda item: item["fecha"])

@login_required
def fase_detalle(request, pk):
    fase = get_object_or_404(FaseProyecto.objects.select_related("proyecto").filter(proyecto__sede=sede_usuario(request.user)), pk=pk)
    sincronizar_trl_desde_resultados(fase.proyecto)
    sincronizar_avance_simple_desde_objetivos(fase.proyecto)
    if not exigir_permiso_edicion_proyecto(request, fase.proyecto):
        return redirect("proyecto_trabajo", pk=fase.proyecto_id)
    if not fase_desbloqueada(fase):
        messages.error(request, "Completa primero la fase anterior para desbloquear este paso.")
        return redirect("proyecto_trabajo", pk=fase.proyecto_id)
    form = FaseProyectoForm(instance=fase)
    if request.method == "POST":
        form = FaseProyectoForm(request.POST, instance=fase)
        if form.is_valid():
            form.save()
            sincronizar_trl_desde_resultados(fase.proyecto)
            messages.success(request, "Fase actualizada correctamente.")
            return redirect(url_retorno_segura(request, fase.proyecto.get_absolute_url()))
    return render(
        request,
        "proyectos/fase_detalle.html",
        {
            "fase": fase,
            "proyecto": fase.proyecto,
            "form": form,
        },
    )



@login_required
def proyecto_eliminar(request, pk):
    if not usuario_puede_eliminar_proyecto(request.user):
        messages.error(request, "Solo la cuenta FAB autorizada puede eliminar proyectos.")
        return redirect("proyecto_detalle", pk=pk)

    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if request.method == "POST":
        nombre = proyecto.nombre
        for evidencia in proyecto.evidencias.all():
            evidencia.archivo.delete(save=False)
        proyecto.delete()
        messages.success(request, f"Proyecto '{nombre}' eliminado correctamente.")
        return redirect("proyecto_lista")

    return render(
        request,
        "proyectos/proyecto_confirm_delete.html",
        {"proyecto": proyecto},
    )

@login_required
def inventario_lista(request):
    items = inventario_de_sede(request.user).filter(activo=True)
    busqueda = request.GET.get("q", "")
    area = request.GET.get("area", "")
    tipo = request.GET.get("tipo", "")
    alerta = request.GET.get("alerta", "")

    if busqueda:
        items = items.filter(
            Q(nombre__icontains=busqueda)
            | Q(codigo_barra__icontains=busqueda)
            | Q(categoria__icontains=busqueda)
            | Q(estado__icontains=busqueda)
            | Q(ubicacion__icontains=busqueda)
            | Q(observacion__icontains=busqueda)
        )
    if area:
        items = items.filter(area=area)
    if tipo:
        items = items.filter(tipo=tipo)
    if alerta:
        items = items.filter(
            tipo=ItemInventario.Tipo.FUNGIBLE,
            cantidad__isnull=False,
            cantidad__lte=F("stock_minimo"),
        )

    alertas = inventario_de_sede(request.user).filter(
        activo=True,
        tipo=ItemInventario.Tipo.FUNGIBLE,
        cantidad__isnull=False,
        cantidad__lte=F("stock_minimo"),
    )
    contexto = {
        "items": items.order_by("area", "categoria", "nombre"),
        "areas": ItemInventario.Area.choices,
        "tipos": ItemInventario.Tipo.choices,
        "busqueda": busqueda,
        "area_actual": area,
        "tipo_actual": tipo,
        "alerta_actual": alerta,
        "total_items": inventario_de_sede(request.user).filter(activo=True).count(),
        "total_alertas": alertas.count(),
        "usos_recientes": UsoInventario.objects.filter(proyecto__sede=sede_usuario(request.user)).select_related("proyecto", "item", "usuario")[:8],
        "es_admin_laboratorio": usuario_es_admin_laboratorio(request.user),
        "puede_gestionar_inventario": usuario_puede_gestionar_inventario(request.user),
    }
    return render(request, "proyectos/inventario_lista.html", contexto)


@login_required
def inventario_crear(request):
    initial = {}
    if request.GET.get("codigo_barra"):
        initial["codigo_barra"] = request.GET["codigo_barra"]
    if request.GET.get("cantidad"):
        initial["cantidad"] = request.GET["cantidad"]
    form = ItemInventarioForm(initial=initial, instance=ItemInventario(sede=sede_usuario(request.user)))
    if request.method == "POST":
        form = ItemInventarioForm(request.POST, instance=ItemInventario(sede=sede_usuario(request.user)))
        if form.is_valid():
            item = form.save(commit=False)
            item.sede = sede_usuario(request.user)
            item.save()
            messages.success(request, "Item agregado al inventario.")
            return redirect("inventario_lista")
    return render(
        request,
        "proyectos/inventario_form.html",
        {
            "form": form,
            "titulo": "Agregar item al inventario",
            "descripcion": "Registra materiales, equipos o insumos disponibles en el laboratorio.",
            "boton": "Guardar item",
            "volver_url": "inventario_lista",
            "captura_codigo_barra": True,
        },
    )


@login_required
def inventario_lector(request):
    form = LectorCodigoBarraForm()
    item_encontrado = None
    if request.method == "POST":
        form = LectorCodigoBarraForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data["codigo_barra"]
            cantidad = form.cleaned_data["cantidad"]
            observacion = form.cleaned_data.get("observacion")
            with transaction.atomic():
                item_encontrado = (
                    inventario_de_sede(request.user)
                    .select_for_update()
                    .filter(activo=True, codigo_barra=codigo)
                    .first()
                )
                if item_encontrado:
                    item_encontrado.cantidad = (item_encontrado.cantidad or 0) + cantidad
                    if observacion:
                        item_encontrado.observacion = (
                            (item_encontrado.observacion + "\n" if item_encontrado.observacion else "")
                            + observacion
                        )
                    item_encontrado.save(update_fields=["cantidad", "observacion", "actualizado_en"])
                    messages.success(request, f"Stock actualizado: {item_encontrado.nombre}.")
                    return redirect("inventario_lector")
            messages.warning(request, "No existe un ítem activo con ese código. Completa el alta para dejarlo registrado.")
            parametros = urlencode({"codigo_barra": codigo, "cantidad": cantidad})
            return redirect(f"{reverse('inventario_crear')}?{parametros}")
    return render(
        request,
        "proyectos/inventario_form.html",
        {
            "form": form,
            "titulo": "Agregar con lector de barra",
            "descripcion": "Escanea el código del ítem y suma la cantidad ingresada al stock existente.",
            "boton": "Agregar al stock",
            "volver_url": "inventario_lista",
            "modo_lector": True,
            "item_encontrado": item_encontrado,
        },
    )


@login_required
def inventario_agregar_stock(request, pk):
    item = get_object_or_404(inventario_de_sede(request.user), pk=pk, activo=True)
    form = AjusteStockForm()
    if request.method == "POST":
        form = AjusteStockForm(request.POST)
        if form.is_valid():
            cantidad = form.cleaned_data["cantidad"]
            item.cantidad = (item.cantidad or 0) + cantidad
            if form.cleaned_data.get("observacion"):
                item.observacion = (item.observacion + "\n" if item.observacion else "") + form.cleaned_data["observacion"]
            item.save(update_fields=["cantidad", "observacion", "actualizado_en"])
            messages.success(request, "Stock actualizado correctamente.")
            return redirect("inventario_lista")
    return render(
        request,
        "proyectos/inventario_form.html",
        {
            "form": form,
            "titulo": f"Agregar stock: {item.nombre}",
            "descripcion": f"Stock actual: {item.cantidad_texto}.",
            "boton": "Actualizar stock",
            "volver_url": "inventario_lista",
        },
    )


@login_required
def registrar_uso_inventario(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    form = UsoInventarioForm(sede=proyecto.sede)
    if request.method == "POST":
        form = UsoInventarioForm(request.POST, sede=proyecto.sede)
        if form.is_valid():
            with transaction.atomic():
                uso = form.save(commit=False)
                uso.proyecto = proyecto
                uso.fase = fase_desde_request(request, proyecto)
                uso.usuario = request.user
                item = inventario_de_sede(request.user).select_for_update().get(pk=uso.item_id)
                if item.descuenta_stock and item.cantidad is not None:
                    if uso.cantidad > item.cantidad:
                        form.add_error("cantidad", f"Stock insuficiente. Disponible: {item.cantidad_texto}.")
                    else:
                        item.cantidad -= uso.cantidad
                        item.save(update_fields=["cantidad", "actualizado_en"])
                        uso.save()
                        messages.success(request, "Uso registrado y stock descontado.")
                        return redirect(url_retorno_segura(request, f"/proyectos/{proyecto.pk}/trabajo/"))
                else:
                    uso.save()
                    messages.success(request, "Uso registrado correctamente.")
                    return redirect(url_retorno_segura(request, f"/proyectos/{proyecto.pk}/trabajo/"))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Registrar uso de inventario",
            "descripcion": "Indica qué material, equipo o insumo usó este proyecto.",
            "boton": "Registrar uso",
        },
    )

@login_required
def actualizar_estado(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, proyecto):
        return redirect("proyecto_trabajo", pk=proyecto.pk)
    form = EstadoProyectoForm(instance=proyecto)
    if request.method == "POST":
        form = EstadoProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado del proyecto actualizado.")
            return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Actualizar estado",
            "descripcion": "Modifica el estado del proyecto.",
            "boton": "Guardar estado",
            "confirmacion": "¿Actualizar el estado y avance del proyecto?",
        },
    )


@login_required
def crear_avance(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, proyecto):
        return redirect("proyecto_trabajo", pk=proyecto.pk)
    form = AvanceForm(sede=proyecto.sede)
    if request.method == "POST":
        form = AvanceForm(request.POST, sede=proyecto.sede)
        if form.is_valid():
            avance = form.save(commit=False)
            avance.proyecto = proyecto
            avance.fase = fase_desde_request(request, proyecto)
            avance.save()
            messages.success(request, "Avance registrado correctamente.")
            return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Registrar avance",
            "descripcion": "Deja evidencia formal del progreso realizado.",
            "boton": "Guardar avance",
        },
    )


@login_required
def crear_tarea(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, proyecto):
        return redirect("proyecto_trabajo", pk=proyecto.pk)
    form = TareaForm(sede=proyecto.sede)
    if request.method == "POST":
        form = TareaForm(request.POST, sede=proyecto.sede)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.fase = fase_desde_request(request, proyecto)
            tarea.save()
            recalcular_avance_por_tareas(proyecto)
            correo_enviado = notificar_tarea_asignada(request, tarea)
            if correo_enviado:
                messages.success(request, "Tarea creada correctamente. Responsable notificado por correo.")
            else:
                messages.success(request, "Tarea creada correctamente.")
            return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Crear tarea",
            "descripcion": "Agrega una actividad concreta para organizar el trabajo del proyecto.",
            "boton": "Guardar tarea",
        },
    )


@login_required
def subir_evidencia(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, proyecto):
        return redirect("proyecto_trabajo", pk=proyecto.pk)
    form = EvidenciaForm()
    if request.method == "POST":
        form = EvidenciaForm(request.POST, request.FILES)
        if form.is_valid():
            evidencia = form.save(commit=False)
            evidencia.proyecto = proyecto
            evidencia.fase = fase_desde_request(request, proyecto)
            evidencia.usuario = request.user
            evidencia.save()
            messages.success(request, "Evidencia subida correctamente.")
            return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Subir evidencia",
            "descripcion": "Adjunta un archivo, presentación, documento o respaldo del proyecto.",
            "boton": "Subir evidencia",
            "multipart": True,
        },
    )


@login_required
def completar_tarea(request, pk):
    tarea = get_object_or_404(Tarea.objects.filter(proyecto__sede=sede_usuario(request.user)), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, tarea.proyecto):
        return redirect("proyecto_trabajo", pk=tarea.proyecto_id)
    if request.method == "POST":
        tarea.estado = Tarea.Estado.COMPLETADA
        tarea.save(update_fields=["estado", "actualizada_en"])
        recalcular_avance_por_tareas(tarea.proyecto)
        messages.success(request, "Tarea marcada como completada.")
    return redirect(url_retorno_segura(request, f"/proyectos/{tarea.proyecto_id}/trabajo/"))


@login_required
def crear_observacion(request, pk):
    proyecto = get_object_or_404(proyectos_de_sede(request.user), pk=pk)
    if not exigir_permiso_edicion_proyecto(request, proyecto):
        return redirect("proyecto_trabajo", pk=proyecto.pk)
    form = ObservacionForm()
    if request.method == "POST":
        form = ObservacionForm(request.POST)
        if form.is_valid():
            observacion = form.save(commit=False)
            observacion.proyecto = proyecto
            observacion.fase = fase_desde_request(request, proyecto)
            observacion.usuario = request.user
            observacion.save()
            correo_enviado = notificar_observacion(request, observacion)
            if correo_enviado:
                messages.success(request, "Observación agregada correctamente. Responsables notificados por correo.")
            else:
                messages.success(request, "Observación agregada correctamente.")
            return redirect(url_retorno_segura(request, proyecto.get_absolute_url().replace(f"/proyectos/{proyecto.pk}/", f"/proyectos/{proyecto.pk}/trabajo/")))
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Agregar observación",
            "descripcion": "Registra una recomendación, comentario o seguimiento del proyecto.",
            "boton": "Guardar observación",
        },
    )


