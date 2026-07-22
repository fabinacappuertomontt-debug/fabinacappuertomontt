"""Paso 2 de 3: reparte los indicadores de la organizacion entre sus proyectos.

Un indicador responde al resultado que mide, asi que ofrecer los de otros
proyectos de la empresa al crear uno nuevo era ruido y no ayuda.
"""

from django.db import migrations


def repartir_por_proyecto(apps, schema_editor):
    IndicadorCatalogo = apps.get_model("proyectos", "IndicadorCatalogo")
    IndicadorResultado = apps.get_model("proyectos", "IndicadorResultado")

    por_proyecto = {}
    usos = IndicadorResultado.objects.filter(catalogo__isnull=False).select_related(
        "catalogo", "resultado__objetivo__proyecto"
    )
    for uso in usos:
        proyecto_id = uso.resultado.objetivo.proyecto_id
        origen = uso.catalogo
        clave = (proyecto_id, origen.nombre)

        entrada = por_proyecto.get(clave)
        if entrada is None:
            entrada, _ = IndicadorCatalogo.objects.get_or_create(
                proyecto_id=proyecto_id,
                nombre=origen.nombre,
                defaults={
                    # organizacion sigue siendo obligatoria hasta la 0053.
                    "organizacion_id": origen.organizacion_id,
                    "tipo": origen.tipo,
                    "unidad": origen.unidad,
                    "medio_verificacion": origen.medio_verificacion,
                    "activo": origen.activo,
                },
            )
            por_proyecto[clave] = entrada

        IndicadorResultado.objects.filter(pk=uso.pk).update(catalogo=entrada)

    # Las entradas que colgaban de la organizacion ya no las usa nadie.
    IndicadorCatalogo.objects.filter(proyecto__isnull=True).delete()


def revertir(apps, schema_editor):
    # Volver atras perderia a que proyecto pertenecia cada indicador.
    IndicadorCatalogo = apps.get_model("proyectos", "IndicadorCatalogo")
    IndicadorResultado = apps.get_model("proyectos", "IndicadorResultado")
    IndicadorResultado.objects.update(catalogo=None)
    IndicadorCatalogo.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0051_mover_indicador_al_proyecto"),
    ]

    operations = [
        migrations.RunPython(repartir_por_proyecto, revertir),
    ]
