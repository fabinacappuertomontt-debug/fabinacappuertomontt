"""Verifica que una organizacion no pueda ver ni tocar los datos de otra."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from proyectos.models import (
    CarpetaArchivos,
    ItemInventario,
    Organizacion,
    SoftwareConfiguracion,
)

Usuario = get_user_model()


class AislamientoOrganizacionTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.inacap = Organizacion.objects.create(nombre="INACAP", slug="inacap-test")
        self.duoc = Organizacion.objects.create(nombre="DuocUC", slug="duoc-test")

        self.usuario_duoc = Usuario.objects.create_user(
            username="ana@duoc.cl",
            email="ana@duoc.cl",
            password="password123",
            organizacion=self.duoc,
            sede="puerto_montt",
        )

        self.software_inacap = SoftwareConfiguracion.objects.create(
            nombre="OrcaSlicer INACAP",
            tipo="slicer",
            organizacion=self.inacap,
        )
        self.carpeta_inacap = CarpetaArchivos.objects.create(
            software=self.software_inacap,
            nombre="Perfiles internos",
        )
        self.item_inacap = ItemInventario.objects.create(
            nombre="Filamento PLA INACAP",
            tipo="filamento",
            area="impresion_3d",
            sede="puerto_montt",
            organizacion=self.inacap,
            cantidad=5,
            unidad="kg",
        )

        self.client.force_login(self.usuario_duoc)

    def test_lista_de_software_no_muestra_otra_organizacion(self):
        respuesta = self.client.get(reverse("software_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "OrcaSlicer INACAP")

    def test_menu_global_no_filtra_software_de_otra_organizacion(self):
        respuesta = self.client.get(reverse("software_lista"))
        self.assertNotIn(
            self.software_inacap,
            list(respuesta.context["software_estandar_list"]),
        )

    def test_no_puede_abrir_software_de_otra_organizacion(self):
        respuesta = self.client.get(
            reverse("software_detalle", kwargs={"pk": self.software_inacap.pk})
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_puede_eliminar_software_de_otra_organizacion(self):
        respuesta = self.client.post(
            reverse("software_eliminar", kwargs={"pk": self.software_inacap.pk})
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(
            SoftwareConfiguracion.objects.filter(pk=self.software_inacap.pk).exists()
        )

    def test_no_puede_eliminar_carpeta_de_otra_organizacion(self):
        respuesta = self.client.post(
            reverse("carpeta_eliminar", kwargs={"pk": self.carpeta_inacap.pk})
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(CarpetaArchivos.objects.filter(pk=self.carpeta_inacap.pk).exists())

    def test_inventario_no_muestra_items_de_otra_organizacion(self):
        respuesta = self.client.get(reverse("inventario_lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Filamento PLA INACAP")

    def test_usuario_sin_organizacion_no_ve_datos_de_nadie(self):
        huerfano = Usuario.objects.create_user(
            username="sin-org@test.cl",
            email="sin-org@test.cl",
            password="password123",
            sede="puerto_montt",
        )
        self.client.force_login(huerfano)
        respuesta = self.client.get(reverse("software_lista"))
        self.assertEqual(list(respuesta.context["items"]), [])
