"""Deja los datos existentes con organización explícita.

Antes de esta migración el inventario y el software eran globales: cualquier usuario
autenticado los veía, sin importar su organización. Al agregar la FK se quedaron en
NULL, así que aquí los repartimos entre las organizaciones que ya existen para que el
filtrado por tenant no deje huérfanos invisibles.
"""

from django.db import migrations


SEDE_A_SLUG = {
    "puerto_montt": "fab-inacap-puerto-montt",
    "osorno": "crea-inacap-osorno",
}


def aplicar(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    ItemInventario = apps.get_model("proyectos", "ItemInventario")
    SoftwareConfiguracion = apps.get_model("proyectos", "SoftwareConfiguracion")

    # El alias deja de estar hardcodeado en las vistas: /login/inacap/ sigue funcionando
    # porque ahora es un dato de la organización.
    Organizacion.objects.filter(slug="fab-inacap-puerto-montt").update(alias_login="inacap")

    por_slug = {org.slug: org for org in Organizacion.objects.all()}
    if not por_slug:
        return

    organizacion_defecto = por_slug.get("fab-inacap-puerto-montt") or next(iter(por_slug.values()))

    for sede, slug in SEDE_A_SLUG.items():
        organizacion = por_slug.get(slug)
        if organizacion:
            ItemInventario.objects.filter(organizacion__isnull=True, sede=sede).update(
                organizacion=organizacion
            )
    ItemInventario.objects.filter(organizacion__isnull=True).update(organizacion=organizacion_defecto)

    for software in SoftwareConfiguracion.objects.filter(organizacion__isnull=True).select_related(
        "creado_por", "proyecto_asociado"
    ):
        organizacion_id = (
            getattr(software.creado_por, "organizacion_id", None)
            or getattr(software.proyecto_asociado, "organizacion_id", None)
            or organizacion_defecto.pk
        )
        SoftwareConfiguracion.objects.filter(pk=software.pk).update(organizacion_id=organizacion_id)


def revertir(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Organizacion.objects.filter(alias_login="inacap").update(alias_login=None)


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0042_iteminventario_organizacion_organizacion_alias_login_and_more"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
