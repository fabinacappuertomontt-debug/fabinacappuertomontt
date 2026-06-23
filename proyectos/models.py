import calendar
from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings



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


def sumar_meses_y_dias(fecha_base, meses=0, dias=0):
    if not fecha_base:
        return None
    meses = meses or 0
    dias = dias or 0
    year = fecha_base.year + ((fecha_base.month - 1 + meses) // 12)
    month = ((fecha_base.month - 1 + meses) % 12) + 1
    day = min(fecha_base.day, calendar.monthrange(year, month)[1])
    fecha_resultado = date(year, month, day)
    if dias:
        fecha_resultado += timezone.timedelta(days=dias)
    return fecha_resultado


# Definiciones normalizadas para evitar texto mojibake en fases y tarjetas.
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


class Sede(models.TextChoices):
    PUERTO_MONTT = "puerto_montt", "Puerto Montt"
    OSORNO = "osorno", "Osorno"


class Organizacion(models.Model):
    class TamanoLetra(models.TextChoices):
        COMPACTA = "compacta", "Compacta"
        NORMAL = "normal", "Normal"
        AMPLIA = "amplia", "Amplia"

    class PaletaVisual(models.TextChoices):
        INACAP = "inacap", "INACAP"
        PACIFICO = "pacifico", "Azul pacifico"
        BOSQUE = "bosque", "Verde bosque"
        COBALTO = "cobalto", "Cobalto"
        CORAL = "coral", "Coral profesional"

    nombre = models.CharField(max_length=180)
    slug = models.SlugField(max_length=80, unique=True)
    logo = models.ImageField(upload_to="organizaciones/logos/%Y/%m/", blank=True, null=True)
    color_principal = models.CharField(max_length=7, default="#cf3f4f")
    color_secundario = models.CharField(max_length=7, default="#1f334d")
    paleta_visual = models.CharField(max_length=20, choices=PaletaVisual.choices, default=PaletaVisual.INACAP)
    tamano_letra = models.CharField(max_length=20, choices=TamanoLetra.choices, default=TamanoLetra.NORMAL)
    mostrar_usuarios = models.BooleanField(default=True)
    modo_oscuro = models.BooleanField(default=False)
    dominio_correo = models.CharField(
        max_length=100,
        blank=True,
        help_text="Dominio permitido para detectar usuarios de la organización, por ejemplo inacap.cl.",
    )
    encargado = models.OneToOneField(
        "Usuario",
        on_delete=models.SET_NULL,
        related_name="organizacion_encargada",
        blank=True,
        null=True,
    )
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Organizacion"
        verbose_name_plural = "Organizaciones"

    def __str__(self):
        return self.nombre

    @property
    def dominio_normalizado(self):
        return self.dominio_correo.strip().lower().lstrip("@")

    def coincide_con_email(self, email):
        dominio = self.dominio_normalizado
        if not dominio or not email:
            return False
        return email.strip().lower().endswith(f"@{dominio}")


class Area(models.Model):
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name="areas",
    )
    nombre = models.CharField(max_length=180)
    slug = models.SlugField(max_length=90)
    correo_contacto = models.EmailField(blank=True)
    activa = models.BooleanField(default=True)
    es_fab = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["organizacion", "slug"], name="area_unica_por_organizacion")
        ]
        verbose_name = "area"
        verbose_name_plural = "areas"

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        SUPERADMIN = "superadmin", "Superadmin"
        ADMIN_ORGANIZACION = "admin_organizacion", "Administrador de organizacion"
        LIDER = "lider", "Lider"
        INTEGRANTE = "integrante", "Integrante"
        ALUMNO = "alumno", "Alumno"
        PRACTICANTE = "practicante", "Practicante"
        PROFESOR = "profesor", "Profesor / Líder"
        ADMINISTRADOR = "administrador", "Administrador"

    class EstadoRegistro(models.TextChoices):
        APROBADO = "aprobado", "Aprobado"
        VERIFICACION_CORREO = "verificacion_correo", "Verificación de correo"
        PENDIENTE_APROBACION = "pendiente_aprobacion", "Pendiente de aprobación"
        RECHAZADO = "rechazado", "Rechazado"

    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    institucion = models.CharField(max_length=180, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    cargo = models.CharField(max_length=120, blank=True)
    direccion = models.CharField(max_length=180, blank=True)
    biografia = models.TextField(blank=True)
    foto = models.ImageField(upload_to="perfiles/%Y/%m/", blank=True, null=True)
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.PRACTICANTE,
    )
    sede = models.CharField(
        max_length=30,
        choices=Sede.choices,
        default=Sede.PUERTO_MONTT,
    )
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.PROTECT,
        related_name="usuarios",
        blank=True,
        null=True,
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="usuarios",
        blank=True,
        null=True,
    )
    correo_verificado = models.BooleanField(default=True)
    estado_registro = models.CharField(
        max_length=30,
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.APROBADO,
    )
    codigo_verificacion = models.CharField(max_length=6, blank=True)
    codigo_verificacion_expira = models.DateTimeField(blank=True, null=True)
    ultima_actividad = models.DateTimeField(blank=True, null=True)
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

    class Metodologia(models.TextChoices):
        SIMPLE = "simple", "Proyecto simple"
        TRL = "trl", "Proyecto con TRL"

    class MesaTrabajoEstado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        GENERANDO = "generando", "Generando con IA"
        LISTA = "lista", "Lista"
        ERROR = "error", "Con respaldo por reglas"

    nombre = models.CharField(max_length=200)
    foto = models.ImageField("Foto del proyecto", upload_to="proyectos/%Y/%m/", blank=True, null=True)
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.PROTECT,
        related_name="proyectos",
        blank=True,
        null=True,
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="proyectos",
        blank=True,
        null=True,
    )
    sede = models.CharField(
        max_length=30,
        choices=Sede.choices,
        default=Sede.PUERTO_MONTT,
    )
    descripcion = models.TextField()
    objetivo_principal = models.TextField(blank=True)
    objetivo_especifico = models.TextField(blank=True)
    resultados_esperados = models.TextField(blank=True)
    indicadores = models.TextField(blank=True)
    kpi = models.TextField(blank=True)
    empresa_externa = models.BooleanField(default=False)
    empresa_externa_nombre = models.CharField(max_length=200, blank=True)
    empresa_externa_rut = models.CharField(max_length=20, blank=True)
    empresa_externa_rubro = models.CharField(max_length=120, blank=True)
    empresa_externa_contacto = models.CharField(max_length=150, blank=True)
    empresa_externa_correo = models.EmailField(blank=True)
    empresa_externa_telefono = models.CharField(max_length=40, blank=True)
    empresa_externa_rol = models.CharField(max_length=120, blank=True)
    empresa_externa_observaciones = models.TextField(blank=True)
    tipo_proyecto = models.CharField(
        max_length=20,
        choices=TipoProyecto.choices,
        default=TipoProyecto.GENERAL,
    )
    metodologia = models.CharField(
        max_length=20,
        choices=Metodologia.choices,
        default=Metodologia.SIMPLE,
    )
    trl_inicial = models.PositiveSmallIntegerField(choices=TRL_DEFINICIONES, blank=True, null=True)
    trl_objetivo = models.PositiveSmallIntegerField(choices=TRL_DEFINICIONES, blank=True, null=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    porcentaje_avance = models.PositiveSmallIntegerField(default=0)
    mesa_trabajo_estado = models.CharField(
        max_length=20,
        choices=MesaTrabajoEstado.choices,
        default=MesaTrabajoEstado.PENDIENTE,
    )
    mesa_trabajo_mensaje = models.CharField(max_length=240, blank=True)
    mesa_trabajo_actualizada_en = models.DateTimeField(blank=True, null=True)
    creador = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="proyectos_creados",
        blank=True,
        null=True,
    )
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
    def responsables_sin_creador(self):
        if self.creador:
            return self.responsables.exclude(pk=self.creador.pk)
        return self.responsables.all()




    @property
    def usa_trl(self):
        return self.metodologia == self.Metodologia.TRL

    @property
    def trl_inicial_efectivo(self):
        return self.trl_inicial or 1

    @property
    def trl_objetivo_efectivo(self):
        return self.trl_objetivo or 9

    @property
    def fases_relevantes(self):
        fases = self.fases.all()
        if self.usa_trl:
            return fases.filter(trl__gte=self.trl_inicial_efectivo, trl__lte=self.trl_objetivo_efectivo)
        return fases.filter(trl__lte=5)

    @property
    def total_fases_relevantes(self):
        if self.usa_trl:
            return max(self.trl_objetivo_efectivo - self.trl_inicial_efectivo, 0)
        return self.fases_relevantes.count()

    @property
    def fases_completadas_relevantes(self):
        if self.usa_trl:
            return max(self.nivel_actual - self.trl_inicial_efectivo, 0)
        return self.fases_relevantes.filter(estado=FaseProyecto.Estado.COMPLETADA).count()

    @property
    def fase_actual(self):
        if self.usa_trl:
            return self.fases_relevantes.filter(trl=self.nivel_actual).first()
        return self.fases_relevantes.filter(estado=FaseProyecto.Estado.COMPLETADA).order_by("-trl").first()

    @property
    def resultados_trl(self):
        return ResultadoEsperado.objects.filter(objetivo__proyecto=self).select_related("objetivo").prefetch_related("indicadores")

    def calcular_trl_desde_resultados(self):
        if not self.usa_trl:
            return 0
        nivel = self.trl_inicial_efectivo
        resultados_por_trl = {}
        for resultado in self.resultados_trl:
            resultados_por_trl.setdefault(resultado.trl_objetivo, []).append(resultado)
        for trl in range(self.trl_inicial_efectivo + 1, self.trl_objetivo_efectivo + 1):
            resultados_nivel = resultados_por_trl.get(trl, [])
            if not resultados_nivel:
                break
            if all(resultado.esta_cumplido for resultado in resultados_nivel):
                nivel = trl
            else:
                break
        return nivel

    @property
    def nivel_actual(self):
        if self.usa_trl:
            return self.calcular_trl_desde_resultados()
        if self.fase_actual:
            return self.fase_actual.trl
        return 0

    @property
    def trl_actual(self):
        return self.nivel_actual

    @property
    def avance_fases_actual(self):
        return self.nivel_actual

    @property
    def nivel_actual_texto(self):
        if self.usa_trl:
            if self.nivel_actual == self.trl_inicial_efectivo:
                return f"TRL base {self.trl_inicial_efectivo}: {TRL_DESCRIPCIONES[self.trl_inicial_efectivo]}"
            return f"TRL actual {self.nivel_actual}: {TRL_DESCRIPCIONES[self.nivel_actual]}"
        if not self.fase_actual:
            return "Sin fases completadas"
        return f"Fase {self.fase_actual.trl}: {self.fase_actual.nombre}"

    @property
    def trl_actual_texto(self):
        return self.nivel_actual_texto

    @property
    def siguiente_fase(self):
        if self.usa_trl:
            siguiente_trl = self.nivel_actual + 1
            if siguiente_trl > self.trl_objetivo_efectivo:
                return None
            return self.fases_relevantes.filter(trl=siguiente_trl).first()
        return self.fases_relevantes.exclude(estado=FaseProyecto.Estado.COMPLETADA).order_by("trl").first()

    @property
    def trl_siguiente(self):
        return self.siguiente_fase

    @property
    def nombre_escala(self):
        return "Madurez tecnológica TRL" if self.usa_trl else "Fases del proyecto"


    @property
    def rango_trl_texto(self):
        if not self.usa_trl:
            return ""
        return f"TRL {self.trl_inicial_efectivo} a TRL {self.trl_objetivo_efectivo}"


class ObjetivoEspecifico(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="objetivos",
    )
    descripcion = models.TextField()
    orden = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"Objetivo {self.orden} - {self.proyecto}"


class ResultadoEsperado(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        CUMPLIDO = "cumplido", "Cumplido"

    objetivo = models.ForeignKey(
        ObjetivoEspecifico,
        on_delete=models.CASCADE,
        related_name="resultados",
    )
    descripcion = models.TextField()
    orden = models.PositiveSmallIntegerField(default=1)
    trl_objetivo = models.PositiveSmallIntegerField(choices=TRL_DEFINICIONES)
    plazo_meses = models.PositiveSmallIntegerField(default=0)
    plazo_dias = models.PositiveSmallIntegerField(default=0)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    fecha_cumplimiento = models.DateField(blank=True, null=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"Resultado {self.orden} - {self.objetivo.proyecto}"

    @property
    def proyecto(self):
        return self.objetivo.proyecto

    @property
    def fecha_objetivo(self):
        return sumar_meses_y_dias(
            self.proyecto.fecha_inicio,
            self.plazo_meses,
            self.plazo_dias,
        )

    @property
    def plazo_texto(self):
        partes = []
        if self.plazo_meses:
            partes.append(f"{self.plazo_meses} mes{'es' if self.plazo_meses != 1 else ''}")
        if self.plazo_dias:
            partes.append(f"{self.plazo_dias} dia{'s' if self.plazo_dias != 1 else ''}")
        return ", ".join(partes) if partes else "Sin plazo definido"

    @property
    def indicadores_totales(self):
        return self.indicadores.count()

    @property
    def indicadores_cumplidos(self):
        return self.indicadores.filter(cumplido=True).count()

    @property
    def estado_calculado(self):
        if self.indicadores_totales and self.indicadores_cumplidos == self.indicadores_totales:
            return self.Estado.CUMPLIDO
        if self.indicadores.filter(
            models.Q(cumplido=True)
            | ~models.Q(valor_actual="")
        ).exists():
            return self.Estado.EN_PROCESO
        return self.Estado.PENDIENTE

    @property
    def esta_cumplido(self):
        return (
            self.estado_calculado == self.Estado.CUMPLIDO
            and self.indicadores_totales > 0
            and self.indicadores_cumplidos == self.indicadores_totales
        )

    @property
    def mes_objetivo(self):
        fecha = self.fecha_objetivo
        return fecha.strftime("%m/%Y") if fecha else ""


class IndicadorResultado(models.Model):
    resultado = models.ForeignKey(
        ResultadoEsperado,
        on_delete=models.CASCADE,
        related_name="indicadores",
    )
    descripcion = models.TextField()
    orden = models.PositiveSmallIntegerField(default=1)
    meta = models.CharField(max_length=200, blank=True)
    valor_actual = models.CharField(max_length=200, blank=True)
    cumplido = models.BooleanField(default=False)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"Indicador {self.orden} - {self.resultado}"


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
    evidencias_sugeridas = models.JSONField(default=list, blank=True)
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

    @property
    def tiene_tareas_pendientes(self):
        return self.tareas_etapa.exclude(estado="completada").exists()

    @property
    def tiene_evidencias(self):
        return self.evidencias_etapa.exists()

class Avance(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="avances",
    )
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.SET_NULL,
        related_name="avances_etapa",
        blank=True,
        null=True,
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
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.SET_NULL,
        related_name="tareas_etapa",
        blank=True,
        null=True,
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

    @property
    def numero_en_proyecto(self):
        ids = list(
            Tarea.objects.filter(proyecto=self.proyecto)
            .order_by("creada_en", "id")
            .values_list("id", flat=True)
        )
        try:
            return ids.index(self.id) + 1
        except ValueError:
            return self.pk

    @property
    def etiqueta_corta(self):
        return f"Tarea {self.numero_en_proyecto}"

    @property
    def etiqueta(self):
        return f"{self.etiqueta_corta}: {self.nombre}"


class Observacion(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="observaciones",
    )
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.SET_NULL,
        related_name="observaciones_etapa",
        blank=True,
        null=True,
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
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.SET_NULL,
        related_name="evidencias_etapa",
        blank=True,
        null=True,
    )
    tarea = models.ForeignKey(
        Tarea,
        on_delete=models.SET_NULL,
        related_name="evidencias",
        blank=True,
        null=True,
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


class RevisionIAEtapa(models.Model):
    class Decision(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADA = "aceptada", "Aceptada"
        RECHAZADA = "rechazada", "Rechazada"

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="revisiones_ia",
    )
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.CASCADE,
        related_name="revisiones_ia",
    )
    etapa_slug = models.SlugField(max_length=120)
    etapa_nombre = models.CharField(max_length=160)
    trl_actual = models.PositiveSmallIntegerField(blank=True, null=True)
    trl_sugerido = models.CharField(max_length=40, blank=True)
    recomienda_avanzar = models.BooleanField(default=False)
    confianza = models.CharField(max_length=40, blank=True)
    justificacion = models.TextField(blank=True)
    faltantes = models.JSONField(default=list, blank=True)
    acciones_sugeridas = models.JSONField(default=list, blank=True)
    respuesta = models.JSONField(default=dict, blank=True)
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDIENTE,
    )
    motivo_decision = models.TextField(blank=True)
    solicitado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="revisiones_ia_solicitadas",
        blank=True,
        null=True,
    )
    decidido_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="revisiones_ia_decididas",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    decidido_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Revision IA {self.fase} - {self.get_decision_display()}"



class ItemInventario(models.Model):
    class Area(models.TextChoices):
        IMPRESION_3D    = "impresion_3d",   "Impresión 3D"
        ELECTRONICA     = "electronica",    "Electrónica"
        CORTE_LASER     = "corte_laser",    "Corte láser"
        VINILO_PLOTEO   = "vinilo_ploteo",  "Vinilo / ploteo"
        CARPINTERIA_CNC = "carpinteria_cnc","Carpintería / CNC"
        COSTURA_TEXTIL  = "costura_textil", "Costura / textil"
        GENERAL         = "general",        "General / bodega"

    class Tipo(models.TextChoices):
        MATERIAL    = "material",    "Material / insumo"
        FILAMENTO   = "filamento",   "Filamento"
        HERRAMIENTA = "herramienta", "Herramienta"
        EQUIPO      = "equipo",      "Equipo / máquina"
        COMPONENTE  = "componente",  "Componente electrónico"
        CABLE       = "cable",       "Cable / conector"
        OTRO        = "otro",        "Otro"
        # Valores legacy (compatibilidad con registros anteriores)
        FUNGIBLE    = "fungible",    "Fungible (legacy)"
        NO_FUNGIBLE = "no_fungible", "No fungible (legacy)"

    # Tipos que descuentan stock al usarse
    TIPOS_FUNGIBLES = {"material", "filamento", "componente", "cable", "fungible"}

    class Estado(models.TextChoices):
        DISPONIBLE    = "disponible",    "Disponible"
        LIMITADO      = "limitado",      "Stock limitado"
        RESERVADO     = "reservado",     "Reservado"
        MANTENIMIENTO = "mantenimiento", "En mantenimiento"
        AGOTADO       = "agotado",       "Agotado"

    nombre       = models.CharField(max_length=180)
    codigo_barra = models.CharField(max_length=80, blank=True, null=True)
    sede         = models.CharField(max_length=30, choices=Sede.choices, default=Sede.PUERTO_MONTT)
    area         = models.CharField(max_length=30, choices=Area.choices)
    categoria    = models.CharField(max_length=120, blank=True)
    tipo         = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad     = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unidad       = models.CharField(max_length=40)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado       = models.CharField(max_length=30, choices=Estado.choices, default=Estado.DISPONIBLE)
    ubicacion    = models.CharField(max_length=160, blank=True)
    observacion  = models.TextField(blank=True)
    activo       = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["area", "categoria", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "codigo_barra"], name="item_inventario_codigo_barra_por_sede")
        ]
        verbose_name = "item de inventario"
        verbose_name_plural = "items de inventario"

    def __str__(self):
        return self.nombre

    @property
    def descuenta_stock(self):
        return self.tipo in self.TIPOS_FUNGIBLES

    @property
    def bajo_stock(self):
        return bool(
            self.descuenta_stock
            and self.cantidad is not None
            and self.stock_minimo is not None
            and self.stock_minimo > 0
            and self.cantidad <= self.stock_minimo
        )

    @property
    def cantidad_texto(self):
        if self.cantidad is None:
            return f"Variado {self.unidad}".strip()
        cantidad = int(self.cantidad) if self.cantidad == self.cantidad.to_integral() else self.cantidad
        return f"{cantidad} {self.unidad}".strip()


class UsoInventario(models.Model):
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name="usos_inventario",
    )
    item = models.ForeignKey(
        ItemInventario,
        on_delete=models.PROTECT,
        related_name="usos",
    )
    fase = models.ForeignKey(
        FaseProyecto,
        on_delete=models.SET_NULL,
        related_name="usos_inventario",
        blank=True,
        null=True,
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField(default=timezone.localdate)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="usos_inventario",
    )
    observacion = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]
        verbose_name = "uso de inventario"
        verbose_name_plural = "usos de inventario"

    def __str__(self):
        return f"{self.item} usado en {self.proyecto}"



class MovimientoStock(models.Model):
    """Registro de cada entrada o ajuste de stock de un ítem de inventario."""

    class Motivo(models.TextChoices):
        COMPRA     = "compra",     "Compra"
        DONACION   = "donacion",   "Donación"
        DEVOLUCION = "devolucion", "Devolución"
        AJUSTE     = "ajuste",     "Ajuste de inventario"
        PRODUCCION = "produccion", "Producción propia"
        OTRO       = "otro",       "Otro"

    item       = models.ForeignKey(
        ItemInventario, on_delete=models.CASCADE, related_name="movimientos"
    )
    cantidad   = models.DecimalField(max_digits=10, decimal_places=2)
    motivo     = models.CharField(max_length=20, choices=Motivo.choices, blank=True)
    observacion = models.TextField(blank=True)
    usuario    = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos_stock"
    )
    fecha      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "movimiento de stock"
        verbose_name_plural = "movimientos de stock"

    def __str__(self):
        return f"+{self.cantidad} {self.item} ({self.get_motivo_display()})"


class GrupoChat(models.Model):
    nombre = models.CharField(max_length=150)
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="grupos_creados",
    )
    miembros = models.ManyToManyField(Usuario, related_name="grupos_chat")
    sede = models.CharField(
        max_length=30,
        choices=Sede.choices,
        default=Sede.PUERTO_MONTT,
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "grupo de chat"
        verbose_name_plural = "grupos de chat"

    def __str__(self):
        return self.nombre


class Notificacion(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    url = models.CharField(max_length=255, blank=True)
    leido = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"{self.usuario.username}: {self.titulo}"


class MensajePrivado(models.Model):
    remitente = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="mensajes_enviados",
    )
    destinatario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="mensajes_recibidos",
        null=True,
        blank=True,
    )
    grupo = models.ForeignKey(
        GrupoChat,
        on_delete=models.CASCADE,
        related_name="mensajes",
        null=True,
        blank=True,
    )
    texto = models.TextField(blank=True)
    archivo = models.FileField(upload_to="chat/%Y/%m/", blank=True, null=True)
    leido = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en"]
        verbose_name = "mensaje privado"
        verbose_name_plural = "mensajes privados"

    def __str__(self):
        if self.grupo:
            return f"{self.remitente} -> Grupo: {self.grupo.nombre}"
        return f"{self.remitente} -> {self.destinatario}"


class SoftwareConfiguracion(models.Model):
    TIPO_CHOICES = [
        ('modelado', 'Modelado 3D'),
        ('slicer', 'Slicer / Impresión'),
        ('electronica', 'Electrónica / PCB'),
        ('diseno', 'Diseño gráfico / Vinilo'),
        ('otro', 'Otro'),
    ]

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='otro')
    descripcion = models.TextField(blank=True)
    archivo_configuracion = models.FileField(
        upload_to='software_config/', blank=True, null=True
    )
    icono = models.CharField(
        max_length=50, blank=True, default='ti-app-window',
        help_text="Nombre de ícono Tabler, ej: ti-printer, ti-cube"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='software_creado'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tipo', 'nombre']
        verbose_name = "Software / Configuración"
        verbose_name_plural = "Software / Configuraciones"

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    @property
    def nombre_archivo(self):
        if self.archivo_configuracion:
            return self.archivo_configuracion.name.split('/')[-1]
        return None
