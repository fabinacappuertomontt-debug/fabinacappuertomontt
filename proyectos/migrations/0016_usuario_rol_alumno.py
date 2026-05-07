from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0015_usuario_perfil_datos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="rol",
            field=models.CharField(
                choices=[
                    ("alumno", "Alumno"),
                    ("practicante", "Practicante"),
                    ("profesor", "Profesor / Líder"),
                    ("administrador", "Administrador"),
                ],
                default="practicante",
                max_length=20,
            ),
        ),
    ]
