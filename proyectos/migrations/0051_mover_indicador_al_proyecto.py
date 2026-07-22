"""Paso 1 de 3: agrega la columna proyecto al indicador, todavia opcional.

El cambio completo va en tres migraciones porque Postgres no permite mezclar
ALTER TABLE con modificacion de filas en la misma transaccion.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0050_proyecto_paso_wizard_alter_proyecto_estado"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="indicadorcatalogo",
            name="indicador_unico_por_organizacion",
        ),
        migrations.AddField(
            model_name="indicadorcatalogo",
            name="proyecto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="indicadores_definidos",
                to="proyectos.proyecto",
            ),
        ),
    ]
