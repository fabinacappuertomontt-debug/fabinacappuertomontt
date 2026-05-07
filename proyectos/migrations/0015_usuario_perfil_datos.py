from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0014_mensajeprivado"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="biografia",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="usuario",
            name="cargo",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="usuario",
            name="direccion",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="usuario",
            name="foto",
            field=models.ImageField(blank=True, null=True, upload_to="perfiles/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="usuario",
            name="telefono",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
