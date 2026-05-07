from django.db import migrations, models
import django.db.models.deletion


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


def crear_fases_trl(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    FaseProyecto = apps.get_model("proyectos", "FaseProyecto")
    for proyecto in Proyecto.objects.all():
        for trl, nombre in TRL_DEFINICIONES:
            FaseProyecto.objects.get_or_create(
                proyecto=proyecto,
                trl=trl,
                defaults={
                    "nombre": nombre,
                    "objetivo": f"Evidenciar el cumplimiento del {nombre.lower()}.",
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0002_evidencia"),
    ]

    operations = [
        migrations.CreateModel(
            name="FaseProyecto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trl", models.PositiveSmallIntegerField(choices=TRL_DEFINICIONES)),
                ("nombre", models.CharField(max_length=200)),
                ("objetivo", models.TextField()),
                ("realizado", models.TextField(blank=True)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("completada", "Completada")], default="pendiente", max_length=20)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("proyecto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fases", to="proyectos.proyecto")),
            ],
            options={
                "ordering": ["trl"],
                "unique_together": {("proyecto", "trl")},
            },
        ),
        migrations.RunPython(crear_fases_trl, migrations.RunPython.noop),
    ]
