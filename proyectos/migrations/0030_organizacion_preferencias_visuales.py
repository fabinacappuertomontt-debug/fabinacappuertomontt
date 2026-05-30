from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0029_asignar_encargado_inacap"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizacion",
            name="modo_oscuro",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organizacion",
            name="mostrar_usuarios",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="organizacion",
            name="paleta_visual",
            field=models.CharField(
                choices=[
                    ("inacap", "INACAP"),
                    ("pacifico", "Azul pacifico"),
                    ("bosque", "Verde bosque"),
                    ("cobalto", "Cobalto"),
                    ("coral", "Coral profesional"),
                ],
                default="inacap",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="organizacion",
            name="tamano_letra",
            field=models.CharField(
                choices=[("compacta", "Compacta"), ("normal", "Normal"), ("amplia", "Amplia")],
                default="normal",
                max_length=20,
            ),
        ),
    ]
