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
    ObservacionForm,
    ProyectoForm,
    TareaForm,
)
from .models import Avance, Proyecto, Tarea, Usuario


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
        return queryset

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


class ProyectoCreateView(LoginRequiredMixin, CreateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = "proyectos/proyecto_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Proyecto creado correctamente.")
        return super().form_valid(form)


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
    }
    return render(request, "proyectos/proyecto_detalle.html", contexto)


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
