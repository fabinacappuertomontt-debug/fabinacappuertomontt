"""Paso 3 de 3: el indicador ya solo puede pertenecer a un proyecto."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0052_indicador_solo_del_proyecto"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="indicadorcatalogo",
            name="organizacion",
        ),
        migrations.AlterField(
            model_name="indicadorcatalogo",
            name="proyecto",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="indicadores_definidos",
                to="proyectos.proyecto",
            ),
        ),
        migrations.AddConstraint(
            model_name="indicadorcatalogo",
            constraint=models.UniqueConstraint(
                fields=("proyecto", "nombre"), name="indicador_unico_por_proyecto"
            ),
        ),
        migrations.AlterModelOptions(
            name="indicadorcatalogo",
            options={
                "ordering": ["nombre"],
                "verbose_name": "indicador del proyecto",
                "verbose_name_plural": "indicadores del proyecto",
            },
        ),
    ]
