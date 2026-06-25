from django.core.management.base import BaseCommand
from proyectos.models import SoftwareConfiguracion, CarpetaArchivos, ArchivoAdjunto

class Command(BaseCommand):
    help = 'Migra archivo_configuracion antiguo a carpetas'

    def handle(self, *args, **options):
        for sw in SoftwareConfiguracion.objects.exclude(archivo_configuracion=''):
            if not sw.archivo_configuracion:
                continue
            carpeta, _ = CarpetaArchivos.objects.get_or_create(
                software=sw, nombre='General'
            )
            ArchivoAdjunto.objects.create(
                carpeta=carpeta,
                archivo=sw.archivo_configuracion,
                subido_por=sw.creado_por,
            )
            self.stdout.write(f'Migrado: {sw.nombre}')
