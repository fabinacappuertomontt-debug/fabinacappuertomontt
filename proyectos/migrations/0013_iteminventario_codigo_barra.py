from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0012_usuario_externo_aprobacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="iteminventario",
            name="codigo_barra",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddConstraint(
            model_name="iteminventario",
            constraint=models.UniqueConstraint(
                fields=("sede", "codigo_barra"),
                name="item_inventario_codigo_barra_por_sede",
            ),
        ),
    ]
