# -*- coding: utf-8 -*-
"""Bajar de nivel no se guarda a la primera: primero se pregunta."""

import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import (
    IndicadorResultado,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    ResultadoEsperado,
    TipoIndicador,
)

Usuario = get_user_model()


class RetrocesoTRLTests(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="DuocUC", slug="duoc-retroceso")
        self.user = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="x",
            organizacion=self.org, sede="puerto_montt",
            rol=Usuario.Rol.ADMIN_ORGANIZACION,
        )
        self.proyecto = Proyecto.objects.create(
            nombre="Sensor", organizacion=self.org, sede="puerto_montt",
            metodologia=Proyecto.Metodologia.TRL, tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3, trl_objetivo=5, fecha_inicio=date(2026, 1, 1),
            estado=Proyecto.Estado.EN_PROCESO, creador=self.user,
        )
        self.proyecto.responsables.add(self.user)
        from proyectos.views import crear_fases_para_proyecto
        crear_fases_para_proyecto(self.proyecto)
        obj = ObjetivoEspecifico.objects.create(proyecto=self.proyecto, descripcion="Validar", orden=1)
        res = ResultadoEsperado.objects.create(objetivo=obj, descripcion="Sensor validado", orden=1, trl_objetivo=4)
        self.medible = IndicadorResultado.objects.create(
            resultado=res, descripcion="Ensayos exitosos", tipo=TipoIndicador.NUMERICO,
            unidad="ensayos", meta_valor=Decimal("30"), linea_base=Decimal("0"), orden=1,
        )
        self.client.force_login(self.user)

        # Punto de partida: el indicador se cumple y el proyecto llega a TRL 4.
        self.actualizar(self.medible, {"valor_medido": "30"})
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def actualizar(self, indicador, cuerpo):
        url = reverse("indicador_actualizar", kwargs={"pk": self.proyecto.pk, "indicador_id": indicador.pk})
        return self.client.post(url, data=json.dumps(cuerpo), content_type="application/json")

    def test_bajar_de_nivel_pide_confirmacion(self):
        respuesta = self.actualizar(self.medible, {"valor_medido": "10"})
        datos = respuesta.json()
        self.assertFalse(datos["ok"])
        self.assertTrue(datos["requiere_confirmacion"])
        self.assertEqual(datos["nivel_antes"], 4)
        self.assertEqual(datos["nivel_despues"], 3)

    def test_sin_confirmar_no_se_guarda_nada(self):
        self.actualizar(self.medible, {"valor_medido": "10"})
        self.medible.refresh_from_db()
        self.proyecto.refresh_from_db()
        self.assertEqual(self.medible.valor_medido, Decimal("30"))  # la medicion anterior sigue
        self.assertTrue(self.medible.cumplido)
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_al_confirmar_el_nivel_baja(self):
        respuesta = self.actualizar(self.medible, {"valor_medido": "10", "confirmar_retroceso": True})
        self.assertTrue(respuesta.json()["ok"])
        self.medible.refresh_from_db()
        self.proyecto.refresh_from_db()
        self.assertEqual(self.medible.valor_medido, Decimal("10"))
        self.assertFalse(self.medible.cumplido)
        self.assertEqual(self.proyecto.nivel_actual, 3)

    def test_subir_o_quedarse_igual_no_pregunta(self):
        # Mejorar la medicion sin cambiar de nivel se guarda directo.
        respuesta = self.actualizar(self.medible, {"valor_medido": "45"})
        datos = respuesta.json()
        self.assertTrue(datos["ok"])
        self.assertNotIn("requiere_confirmacion", datos)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_un_proyecto_simple_nunca_pregunta(self):
        simple = Proyecto.objects.create(
            nombre="Taller", organizacion=self.org, sede="puerto_montt",
            metodologia=Proyecto.Metodologia.SIMPLE, fecha_inicio=date(2026, 1, 1),
            estado=Proyecto.Estado.EN_PROCESO, creador=self.user,
        )
        simple.responsables.add(self.user)
        obj = ObjetivoEspecifico.objects.create(proyecto=simple, descripcion="Hacer", orden=1)
        res = ResultadoEsperado.objects.create(objetivo=obj, descripcion="Hecho", orden=1, trl_objetivo=1)
        ind = IndicadorResultado.objects.create(
            resultado=res, descripcion="Listo", tipo=TipoIndicador.BINARIO, orden=1,
        )
        url = reverse("indicador_actualizar", kwargs={"pk": simple.pk, "indicador_id": ind.pk})
        self.client.post(url, data=json.dumps({"cumplido": True}), content_type="application/json")
        respuesta = self.client.post(url, data=json.dumps({"cumplido": False}), content_type="application/json")
        self.assertTrue(respuesta.json()["ok"])
