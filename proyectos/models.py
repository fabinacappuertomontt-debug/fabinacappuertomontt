from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone



TRL_DEFINICIONES = [
    (1, "Principios básicos observados"),
    (2, "Concepto tecnológico formulado"),
    (3, "Prueba de concepto experimental"),
    (4, "Validación en laboratorio"),
    (5, "Validación en entorno relevante"),
    (6, "Prototipo demostrado en entorno relevante"),
    (7, "Prototipo demostrado en entorno real"),
    (8, "Sistema completo y validado"),
    (9, "Sistema probado con éxito en entorno real"),
]

TRL_DESCRIPCIONES = dict(TRL_DEFINICIONES)

ACTIVIDAD_FASES = [
    (1, "Planificación"),
    (2, "Preparación de materiales"),
    (3, "Coordinación y difusión"),
    (4, "Ejecución"),
    (5, "Evaluación"),
    (6, "Cierre"),
]

GENERAL_FASES = [
    (1, "Levantamiento"),
    (2, "Planificación"),
    (3, "Ejecución"),
    (4, "Validación"),
    (5, "Cierre"),
]


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        PRACTICANTE = "practicante", "Practicante"
        PROFESOR = "profesor", "Profesor / Líder"
        ADMINISTRADOR = "administrador", "Administrador"

    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.PRACTICANTE,
    )
    REQUIRED_FIELDS = ["nombre", "email"]

    def __str__(self):
        return self.nombre or self.username


class Proyecto(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        EN_PAUSA = "en_pausa", "En pausa"
        FINALIZADO = "finalizado", "Finalizado"

    class TipoProyecto(models.TextChoices):
        TECNOLOGICO = "tecnologico", "Proyecto tecnológico"
        ACTIVIDAD = "actividad", "Actividad académica"
        GENERAL = "general", "Proyecto general"

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    tipo_proyecto = models.CharField(
        max_length=20,
        choices=TipoProyecto.choices,
        default=TipoProyecto.GENERAL,
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    porcentaje_avance = models.PositiveSmallIntegerField(default=0)
    responsables = models.ManyToManyField(
        Usuario,
        related_name="proyectos_responsable",
        blank=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-actualizado_en", "nombre"]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("proyecto_detalle", kwargs={"pk": self.pk})

    @property
    def tareas_pendientes_count(self):
        return self.tareas.exclude(estado=Tarea.Estado.COMPLETADA).count()

    @property
    def dias_restantes(self):
        if not self.fecha_fin:
            return None
        return (self.fecha_fin - timezone.localdate()).days

    @property
    def esta_atrasado(self):
        return (
            self.fecha_fin is not None
            and self.fecha_fin < timezone.localdate()
            and self.estado != self.Estado.FINALIZADO
        )

    @property
    def nivel_alerta(self):
        if self.estado == self.Estado.FINALIZADO:
            return "ok"
        if self.esta_atrasado:
            return "riesgo"
        if self.porcentaje_avance < 40 and self.tareas_pendientes_count >= 3:
            return "riesgo"
        if self.dias_restantes is not None and self.dias_restantes <= 7 and self.porcentaje_avance < 80:
            return "advertencia"
        if self.estado == self.Estado.EN_PAUSA:
            return "advertencia"
        return "ok"

    @property
    def texto_alerta(self):
        if self.nivel_alerta == "riesgo":
            if self.esta_atrasado:
                return "Proyecto atrasado"
            return "Bajo avance y tareas pendientes"
        if self.nivel_alerta == "advertencia":
            if self.estado == self.Estado.EN_PAUSA:
                return "Proyecto en pausa"
            return "Próximo a vencer"
        return "Avance normal"




    @property
    def usa_trl(self):
        return self.tipo_proyecto == self.TipoProyecto.TECNOLOGICO

    @property
    def fase_actual(self):
        return self.fases.filter(estado=FaseProyecto.Estado.COMPLETADA).order_by("-trl").first()

    @property
    def nivel_actual(self):
        return self.fase_actual.trl if self.fase_actual else 0

    @property
    def trl_actual(self):
        return self.nivel_actual

    @property
    def avance_fases_actual(self):
        return self.nivel_actual

    @property
    def nivel_actual_texto(self):
        if self.usa_trl:
            if not self.nivel_actual:
                return "Sin TRL completado"
            return f"TRL {self.nivel_actual}: {TRL_DESCRIPCIONES[self.nivel_actual]}"
        if not self.fase_actual:
            return "Sin fases completadas"
        return f"Fase {self.fase_actual.trl}: {self.fase_actual.nombre}"

    @property
    def trl_actual_texto(self):
        return self.nivel_actual_texto

    @property
    def siguiente_fase(self):
        return self.fases.exclude(estado=FaseProyecto.Estado.COMPLETADA).order_by("trl").first()

    @property
    def trl_siguiente(self):
        return self.siguiente_fase

    @property
    def nombre_escala(self):
        return "Madurez tecnológica TRL" if self.usa_trl else "Fases del proyecto"


class FaseProyecto(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        COMPLETADA = "completada", "Completada"

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="fases",
    )
    trl = models.PositiveSmallIntegerField(choices=TRL_DEFINICIONES)
    nombre = models.CharField(max_length=200)
    objetivo = models.TextField()
    realizado = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trl"]
        unique_together = ["proyecto", "trl"]

    def __str__(self):
        return f"{self.etiqueta} - {self.proyecto}"

    @property
    def completada(self):
        return self.estado == self.Estado.COMPLETADA

    @property
    def etiqueta(self):
        if self.proyecto.usa_trl:
            return f"TRL {self.trl}"
        return f"Fase {self.trl}"

class Avance(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="avances",
    )
    descripcion = models.TextField()
    fecha = models.DateField()
    responsable = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="avances_registrados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]

    def __str__(self):
        return f"Avance de {self.proyecto} - {self.fecha}"


class Tarea(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        COMPLETADA = "completada", "Completada"

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="tareas",
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    responsable = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="tareas_asignadas",
        blank=True,
        null=True,
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["estado", "-actualizada_en"]

    def __str__(self):
        return self.nombre

    @property
    def completada(self):
        return self.estado == self.Estado.COMPLETADA


class Observacion(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="observaciones",
    )
    comentario = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="observaciones",
    )

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Observación de {self.usuario} en {self.proyecto}"


class Evidencia(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="evidencias",
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to="evidencias/%Y/%m/")
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="evidencias_subidas",
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_subida"]

    def __str__(self):
        return self.nombre
