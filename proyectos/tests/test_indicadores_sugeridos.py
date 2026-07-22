"""Los indicadores que se ofrecen son los del propio proyecto."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import IndicadorCatalogo, Organizacion, Proyecto, TipoIndicador

Usuario = get_user_model()


class IndicadoresDelProyectoTests(TestCase):
    def setUp(self):
        self.duoc = Organizacion.objects.create(nombre="DuocUC", slug="duoc-ind")
        self.otra = Organizacion.objects.create(nombre="UACh", slug="uach-ind")
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.duoc, rol=Usuario.Rol.ADMIN_ORGANIZACION,
        )
        self.proyecto = self.crear_proyecto("Sensor de riego", self.duoc)
        self.client.force_login(self.usuario)

    def crear_proyecto(self, nombre, organizacion):
        return Proyecto.objects.create(
            nombre=nombre,
            organizacion=organizacion,
            sede="puerto_montt",
            fecha_inicio=date(2026, 1, 1),
        )

    def pedir(self, **parametros):
        return self.client.get(reverse("indicadores_sugeridos"), parametros).json()

    def nombres(self, datos):
        return [entrada["nombre"] for entrada in datos["usados"]]

    def test_ofrece_los_indicadores_definidos_en_ese_proyecto(self):
        IndicadorCatalogo.objects.create(
            proyecto=self.proyecto,
            nombre="Lecturas estables durante 72 horas",
            tipo=TipoIndicador.NUMERICO,
            unidad="horas",
        )
        datos = self.pedir(metodologia="trl", proyecto=self.proyecto.pk)
        self.assertIn("Lecturas estables durante 72 horas", self.nombres(datos))

    def test_no_ofrece_los_de_otro_proyecto_de_la_misma_empresa(self):
        # Es el punto del profesor: un indicador responde al resultado que mide,
        # asi que los de otro proyecto casi nunca aplican.
        otro = self.crear_proyecto("Proyecto distinto", self.duoc)
        IndicadorCatalogo.objects.create(proyecto=otro, nombre="Indicador de otro proyecto")

        datos = self.pedir(metodologia="trl", proyecto=self.proyecto.pk)
        self.assertNotIn("Indicador de otro proyecto", self.nombres(datos))

    def test_no_se_pueden_ver_los_de_un_proyecto_de_otra_empresa(self):
        ajeno = self.crear_proyecto("Proyecto ajeno", self.otra)
        IndicadorCatalogo.objects.create(proyecto=ajeno, nombre="Indicador de la competencia")

        datos = self.pedir(metodologia="trl", proyecto=ajeno.pk)
        self.assertEqual(datos["usados"], [])

    def test_sin_proyecto_no_devuelve_indicadores_propios(self):
        # Al empezar a crear todavia no hay proyecto: solo van las sugerencias.
        datos = self.pedir(metodologia="trl")
        self.assertEqual(datos["usados"], [])
        self.assertTrue(datos["catalogo"])

    def test_informa_si_el_sistema_puede_medirlo_solo(self):
        IndicadorCatalogo.objects.create(
            proyecto=self.proyecto, nombre="Ensayos exitosos",
            tipo=TipoIndicador.NUMERICO, unidad="ensayos",
        )
        IndicadorCatalogo.objects.create(
            proyecto=self.proyecto, nombre="Informe aprobado",
            tipo=TipoIndicador.CUALITATIVO,
        )
        por_nombre = {
            e["nombre"]: e
            for e in self.pedir(metodologia="trl", proyecto=self.proyecto.pk)["usados"]
        }
        self.assertTrue(por_nombre["Ensayos exitosos"]["medible"])
        self.assertEqual(por_nombre["Ensayos exitosos"]["unidad"], "ensayos")
        self.assertFalse(por_nombre["Informe aprobado"]["medible"])

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

    def test_hay_que_estar_autenticado(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("indicadores_sugeridos")).status_code, 302
        )
