"""Renombra la paleta 'inacap' a 'clasica'.

El valor viajaba al HTML dentro del <option> del selector de paleta, asi que
delataba la marca de un cliente en el panel de cualquier otra empresa.
"""

from django.db import migrations


def aplicar(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Organizacion.objects.filter(paleta_visual="inacap").update(paleta_visual="clasica")


def revertir(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Organizacion.objects.filter(paleta_visual="clasica").update(paleta_visual="inacap")


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0044_alter_organizacion_alias_login_and_more"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
