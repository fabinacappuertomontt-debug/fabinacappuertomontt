"""El indicador se elige de una lista, no se inventa en un campo vacio."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import (
    IndicadorResultado,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    ResultadoEsperado,
)

Usuario = get_user_model()


class IndicadoresSugeridosTests(TestCase):
    def setUp(self):
        self.duoc = Organizacion.objects.create(nombre="DuocUC", slug="duoc-ind")
        self.otra = Organizacion.objects.create(nombre="UACh", slug="uach-ind")
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.duoc,
        )
        self.client.force_login(self.usuario)

    def crear_indicador(self, organizacion, descripcion, veces=1):
        proyecto = Proyecto.objects.create(
            nombre=f"Proyecto {descripcion[:12]}",
            organizacion=organizacion,
            fecha_inicio=date(2026, 1, 1),
        )
        objetivo = ObjetivoEspecifico.objects.create(
            proyecto=proyecto, descripcion="Objetivo", orden=1
        )
        resultado = ResultadoEsperado.objects.create(
            objetivo=objetivo, descripcion="Resultado", orden=1, trl_objetivo=4
        )
        for i in range(veces):
            IndicadorResultado.objects.create(
                resultado=resultado, descripcion=descripcion, orden=i + 1, meta="100%"
            )

    def pedir(self, **parametros):
        return self.client.get(reverse("indicadores_sugeridos"), parametros).json()

    def test_ofrece_los_indicadores_que_la_organizacion_ya_uso(self):
        self.crear_indicador(self.duoc, "Lecturas estables durante 72 horas")
        datos = self.pedir(metodologia="trl")
        self.assertIn("Lecturas estables durante 72 horas", datos["usados"])

    def test_no_ofrece_los_de_otra_organizacion(self):
        self.crear_indicador(self.otra, "Indicador secreto de la competencia")
        datos = self.pedir(metodologia="trl")
        self.assertNotIn("Indicador secreto de la competencia", datos["usados"])

    def test_los_mas_repetidos_van_primero(self):
        # Un indicador reutilizado es el que de verdad permite comparar proyectos.
        self.crear_indicador(self.duoc, "Indicador usado una sola vez")
        self.crear_indicador(self.duoc, "Indicador reutilizado varias veces", veces=4)
        datos = self.pedir(metodologia="trl")
        self.assertEqual(datos["usados"][0], "Indicador reutilizado varias veces")

    def test_descarta_los_valores_basura(self):
        # En los datos reales hay indicadores que dicen solo "1".
        self.crear_indicador(self.duoc, "1")
        self.crear_indicador(self.duoc, "x" * 400)
        datos = self.pedir(metodologia="trl")
        self.assertNotIn("1", datos["usados"])
        self.assertFalse(any(len(texto) > 160 for texto in datos["usados"]))

    def test_el_catalogo_se_acota_al_recorrido_trl_del_proyecto(self):
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
        respuesta = self.client.get(reverse("indicadores_sugeridos"))
        self.assertEqual(respuesta.status_code, 302)

    def test_el_formulario_incluye_la_lista_para_elegir(self):
        respuesta = self.client.get(reverse("proyecto_crear"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="catalogo-indicadores"')
