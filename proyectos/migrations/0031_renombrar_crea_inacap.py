from django.db import migrations


def aplicar_crea_inacap(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Area = apps.get_model("proyectos", "Area")

    Organizacion.objects.filter(slug="fab-inacap-puerto-montt").update(
        nombre="Crea INACAP Puerto Montt"
    )
    Area.objects.filter(slug="fab-puerto-montt").update(
        nombre="Crea INACAP Puerto Montt"
    )


def revertir_crea_inacap(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Area = apps.get_model("proyectos", "Area")

    Organizacion.objects.filter(slug="fab-inacap-puerto-montt").update(
        nombre="FAB INACAP Puerto Montt"
    )
    Area.objects.filter(slug="fab-puerto-montt").update(
        nombre="FAB Puerto Montt"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0030_organizacion_preferencias_visuales"),
    ]

    operations = [
        migrations.RunPython(aplicar_crea_inacap, revertir_crea_inacap),
    ]
