# -*- coding: utf-8 -*-
"""La puerta de cada nivel TRL: dato, prueba y juicio."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from proyectos.models import (
    Evidencia,
    IndicadorResultado,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    ResultadoEsperado,
    RevisionIAEtapa,
    TipoIndicador,
)
from proyectos.views import crear_fases_para_proyecto, sincronizar_trl_desde_resultados

Usuario = get_user_model()


class PuertaTrlTests(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="DuocUC", slug="duoc-puerta")
        self.user = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="x", organizacion=self.org,
        )
        self.proyecto = Proyecto.objects.create(
            nombre="Guante", organizacion=self.org,
            metodologia=Proyecto.Metodologia.TRL, tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3, trl_objetivo=5, fecha_inicio=date(2026, 1, 1),
            estado=Proyecto.Estado.EN_PROCESO, creador=self.user,
        )
        crear_fases_para_proyecto(self.proyecto)
        obj = ObjetivoEspecifico.objects.create(proyecto=self.proyecto, descripcion="Validar", orden=1)
        self.res4 = ResultadoEsperado.objects.create(objetivo=obj, descripcion="Calibrado", orden=1, trl_objetivo=4)
        self.ind4 = IndicadorResultado.objects.create(
            resultado=self.res4, descripcion="Ensayos", tipo=TipoIndicador.NUMERICO,
            unidad="ensayos", meta_valor=Decimal("30"), orden=1,
        )

    def cumplir_dato(self):
        self.ind4.valor_medido = Decimal("30")
        self.ind4.save()

    def subir_evidencia(self):
        Evidencia.objects.create(
            proyecto=self.proyecto, fase=self.proyecto.fases.get(trl=4),
            nombre="Informe", archivo="evidencias/x.pdf", usuario=self.user,
        )

    def aprobar_nivel(self):
        RevisionIAEtapa.objects.create(
            proyecto=self.proyecto, fase=self.proyecto.fases.get(trl=4),
            etapa_slug="validacion", etapa_nombre="Validacion",
            recomienda_avanzar=True, decision=RevisionIAEtapa.Decision.ACEPTADA,
        )

    # ── llaves individuales ─────────────────────────────────────────────

    def test_puerta_reporta_las_tres_llaves(self):
        puerta = self.proyecto.estado_puerta_trl(4)
        self.assertFalse(puerta["dato"])
        self.cumplir_dato()
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["dato"])

    def test_la_llave_prueba_se_pone_con_evidencia(self):
        self.assertFalse(self.proyecto.estado_puerta_trl(4)["prueba"])
        self.subir_evidencia()
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["prueba"])

    def test_la_llave_juicio_se_pone_al_aprobar(self):
        self.assertFalse(self.proyecto.estado_puerta_trl(4)["juicio"])
        self.aprobar_nivel()
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["juicio"])

    # ── el avance respeta lo que la organizacion exige ──────────────────

    def test_sin_exigencias_basta_el_dato(self):
        self.cumplir_dato()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_con_evidencia_exigida_el_dato_solo_no_alcanza(self):
        self.org.exige_evidencia_trl = True
        self.org.save()
        self.cumplir_dato()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 3)  # falta la prueba

        self.subir_evidencia()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_con_aprobacion_exigida_hacen_falta_las_tres_llaves(self):
        self.org.exige_aprobacion_trl = True
        self.org.save()
        self.cumplir_dato()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 3)  # falta el visto bueno

        self.aprobar_nivel()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.nivel_actual, 4)

    def test_la_puerta_abierta_refleja_lo_exigido(self):
        self.org.exige_aprobacion_trl = True
        self.org.save()
        self.cumplir_dato()
        puerta = self.proyecto.estado_puerta_trl(4)
        self.assertTrue(puerta["dato"])
        self.assertFalse(puerta["abierta"])  # falta la aprobacion

        self.aprobar_nivel()
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["abierta"])

    # ── el veredicto neto, no el boton apretado ─────────────────────────

    def revisar(self, recomienda, decision):
        RevisionIAEtapa.objects.create(
            proyecto=self.proyecto, fase=self.proyecto.fases.get(trl=4),
            etapa_slug="validacion", etapa_nombre="Validacion",
            recomienda_avanzar=recomienda, decision=decision,
        )

    def test_aceptar_un_no_avanzar_no_abre_la_puerta(self):
        # El bug que encontramos probando: aceptar "mantener en trabajo" no es
        # aprobar el avance, es estar de acuerdo en NO avanzar.
        self.revisar(recomienda=False, decision=RevisionIAEtapa.Decision.ACEPTADA)
        self.assertFalse(self.proyecto.estado_puerta_trl(4)["juicio"])

    def test_aceptar_un_si_avanzar_abre_la_puerta(self):
        self.revisar(recomienda=True, decision=RevisionIAEtapa.Decision.ACEPTADA)
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["juicio"])

    def test_el_responsable_puede_avanzar_pese_a_la_ia(self):
        # La IA dice que no, el responsable discrepa y avanza igual: es su
        # prerrogativa y queda registrada.
        self.revisar(recomienda=False, decision=RevisionIAEtapa.Decision.RECHAZADA)
        self.assertTrue(self.proyecto.estado_puerta_trl(4)["juicio"])

    def test_el_responsable_puede_frenar_pese_a_la_ia(self):
        self.revisar(recomienda=True, decision=RevisionIAEtapa.Decision.RECHAZADA)
        self.assertFalse(self.proyecto.estado_puerta_trl(4)["juicio"])

    def test_una_revision_pendiente_no_cuenta(self):
        self.revisar(recomienda=True, decision=RevisionIAEtapa.Decision.PENDIENTE)
        self.assertFalse(self.proyecto.estado_puerta_trl(4)["juicio"])
