"""Crea o actualiza la cuenta de superadmin de la plataforma.

Es el arranque de un despliegue limpio: sin superadmin no hay forma de entrar a
/control/ ni de dar de alta la primera empresa.
"""

import os
import secrets

from django.core.management.base import BaseCommand, CommandError

from proyectos.models import Usuario


class Command(BaseCommand):
    help = "Crea o actualiza el superadmin dueño de la plataforma."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Correo de acceso al panel de control.")
        parser.add_argument("--nombre", default="", help="Nombre visible. Por defecto usa el correo.")
        parser.add_argument(
            "--password",
            default=None,
            help="Contraseña. Si se omite, se lee SUPERADMIN_PASSWORD o se genera una aleatoria.",
        )

    def handle(self, *args, **opciones):
        email = opciones["email"].strip().lower()
        if "@" not in email:
            raise CommandError("El correo no es válido.")

        password = opciones["password"] or os.getenv("SUPERADMIN_PASSWORD")
        generada = False
        if not password:
            password = secrets.token_urlsafe(12)
            generada = True

        usuario = Usuario.objects.filter(email__iexact=email).first()
        if usuario is None:
            usuario = Usuario(username=email.split("@")[0][:150], email=email)
            # El username debe ser unico aunque dos correos compartan la parte local.
            base = usuario.username
            contador = 1
            while Usuario.objects.filter(username=usuario.username).exists():
                contador += 1
                usuario.username = f"{base[:145]}{contador}"
            accion = "creado"
        else:
            accion = "actualizado"

        usuario.nombre = opciones["nombre"].strip() or usuario.nombre or email
        usuario.rol = Usuario.Rol.SUPERADMIN
        usuario.is_superuser = True
        usuario.is_staff = True
        usuario.is_active = True
        usuario.correo_verificado = True
        usuario.estado_registro = Usuario.EstadoRegistro.APROBADO
        # El dueño de la plataforma no pertenece a ninguna empresa: las ve todas.
        usuario.organizacion = None
        usuario.debe_cambiar_password = False
        usuario.set_password(password)
        usuario.save()

        self.stdout.write(self.style.SUCCESS(f"Superadmin {accion}: {email}"))
        if generada:
            self.stdout.write(self.style.WARNING(f"Contraseña generada: {password}"))
            self.stdout.write("Guárdala ahora: no se vuelve a mostrar.")
        self.stdout.write("Entra en /control/login/")
