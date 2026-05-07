from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0010_sedes"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="codigo_verificacion",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="usuario",
            name="codigo_verificacion_expira",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="correo_verificado",
            field=models.BooleanField(default=True),
        ),
    ]
