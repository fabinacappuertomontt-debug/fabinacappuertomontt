from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0013_iteminventario_codigo_barra"),
    ]

    operations = [
        migrations.CreateModel(
            name="MensajePrivado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("texto", models.TextField(blank=True)),
                ("archivo", models.FileField(blank=True, null=True, upload_to="chat/%Y/%m/")),
                ("leido", models.BooleanField(default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "destinatario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mensajes_recibidos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "remitente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mensajes_enviados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "mensaje privado",
                "verbose_name_plural": "mensajes privados",
                "ordering": ["creado_en"],
            },
        ),
    ]
