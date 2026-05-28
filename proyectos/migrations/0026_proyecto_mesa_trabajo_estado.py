from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0025_faseproyecto_evidencias_sugeridas"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="mesa_trabajo_actualizada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="mesa_trabajo_estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("generando", "Generando con IA"),
                    ("lista", "Lista"),
                    ("error", "Con respaldo por reglas"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="mesa_trabajo_mensaje",
            field=models.CharField(blank=True, max_length=240),
        ),
    ]
