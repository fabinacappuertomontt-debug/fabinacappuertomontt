from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0024_revisioniaetapa"),
    ]

    operations = [
        migrations.AddField(
            model_name="faseproyecto",
            name="evidencias_sugeridas",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
