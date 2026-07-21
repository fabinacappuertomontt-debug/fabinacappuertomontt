"""Un nivel TRL se demuestra con evidencia, no se declara con una casilla."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from proyectos.models import (
    Evidencia,
    IndicadorResultado,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    ResultadoEsperado,
)
from proyectos.views import crear_fases_para_proyecto, sincronizar_trl_desde_resultados

Usuario = get_user_model()


class EvidenciaObligatoriaTrlTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(
            nombre="DuocUC", slug="duoc-evidencia", exige_evidencia_trl=True
        )
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.organizacion,
        )
        self.proyecto = Proyecto.objects.create(
            nombre="Sensor de riego",
            organizacion=self.organizacion,
            metodologia=Proyecto.Metodologia.TRL,
            tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3,
            trl_objetivo=5,
            fecha_inicio=date(2026, 1, 1),
        )
        crear_fases_para_proyecto(self.proyecto)

        objetivo = ObjetivoEspecifico.objects.create(
            proyecto=self.proyecto, descripcion="Validar el sensor", orden=1
        )
        self.resultado = ResultadoEsperado.objects.create(
            objetivo=objetivo,
            descripcion="Sensor validado en laboratorio",
            orden=1,
            trl_objetivo=4,
        )
        IndicadorResultado.objects.create(
            resultado=self.resultado, descripcion="Lecturas estables", orden=1, meta="100%"
        )

    def cumplir_indicadores(self):
        self.resultado.indicadores.update(cumplido=True, valor_actual="OK")

    def subir_evidencia(self, trl):
        return Evidencia.objects.create(
            proyecto=self.proyecto,
            fase=self.proyecto.fases.get(trl=trl),
            nombre=f"Informe de ensayo TRL {trl}",
            archivo=SimpleUploadedFile("informe.pdf", b"contenido"),
            usuario=self.usuario,
        )

    def test_marcar_los_indicadores_no_basta_para_subir_de_nivel(self):
        self.cumplir_indicadores()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()

        self.assertEqual(self.proyecto.nivel_actual, 3)
        self.assertEqual(self.proyecto.trl_bloqueado_por_falta_de_evidencia, 4)

    def test_con_la_evidencia_cargada_el_nivel_avanza(self):
        self.cumplir_indicadores()
        self.subir_evidencia(4)
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()

        self.assertEqual(self.proyecto.nivel_actual, 4)
        self.assertIsNone(self.proyecto.trl_bloqueado_por_falta_de_evidencia)

    def test_la_evidencia_de_otro_nivel_no_sirve(self):
        # Subir un informe del TRL 5 no acredita el TRL 4.
        self.cumplir_indicadores()
        self.subir_evidencia(5)
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()

        self.assertEqual(self.proyecto.nivel_actual, 3)

    def test_la_evidencia_sin_indicadores_cumplidos_tampoco_basta(self):
        self.subir_evidencia(4)
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()

        self.assertEqual(self.proyecto.nivel_actual, 3)
        # No se avisa de evidencia faltante porque el bloqueo real son los indicadores.
        self.assertIsNone(self.proyecto.trl_bloqueado_por_falta_de_evidencia)

    def test_si_la_empresa_no_lo_exige_el_comportamiento_no_cambia(self):
        self.organizacion.exige_evidencia_trl = False
        self.organizacion.save(update_fields=["exige_evidencia_trl"])

        self.cumplir_indicadores()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.refresh_from_db()

        self.assertEqual(self.proyecto.nivel_actual, 4)
        self.assertIsNone(self.proyecto.trl_bloqueado_por_falta_de_evidencia)

    def test_el_aviso_aparece_en_el_espacio_de_trabajo(self):
        self.cumplir_indicadores()
        sincronizar_trl_desde_resultados(self.proyecto)
        self.proyecto.responsables.add(self.usuario)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(f"/proyectos/{self.proyecto.pk}/trabajo/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "falta la evidencia")
