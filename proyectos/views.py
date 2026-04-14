from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (
    AvanceForm,
    EstadoProyectoForm,
    EvidenciaForm,
    FaseProyectoForm,
    ObservacionForm,
    ProyectoForm,
    TareaForm,
    UsuarioRegistroForm,
)
from .models import ACTIVIDAD_FASES, GENERAL_FASES, TRL_DEFINICIONES, Avance, FaseProyecto, Proyecto, Tarea, Usuario


@login_required
def dashboard(request):
    proyectos = Proyecto.objects.prefetch_related("responsables", "tareas")
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
            "total": proyectos.filter(estado=value).count(),
        }
        for value, label in Proyecto.Estado.choices
    ]
    contexto = {
        "total_proyectos": proyectos.count(),
        "promedio_avance": proyectos.aggregate(promedio=Avg("porcentaje_avance"))["promedio"] or 0,
        "tareas_pendientes": Tarea.objects.exclude(estado=Tarea.Estado.COMPLETADA).count(),
        "proyectos_recientes": proyectos[:5],
        "proyectos_riesgo": proyectos_riesgo[:5],
        "proyectos_atrasados": proyectos_atrasados[:5],
        "ultimos_avances": Avance.objects.select_related("proyecto", "responsable")[:5],
        "tareas_por_responsable": Usuario.objects.annotate(
            pendientes=Count(
                "tareas_asignadas",
                filter=~Q(tareas_asignadas__estado=Tarea.Estado.COMPLETADA),
                distinct=True,
            )
        ).filter(pendientes__gt=0).order_by("-pendientes", "nombre")[:5],
        "resumen_estados": resumen_estados,
    }
    return render(request, "proyectos/dashboard.html", contexto)


class ProyectoListView(LoginRequiredMixin, ListView):
    model = Proyecto
    template_name = "proyectos/proyecto_lista.html"
    context_object_name = "proyectos"
    paginate_by = 10

    def get_queryset(self):
        queryset = Proyecto.objects.prefetch_related("responsables").annotate(
            total_tareas=Count("tareas"),
            tareas_completadas=Count("tareas", filter=Q(tareas__estado=Tarea.Estado.COMPLETADA)),
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
        context["estados"] = Proyecto.Estado.choices
        context["responsables"] = Usuario.objects.order_by("nombre", "username")
        context["estado_actual"] = self.request.GET.get("estado", "")
        context["responsable_actual"] = self.request.GET.get("responsable", "")
        context["busqueda"] = self.request.GET.get("q", "")
        return context


class UsuarioListView(LoginRequiredMixin, ListView):
    model = Usuario
    template_name = "proyectos/usuario_lista.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        return Usuario.objects.annotate(
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
        messages.success(self.request, "Usuario creado correctamente.")
        return super().form_valid(form)




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
    tipo_proyecto = detectar_tipo_proyecto(proyecto)
    if proyecto.tipo_proyecto != tipo_proyecto:
        proyecto.tipo_proyecto = tipo_proyecto
        proyecto.save(update_fields=["tipo_proyecto"])
    for numero, nombre, objetivo in fases_por_tipo(tipo_proyecto):
        FaseProyecto.objects.get_or_create(
            proyecto=proyecto,
            trl=numero,
            defaults={"nombre": nombre, "objetivo": objetivo},
        )


class ProyectoCreateView(LoginRequiredMixin, CreateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = "proyectos/proyecto_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        crear_fases_para_proyecto(self.object)
        messages.success(self.request, "Proyecto creado correctamente.")
        return response

class ProyectoUpdateView(LoginRequiredMixin, UpdateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = "proyectos/proyecto_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Proyecto actualizado correctamente.")
        return super().form_valid(form)


@login_required
def proyecto_detalle(request, pk):
    proyecto = get_object_or_404(
        Proyecto.objects.prefetch_related(
            "responsables",
            "avances__responsable",
            "tareas__responsable",
            "observaciones__usuario",
            "evidencias__usuario",
        ),
        pk=pk,
    )
    contexto = {
        "proyecto": proyecto,
        "tareas_pendientes": proyecto.tareas.exclude(estado=Tarea.Estado.COMPLETADA),
        "tareas_completadas": proyecto.tareas.filter(estado=Tarea.Estado.COMPLETADA),
        "timeline_items": construir_linea_temporal(proyecto),
    }
    return render(request, "proyectos/proyecto_detalle.html", contexto)




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
    fase = get_object_or_404(FaseProyecto.objects.select_related("proyecto"), pk=pk)
    form = FaseProyectoForm(instance=fase)
    if request.method == "POST":
        form = FaseProyectoForm(request.POST, instance=fase)
        if form.is_valid():
            form.save()
            messages.success(request, "Fase actualizada correctamente.")
            return redirect("fase_detalle", pk=fase.pk)
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
def actualizar_estado(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    form = EstadoProyectoForm(instance=proyecto)
    if request.method == "POST":
        form = EstadoProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado del proyecto actualizado.")
            return redirect("proyecto_detalle", pk=proyecto.pk)
    return render(
        request,
        "proyectos/accion_form.html",
        {
            "proyecto": proyecto,
            "form": form,
            "titulo": "Actualizar estado",
            "descripcion": "Modifica el estado y el porcentaje de avance del proyecto.",
            "boton": "Guardar estado",
            "confirmacion": "¿Actualizar el estado y avance del proyecto?",
        },
    )


@login_required
def crear_avance(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    form = AvanceForm()
    if request.method == "POST":
        form = AvanceForm(request.POST)
        if form.is_valid():
            avance = form.save(commit=False)
            avance.proyecto = proyecto
            avance.save()
            messages.success(request, "Avance registrado correctamente.")
            return redirect("proyecto_detalle", pk=proyecto.pk)
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
    proyecto = get_object_or_404(Proyecto, pk=pk)
    form = TareaForm()
    if request.method == "POST":
        form = TareaForm(request.POST)
        if form.is_valid():
            tarea = form.save(commit=False)
            tarea.proyecto = proyecto
            tarea.save()
            messages.success(request, "Tarea creada correctamente.")
            return redirect("proyecto_detalle", pk=proyecto.pk)
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
    proyecto = get_object_or_404(Proyecto, pk=pk)
    form = EvidenciaForm()
    if request.method == "POST":
        form = EvidenciaForm(request.POST, request.FILES)
        if form.is_valid():
            evidencia = form.save(commit=False)
            evidencia.proyecto = proyecto
            evidencia.usuario = request.user
            evidencia.save()
            messages.success(request, "Evidencia subida correctamente.")
            return redirect("proyecto_detalle", pk=proyecto.pk)
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
    tarea = get_object_or_404(Tarea, pk=pk)
    if request.method == "POST":
        tarea.estado = Tarea.Estado.COMPLETADA
        tarea.save(update_fields=["estado", "actualizada_en"])
        messages.success(request, "Tarea marcada como completada.")
    return redirect("proyecto_detalle", pk=tarea.proyecto_id)


@login_required
def crear_observacion(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    form = ObservacionForm()
    if request.method == "POST":
        form = ObservacionForm(request.POST)
        if form.is_valid():
            observacion = form.save(commit=False)
            observacion.proyecto = proyecto
            observacion.usuario = request.user
            observacion.save()
            messages.success(request, "Observación agregada correctamente.")
            return redirect("proyecto_detalle", pk=proyecto.pk)
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
