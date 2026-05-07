from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0016_usuario_rol_alumno"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iteminventario",
            name="area",
            field=models.CharField(
                choices=[
                    ("impresion_3d", "Impresión 3D"),
                    ("computacion", "Computación"),
                    ("herramientas", "Herramientas"),
                    ("electronica", "Electrónica"),
                    ("insumos", "Insumos"),
                    ("otros", "Otros"),
                ],
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="usuario",
            name="estado_registro",
            field=models.CharField(
                choices=[
                    ("aprobado", "Aprobado"),
                    ("verificacion_correo", "Verificación de correo"),
                    ("pendiente_aprobacion", "Pendiente de aprobación"),
                    ("rechazado", "Rechazado"),
                ],
                default="aprobado",
                max_length=30,
            ),
        ),
    ]
