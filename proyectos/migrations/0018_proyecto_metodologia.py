from django.db import migrations, models


def poblar_metodologia(apps, schema_editor):
    Proyecto = apps.get_model("proyectos", "Proyecto")
    Proyecto.objects.filter(tipo_proyecto="tecnologico").update(metodologia="trl")
    Proyecto.objects.exclude(tipo_proyecto="tecnologico").update(metodologia="simple")


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0017_ortografia_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="metodologia",
            field=models.CharField(
                choices=[
                    ("simple", "Proyecto simple"),
                    ("trl", "Proyecto con TRL"),
                ],
                default="simple",
                max_length=20,
            ),
        ),
        migrations.RunPython(poblar_metodologia, migrations.RunPython.noop),
    ]
