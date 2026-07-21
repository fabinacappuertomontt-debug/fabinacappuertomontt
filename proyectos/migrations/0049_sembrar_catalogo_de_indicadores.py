"""Convierte los indicadores de texto que ya existen en un catalogo por empresa.

Asi el selector aparece poblado desde el primer dia con lo que cada
organizacion ya venia midiendo, en vez de arrancar vacio y obligar a escribir
de nuevo lo mismo que ya estaba.
"""

from django.db import migrations

# Los textos muy cortos ("1") o muy largos son basura acumulada, no indicadores.
LARGO_MINIMO = 12
LARGO_MAXIMO = 200


def sembrar(apps, schema_editor):
    IndicadorResultado = apps.get_model("proyectos", "IndicadorResultado")
    IndicadorCatalogo = apps.get_model("proyectos", "IndicadorCatalogo")

    indicadores = IndicadorResultado.objects.select_related(
        "resultado__objetivo__proyecto"
    ).all()

    catalogo_por_clave = {}
    for indicador in indicadores:
        proyecto = indicador.resultado.objetivo.proyecto
        organizacion_id = proyecto.organizacion_id
        nombre = (indicador.descripcion or "").strip()
        if not organizacion_id or not (LARGO_MINIMO <= len(nombre) <= LARGO_MAXIMO):
            continue

        clave = (organizacion_id, nombre)
        entrada = catalogo_por_clave.get(clave)
        if entrada is None:
            entrada, _ = IndicadorCatalogo.objects.get_or_create(
                organizacion_id=organizacion_id,
                nombre=nombre,
                defaults={
                    # No se sabe como se median, asi que entran como descriptivos
                    # y conservan su marca manual. Al editarlos se les puede dar
                    # unidad y meta numerica.
                    "tipo": "cualitativo",
                    "activo": True,
                },
            )
            catalogo_por_clave[clave] = entrada

        IndicadorResultado.objects.filter(pk=indicador.pk).update(
            catalogo=entrada, tipo="cualitativo"
        )


def revertir(apps, schema_editor):
    IndicadorResultado = apps.get_model("proyectos", "IndicadorResultado")
    IndicadorCatalogo = apps.get_model("proyectos", "IndicadorCatalogo")
    IndicadorResultado.objects.update(catalogo=None)
    IndicadorCatalogo.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0048_indicadorresultado_linea_base_and_more"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
