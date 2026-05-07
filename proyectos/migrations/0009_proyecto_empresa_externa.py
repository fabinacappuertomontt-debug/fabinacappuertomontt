from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0008_proyecto_trl_inicial_proyecto_trl_objetivo"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_nombre",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_rut",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_rubro",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_contacto",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_correo",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_telefono",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_rol",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="empresa_externa_observaciones",
            field=models.TextField(blank=True),
        ),
    ]
