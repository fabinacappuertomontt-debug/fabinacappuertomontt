# -*- coding: utf-8 -*-
"""En la mesa de trabajo, un indicador medible se actualiza con su medicion."""

import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import (
    IndicadorCatalogo,
    IndicadorResultado,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    ResultadoEsperado,
    TipoIndicador,
)

Usuario = get_user_model()


class MesaIndicadoresMediblesTests(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="DuocUC", slug="duoc-mesa")
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
        crear_fases_para_proyecto(self.proyecto)  # la etapa Validacion necesita sus fases
        obj = ObjetivoEspecifico.objects.create(proyecto=self.proyecto, descripcion="Validar", orden=1)
        res = ResultadoEsperado.objects.create(objetivo=obj, descripcion="Sensor validado", orden=1, trl_objetivo=4)
        self.medible = IndicadorResultado.objects.create(
            resultado=res, descripcion="Ensayos exitosos", tipo=TipoIndicador.NUMERICO,
            unidad="ensayos", meta_valor=Decimal("30"), linea_base=Decimal("0"), orden=1,
        )
        self.cualitativo = IndicadorResultado.objects.create(
            resultado=res, descripcion="Informe aprobado", tipo=TipoIndicador.CUALITATIVO, orden=2,
        )
        self.client.force_login(self.user)

    def actualizar(self, indicador, cuerpo):
        url = reverse("indicador_actualizar", kwargs={"pk": self.proyecto.pk, "indicador_id": indicador.pk})
        return self.client.post(url, data=json.dumps(cuerpo), content_type="application/json")

    def test_medible_se_actualiza_con_la_medicion(self):
        self.actualizar(self.medible, {"valor_medido": "30"})
        self.medible.refresh_from_db()
        self.assertEqual(self.medible.valor_medido, Decimal("30"))
        self.assertTrue(self.medible.cumplido)

    def test_medible_no_alcanza_la_meta_no_se_cumple(self):
        self.actualizar(self.medible, {"valor_medido": "29"})
        self.medible.refresh_from_db()
        self.assertFalse(self.medible.cumplido)

    def test_en_un_medible_no_manda_la_casilla(self):
        # Aunque el cliente mande cumplido=True, decide la medicion.
        self.actualizar(self.medible, {"valor_medido": "10", "cumplido": True})
        self.medible.refresh_from_db()
        self.assertFalse(self.medible.cumplido)

    def test_cualitativo_sigue_con_su_casilla(self):
        self.actualizar(self.cualitativo, {"cumplido": True, "valor_actual": "listo"})
        self.cualitativo.refresh_from_db()
        self.assertTrue(self.cualitativo.cumplido)

    def test_la_medicion_guardada_hace_subir_el_trl(self):
        self.actualizar(self.medible, {"valor_medido": "30"})
        self.actualizar(self.cualitativo, {"cumplido": True})
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_la_pantalla_muestra_campo_medido_para_medibles(self):
        url = reverse("etapa_trabajo", kwargs={"pk": self.proyecto.pk, "slug": "validacion"})
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'data-medible="1"')
        self.assertContains(respuesta, "Medido:")
