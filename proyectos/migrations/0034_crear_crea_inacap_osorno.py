from django.db import migrations


AREAS_OSORNO = [
    ("crea-inacap-osorno", "Crea INACAP Osorno", "crea.osorno@inacap.cl", True),
    ("direccion-vida-estudiantil-dae-osorno", "Dirección de Vida Estudiantil (DAE)", "", False),
    ("registro-curricular-osorno", "Registro Curricular", "", False),
    ("apoyo-pedagogico-osorno", "Apoyo Pedagógico y Académico", "", False),
    ("admision-comunicaciones-osorno", "Admisión y Comunicaciones", "", False),
    ("educacion-continua-osorno", "Educación Continua", "", False),
    ("biblioteca-osorno", "Biblioteca", "", False),
    ("finanzas-tesoreria-osorno", "Finanzas / Tesorería", "", False),
    ("soporte-informatico-osorno", "Soporte Informático", "", False),
    ("vinculacion-medio-innovacion-osorno", "Vinculación con el Medio e Innovación", "", False),
    ("turismo-gastronomia-osorno", "Turismo y Hospitalidad / Gastronomía", "", False),
    ("informatica-telecomunicaciones-osorno", "Informática y Telecomunicaciones / Diseño e Industria Digital", "", False),
    ("mecanica-electromovilidad-osorno", "Mecánica / Electromovilidad", "", False),
    ("electricidad-electronica-osorno", "Electricidad y Electrónica", "", False),
    ("administracion-negocios-osorno", "Administración y Negocios / Agrícola", "", False),
    ("salud-osorno", "Salud", "", False),
]


def crear_organizacion_osorno(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Area = apps.get_model("proyectos", "Area")

    organizacion, _ = Organizacion.objects.get_or_create(
        slug="crea-inacap-osorno",
        defaults={
            "nombre": "Crea INACAP Osorno",
            "color_principal": "#cf3f4f",
            "color_secundario": "#1f334d",
            "activa": True,
        },
    )

    for slug, nombre, correo, es_fab in AREAS_OSORNO:
        Area.objects.update_or_create(
            organizacion=organizacion,
            slug=slug,
            defaults={
                "nombre": nombre,
                "correo_contacto": correo,
                "activa": True,
                "es_fab": es_fab,
            },
        )


def revertir_organizacion_osorno(apps, schema_editor):
    Organizacion = apps.get_model("proyectos", "Organizacion")
    Area = apps.get_model("proyectos", "Area")

    try:
        organizacion = Organizacion.objects.get(slug="crea-inacap-osorno")
    except Organizacion.DoesNotExist:
        return

    Area.objects.filter(organizacion=organizacion).delete()
    organizacion.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0033_proyecto_foto"),
    ]

    operations = [
        migrations.RunPython(crear_organizacion_osorno, revertir_organizacion_osorno),
    ]
