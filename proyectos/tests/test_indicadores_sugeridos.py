"""El indicador se elige del catalogo de la organizacion, no se inventa."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import IndicadorCatalogo, Organizacion, TipoIndicador

Usuario = get_user_model()


class CatalogoIndicadoresTests(TestCase):
    def setUp(self):
        self.duoc = Organizacion.objects.create(nombre="DuocUC", slug="duoc-ind")
        self.otra = Organizacion.objects.create(nombre="UACh", slug="uach-ind")
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.duoc,
        )
        self.client.force_login(self.usuario)

    def pedir(self, **parametros):
        return self.client.get(reverse("indicadores_sugeridos"), parametros).json()

    def nombres(self, datos):
        return [entrada["nombre"] for entrada in datos["usados"]]

    def test_ofrece_el_catalogo_de_la_organizacion(self):
        IndicadorCatalogo.objects.create(
            organizacion=self.duoc,
            nombre="Lecturas estables durante 72 horas",
            tipo=TipoIndicador.NUMERICO,
            unidad="horas",
        )
        datos = self.pedir(metodologia="trl")
        self.assertIn("Lecturas estables durante 72 horas", self.nombres(datos))

    def test_no_ofrece_el_catalogo_de_otra_organizacion(self):
        IndicadorCatalogo.objects.create(
            organizacion=self.otra, nombre="Indicador de la competencia"
        )
        datos = self.pedir(metodologia="trl")
        self.assertNotIn("Indicador de la competencia", self.nombres(datos))

    def test_informa_si_el_sistema_puede_medirlo_solo(self):
        IndicadorCatalogo.objects.create(
            organizacion=self.duoc, nombre="Ensayos exitosos",
            tipo=TipoIndicador.NUMERICO, unidad="ensayos",
        )
        IndicadorCatalogo.objects.create(
            organizacion=self.duoc, nombre="Informe aprobado",
            tipo=TipoIndicador.CUALITATIVO,
        )
        por_nombre = {e["nombre"]: e for e in self.pedir(metodologia="trl")["usados"]}

        self.assertTrue(por_nombre["Ensayos exitosos"]["medible"])
        self.assertEqual(por_nombre["Ensayos exitosos"]["unidad"], "ensayos")
        self.assertFalse(por_nombre["Informe aprobado"]["medible"])

    def test_no_ofrece_los_desactivados(self):
        IndicadorCatalogo.objects.create(
            organizacion=self.duoc, nombre="Indicador retirado", activo=False
        )
        self.assertNotIn("Indicador retirado", self.nombres(self.pedir(metodologia="trl")))

    def test_el_catalogo_por_nivel_se_acota_al_recorrido_del_proyecto(self):
        datos = self.pedir(metodologia="trl", trl_inicial="4", trl_objetivo="6")
        grupos = [g["grupo"] for g in datos["catalogo"]]
        self.assertEqual(len(grupos), 3)
        self.assertTrue(grupos[0].startswith("TRL 4"))
        self.assertTrue(grupos[-1].startswith("TRL 6"))

    def test_un_proyecto_simple_recibe_sugerencias_sin_trl(self):
        datos = self.pedir(metodologia="simple")
        self.assertEqual(len(datos["catalogo"]), 1)
        self.assertNotIn("TRL", datos["catalogo"][0]["grupo"])
        self.assertTrue(datos["catalogo"][0]["opciones"])

    def test_hay_que_estar_autenticado(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("indicadores_sugeridos")).status_code, 302
        )

    def test_el_formulario_trae_el_selector_del_catalogo(self):
        respuesta = self.client.get(reverse("proyecto_crear"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-indicator-catalogo")
        self.assertContains(respuesta, 'id="catalogo-indicadores"')
