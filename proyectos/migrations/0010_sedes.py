from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0009_proyecto_empresa_externa"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="sede",
            field=models.CharField(
                choices=[("puerto_montt", "Puerto Montt"), ("osorno", "Osorno")],
                default="puerto_montt",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="sede",
            field=models.CharField(
                choices=[("puerto_montt", "Puerto Montt"), ("osorno", "Osorno")],
                default="puerto_montt",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="iteminventario",
            name="sede",
            field=models.CharField(
                choices=[("puerto_montt", "Puerto Montt"), ("osorno", "Osorno")],
                default="puerto_montt",
                max_length=30,
            ),
        ),
    ]
