from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0018_proyecto_metodologia"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="ultima_actividad",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
