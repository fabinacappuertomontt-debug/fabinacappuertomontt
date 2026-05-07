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


class Sede(models.TextChoices):
    PUERTO_MONTT = "puerto_montt", "Puerto Montt"
    OSORNO = "osorno", "Osorno"


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
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

    nombre = models.CharField(max_length=200)
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
        return self.fases_relevantes.count()

    @property
    def fases_completadas_relevantes(self):
        return self.fases_relevantes.filter(estado=FaseProyecto.Estado.COMPLETADA).count()

    @property
    def fase_actual(self):
        return self.fases_relevantes.filter(estado=FaseProyecto.Estado.COMPLETADA).order_by("-trl").first()

    @property
    def nivel_actual(self):
        if self.fase_actual:
            return self.fase_actual.trl
        if self.usa_trl:
            return self.trl_inicial_efectivo
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
            if not self.fase_actual:
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



class ItemInventario(models.Model):
    class Area(models.TextChoices):
        IMPRESION_3D = "impresion_3d", "Impresión 3D"
        COMPUTACION = "computacion", "Computación"
        HERRAMIENTAS = "herramientas", "Herramientas"
        ELECTRONICA = "electronica", "Electrónica"
        INSUMOS = "insumos", "Insumos"
        OTROS = "otros", "Otros"

    class Tipo(models.TextChoices):
        FUNGIBLE = "fungible", "Fungible"
        NO_FUNGIBLE = "no_fungible", "No fungible"

    nombre = models.CharField(max_length=180)
    codigo_barra = models.CharField(max_length=80, blank=True, null=True)
    sede = models.CharField(
        max_length=30,
        choices=Sede.choices,
        default=Sede.PUERTO_MONTT,
    )
    area = models.CharField(max_length=30, choices=Area.choices)
    categoria = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unidad = models.CharField(max_length=40)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=120)
    ubicacion = models.CharField(max_length=160, blank=True)
    observacion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
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
        return self.tipo == self.Tipo.FUNGIBLE

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
        return f"{self.remitente} -> {self.destinatario}"
