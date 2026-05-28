from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0026_proyecto_mesa_trabajo_estado"),
    ]

    operations = [
        migrations.AddField(
            model_name="evidencia",
            name="tarea",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="evidencias",
                to="proyectos.tarea",
            ),
        ),
    ]
