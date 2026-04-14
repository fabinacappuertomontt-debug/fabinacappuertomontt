import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Evidencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True)),
                ("archivo", models.FileField(upload_to="evidencias/%Y/%m/")),
                ("fecha_subida", models.DateTimeField(auto_now_add=True)),
                ("proyecto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidencias", to="proyectos.proyecto")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evidencias_subidas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-fecha_subida"],
            },
        ),
    ]
