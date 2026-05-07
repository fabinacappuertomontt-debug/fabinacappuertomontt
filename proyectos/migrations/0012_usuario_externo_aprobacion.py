from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0011_usuario_verificacion_correo"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="estado_registro",
            field=models.CharField(
                choices=[
                    ("aprobado", "Aprobado"),
                    ("verificacion_correo", "Verificacion de correo"),
                    ("pendiente_aprobacion", "Pendiente de aprobacion"),
                    ("rechazado", "Rechazado"),
                ],
                default="aprobado",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="usuario",
            name="institucion",
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
