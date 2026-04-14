from django.core.management.base import BaseCommand

from proyectos.models import Usuario


USUARIOS_BASE = [
    {
        "username": "diego",
        "nombre": "Diego Henríquez",
        "email": "diego.henriquez34@inacapmail.cl",
        "rol": Usuario.Rol.PRACTICANTE,
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "jorge",
        "nombre": "Jorge Navarro",
        "email": "jorge.navarrp@inacapmail.cl",
        "rol": Usuario.Rol.PRACTICANTE,
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "victor",
        "nombre": "Víctor Marín",
        "email": "vmarina@inacap.cl",
        "rol": Usuario.Rol.PROFESOR,
        "is_staff": True,
        "is_superuser": True,
    },
]


class Command(BaseCommand):
    help = "Crea o actualiza los usuarios base del proyecto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="Inacap2026",
            help="Contraseña para crear o actualizar los usuarios base.",
        )

    def handle(self, *args, **options):
        password = options["password"]

        for datos in USUARIOS_BASE:
            usuario, creado = Usuario.objects.get_or_create(
                username=datos["username"],
                defaults={
                    "nombre": datos["nombre"],
                    "email": datos["email"],
                    "rol": datos["rol"],
                    "is_staff": datos["is_staff"],
                    "is_superuser": datos["is_superuser"],
                },
            )

            if creado:
                estado = "creado"
            else:
                for campo in ["nombre", "email", "rol", "is_staff", "is_superuser"]:
                    setattr(usuario, campo, datos[campo])
                estado = "actualizado"

            usuario.set_password(password)
            usuario.save()
            self.stdout.write(self.style.SUCCESS(f"{usuario.username} {estado}."))

        self.stdout.write(
            self.style.WARNING(
                "Usuarios listos para iniciar sesión con correo y la contraseña indicada."
            )
        )
