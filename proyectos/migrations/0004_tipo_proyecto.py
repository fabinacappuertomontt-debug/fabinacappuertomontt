from django.db import migrations, models


TRL_FASES = [
    (1, "Principios básicos observados", "Evidenciar el cumplimiento de los principios básicos observados."),
    (2, "Concepto tecnológico formulado", "Evidenciar el cumplimiento del concepto tecnológico formulado."),
    (3, "Prueba de concepto experimental", "Evidenciar el cumplimiento de la prueba de concepto experimental."),
    (4, "Validación en laboratorio", "Evidenciar el cumplimiento de la validación en laboratorio."),
    (5, "Validación en entorno relevante", "Evidenciar el cumplimiento de la validación en entorno relevante."),
    (6, "Prototipo demostrado en entorno relevante", "Evidenciar el cumplimiento del prototipo demostrado en entorno relevante."),
    (7, "Prototipo demostrado en entorno real", "Evidenciar el cumplimiento del prototipo demostrado en entorno real."),
    (8, "Sistema completo y validado", "Evidenciar el cumplimiento del sistema completo y validado."),
    (9, "Sistema probado con éxito en entorno real", "Evidenciar el cumplimiento del sistema probado con éxito en entorno real."),
]

ACTIVIDAD_FASES = [
    (1, "Planificación", "Definir objetivo, público, fecha tentativa y responsables de la actividad."),
    (2, "Preparación de materiales", "Preparar presentación, pauta, recursos y materiales necesarios."),
    (3, "Coordinación y difusión", "Coordinar sala, participantes, difusión y confirmaciones."),
    (4, "Ejecución", "Realizar la actividad y dejar registro de asistencia o evidencia."),
    (5, "Evaluación", "Registrar resultados, comentarios, aprendizajes y mejoras detectadas."),
    (6, "Cierre", "Cerrar la actividad con evidencias, conclusiones y próximos pasos."),
]

GENERAL_FASES = [
    (1, "Levantamiento", "Levantar necesidad, alcance inicial y responsables."),
    (2, "Planificación", "Ordenar actividades, fechas, tareas y recursos disponibles."),
    (3, "Ejecución", "Ejecutar las tareas principales y registrar avances."),
    (4, "Validación", "Revisar resultados, evidencias y cumplimiento del objetivo."),
    (5, "Cierre", "Cerrar el proyecto con conclusiones y pendientes documentados."),
]

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


def detectar_tipo(proyecto):
    texto = f"{proyecto.nombre} {proyecto.descripcion}".lower()
    if any(palabra in texto for palabra in PALABRAS_TECNOLOGIA):
        return "tecnologico"
    if any(palabra in texto for palabra in PALABRAS_ACTIVIDAD):
        return "actividad"
    return "general"


def fases_para_tipo(tipo):
    if tipo == "tecnologico":
        return TRL_FASES
    if tipo == "actividad":
        return ACTIVIDAD_FASES
    return GENERAL_FASES


def clasificar_proyectos(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    FaseProyecto = apps.get_model("proyectos", "FaseProyecto")
    for proyecto in Proyecto.objects.all():
        tipo = detectar_tipo(proyecto)
        fases = fases_para_tipo(tipo)
        total_fases = len(fases)
        completadas = total_fases if proyecto.estado == "finalizado" else round((proyecto.porcentaje_avance or 0) * total_fases / 100)

        proyecto.tipo_proyecto = tipo
        proyecto.save(update_fields=["tipo_proyecto"])
        FaseProyecto.objects.filter(proyecto=proyecto).delete()
        for numero, nombre, objetivo in fases:
            estado = "completada" if numero <= completadas else "pendiente"
            FaseProyecto.objects.create(
                proyecto=proyecto,
                trl=numero,
                nombre=nombre,
                objetivo=objetivo,
                estado=estado,
            )


def revertir_tipo(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0003_faseproyecto"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="tipo_proyecto",
            field=models.CharField(
                choices=[
                    ("tecnologico", "Proyecto tecnológico"),
                    ("actividad", "Actividad académica"),
                    ("general", "Proyecto general"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.RunPython(clasificar_proyectos, revertir_tipo),
    ]
