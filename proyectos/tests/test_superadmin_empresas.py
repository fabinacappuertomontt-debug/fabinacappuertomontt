"""Panel privado del superadmin: alta, edicion y baja de empresas."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from proyectos.models import Organizacion, Proyecto

Usuario = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SuperadminEmpresasTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = Usuario.objects.create_user(
            username="dueno",
            email="dueno@plataforma.cl",
            password="password123",
            rol=Usuario.Rol.SUPERADMIN,
        )
        self.client.force_login(self.superadmin)

    def crear_empresa(self, **extra):
        datos = {
            "nombre": "DuocUC",
            "slug": "duoc-uc",
            "alias_login": "duoc",
            "color_principal": "#0033a0",
            "color_secundario": "#101828",
            "dominio_correo": "duoc.cl",
            "activa": "on",
            "encargado_nombre": "Ana Pérez",
            "encargado_email": "ana@duoc.cl",
        }
        datos.update(extra)
        return self.client.post(reverse("superadmin_organizacion_crear"), datos)

    # --- alta ---------------------------------------------------------------

    def test_crear_empresa_crea_encargado_y_envia_credenciales(self):
        respuesta = self.crear_empresa()

        organizacion = Organizacion.objects.get(slug="duoc-uc")
        self.assertRedirects(
            respuesta, reverse("superadmin_organizacion_detalle", args=[organizacion.pk])
        )

        encargado = organizacion.encargado
        self.assertIsNotNone(encargado)
        self.assertEqual(encargado.email, "ana@duoc.cl")
        self.assertEqual(encargado.rol, Usuario.Rol.ADMIN_ORGANIZACION)
        self.assertTrue(encargado.debe_cambiar_password)

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["ana@duoc.cl"])
        self.assertIn("DuocUC", correo.subject)
        # El correo lleva la marca de la empresa nueva, no la de otra.
        self.assertIn("#0033a0", correo.alternatives[0][0])

    def test_la_contrasena_temporal_sirve_para_entrar(self):
        self.crear_empresa()
        cuerpo = mail.outbox[0].body
        password = cuerpo.split("Contraseña temporal:")[1].split("\n")[0].strip()

        anonimo = Client()
        entro = anonimo.login(username="ana@duoc.cl", password=password)
        self.assertTrue(entro)

    def test_credenciales_se_muestran_una_sola_vez(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")
        url = reverse("superadmin_organizacion_detalle", args=[organizacion.pk])

        primera = self.client.get(url)
        self.assertIsNotNone(primera.context["credenciales"])

        segunda = self.client.get(url)
        self.assertIsNone(segunda.context["credenciales"])

    def test_alias_vacio_se_guarda_como_null_para_no_chocar(self):
        # alias_login es unique: si el vacio se guardara como "" la segunda empresa
        # sin alias chocaria con la primera.
        self.crear_empresa(alias_login="")
        self.crear_empresa(
            nombre="UACh", slug="uach", alias_login="", encargado_email="jefe@uach.cl"
        )
        creadas = Organizacion.objects.filter(slug__in=["duoc-uc", "uach"])
        self.assertEqual(creadas.count(), 2)
        self.assertEqual(creadas.filter(alias_login__isnull=True).count(), 2)

    # --- edicion ------------------------------------------------------------

    def test_editar_cambia_la_marca(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")

        self.client.post(
            reverse("superadmin_organizacion_editar", args=[organizacion.pk]),
            {
                "nombre": "Duoc UC Puerto Montt",
                "slug": "duoc-uc",
                "alias_login": "duoc",
                "color_principal": "#ff8800",
                "color_secundario": "#101828",
                "dominio_correo": "duoc.cl",
                "activa": "on",
            },
        )

        organizacion.refresh_from_db()
        self.assertEqual(organizacion.nombre, "Duoc UC Puerto Montt")
        self.assertEqual(organizacion.color_principal, "#ff8800")

    def test_desactivar_bloquea_el_acceso_de_la_empresa(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")

        self.client.post(reverse("superadmin_organizacion_estado", args=[organizacion.pk]))
        organizacion.refresh_from_db()
        self.assertFalse(organizacion.activa)

        anonimo = Client()
        respuesta = anonimo.get(reverse("organizacion_login", args=["duoc"]))
        self.assertEqual(respuesta.status_code, 404)

    def test_reset_genera_clave_nueva_y_anula_la_anterior(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")
        password_vieja = mail.outbox[0].body.split("Contraseña temporal:")[1].split("\n")[0].strip()
        mail.outbox.clear()

        self.client.post(
            reverse("superadmin_organizacion_reset_credenciales", args=[organizacion.pk])
        )

        self.assertEqual(len(mail.outbox), 1)
        password_nueva = mail.outbox[0].body.split("Contraseña temporal:")[1].split("\n")[0].strip()
        self.assertNotEqual(password_vieja, password_nueva)

        anonimo = Client()
        self.assertFalse(anonimo.login(username="ana@duoc.cl", password=password_vieja))
        self.assertTrue(anonimo.login(username="ana@duoc.cl", password=password_nueva))

    # --- baja ---------------------------------------------------------------

    def test_eliminar_exige_escribir_el_nombre_exacto(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")

        self.client.post(
            reverse("superadmin_organizacion_eliminar", args=[organizacion.pk]),
            {"confirmacion": "duoc"},
        )
        self.assertTrue(Organizacion.objects.filter(pk=organizacion.pk).exists())

        self.client.post(
            reverse("superadmin_organizacion_eliminar", args=[organizacion.pk]),
            {"confirmacion": "DuocUC"},
        )
        self.assertFalse(Organizacion.objects.filter(pk=organizacion.pk).exists())
        self.assertFalse(Usuario.objects.filter(email="ana@duoc.cl").exists())

    def test_eliminar_se_lleva_los_proyectos_de_la_empresa(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")
        Proyecto.objects.create(
            nombre="Proyecto Duoc",
            organizacion=organizacion,
            fecha_inicio=date(2026, 1, 1),
        )

        self.client.post(
            reverse("superadmin_organizacion_eliminar", args=[organizacion.pk]),
            {"confirmacion": "DuocUC"},
        )
        self.assertFalse(Proyecto.objects.filter(nombre="Proyecto Duoc").exists())

    # --- render -------------------------------------------------------------

    def test_todas_las_pantallas_del_panel_renderizan(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")

        urls = [
            reverse("superadmin_organizaciones"),
            reverse("superadmin_usuarios"),
            reverse("superadmin_estadisticas"),
            reverse("superadmin_organizacion_crear"),
            reverse("superadmin_organizacion_detalle", args=[organizacion.pk]),
            reverse("superadmin_organizacion_editar", args=[organizacion.pk]),
            reverse("superadmin_organizacion_eliminar", args=[organizacion.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    # --- permisos -----------------------------------------------------------

    def test_un_usuario_normal_no_entra_al_panel(self):
        normal = Usuario.objects.create_user(
            username="normal", email="normal@duoc.cl", password="password123"
        )
        cliente = Client()
        cliente.force_login(normal)

        for nombre in ["superadmin_organizaciones", "superadmin_usuarios", "superadmin_estadisticas"]:
            respuesta = cliente.get(reverse(nombre))
            self.assertRedirects(respuesta, reverse("superadmin_login"))

    def test_un_usuario_normal_no_puede_crear_ni_borrar_empresas(self):
        self.crear_empresa()
        organizacion = Organizacion.objects.get(slug="duoc-uc")

        normal = Usuario.objects.create_user(
            username="normal", email="normal@duoc.cl", password="password123"
        )
        cliente = Client()
        cliente.force_login(normal)

        cliente.post(
            reverse("superadmin_organizacion_eliminar", args=[organizacion.pk]),
            {"confirmacion": "DuocUC"},
        )
        self.assertTrue(Organizacion.objects.filter(pk=organizacion.pk).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CambioPasswordObligatorioTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(nombre="DuocUC", slug="duoc-uc")
        self.encargado = Usuario.objects.create_user(
            username="ana",
            email="ana@duoc.cl",
            password="temporal-123",
            organizacion=self.organizacion,
            debe_cambiar_password=True,
        )
        self.client = Client()
        self.client.force_login(self.encargado)

    def test_con_clave_temporal_todo_redirige_a_cambiarla(self):
        respuesta = self.client.get(reverse("proyecto_lista"))
        self.assertRedirects(respuesta, reverse("cambiar_password_obligatorio"))

    def test_al_definir_una_clave_propia_se_libera_el_paso(self):
        respuesta = self.client.post(
            reverse("cambiar_password_obligatorio"),
            {"new_password1": "MiClavePropia.2026", "new_password2": "MiClavePropia.2026"},
        )
        self.assertRedirects(respuesta, reverse("dashboard"))

        self.encargado.refresh_from_db()
        self.assertFalse(self.encargado.debe_cambiar_password)
        # La sesion sigue viva tras cambiar la clave.
        self.assertEqual(self.client.get(reverse("proyecto_lista")).status_code, 200)

    def test_la_pantalla_de_cambio_es_accesible_sin_bucle(self):
        respuesta = self.client.get(reverse("cambiar_password_obligatorio"))
        self.assertEqual(respuesta.status_code, 200)
