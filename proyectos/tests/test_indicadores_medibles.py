"""El cumplimiento de un indicador se calcula con datos, no se declara."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

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


class IndicadorMedibleTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(nombre="DuocUC", slug="duoc-medible")
        self.proyecto = Proyecto.objects.create(
            nombre="Sensor de riego",
            organizacion=self.organizacion,
            metodologia=Proyecto.Metodologia.TRL,
            trl_inicial=3,
            trl_objetivo=5,
            fecha_inicio=date(2026, 1, 1),
        )
        objetivo = ObjetivoEspecifico.objects.create(
            proyecto=self.proyecto, descripcion="Validar el sensor", orden=1
        )
        self.resultado = ResultadoEsperado.objects.create(
            objetivo=objetivo, descripcion="Sensor validado", orden=1, trl_objetivo=4
        )
        self.catalogo = IndicadorCatalogo.objects.create(
            proyecto=self.proyecto,
            nombre="Ensayos de humedad exitosos",
            tipo=TipoIndicador.NUMERICO,
            unidad="ensayos",
            medio_verificacion="Bitacora de laboratorio",
        )

    def crear(self, **extra):
        datos = {
            "resultado": self.resultado,
            "descripcion": self.catalogo.nombre,
            "catalogo": self.catalogo,
            "tipo": TipoIndicador.NUMERICO,
            "unidad": "ensayos",
            "linea_base": Decimal("0"),
            "meta_valor": Decimal("30"),
            "orden": 1,
        }
        datos.update(extra)
        return IndicadorResultado.objects.create(**datos)

    def test_sin_medicion_no_se_da_por_cumplido(self):
        indicador = self.crear()
        self.assertFalse(indicador.cumplido)

    def test_alcanzar_la_meta_lo_da_por_cumplido_solo(self):
        indicador = self.crear(valor_medido=Decimal("30"))
        self.assertTrue(indicador.cumplido)

    def test_superar_la_meta_tambien_cuenta(self):
        indicador = self.crear(valor_medido=Decimal("45"))
        self.assertTrue(indicador.cumplido)

    def test_quedarse_corto_no_cuenta_aunque_se_marque_a_mano(self):
        # Este es el punto: la casilla deja de mandar cuando hay medicion.
        indicador = self.crear(valor_medido=Decimal("29"), cumplido=True)
        indicador.refresh_from_db()
        self.assertFalse(indicador.cumplido)

    def test_bajar_la_medicion_revierte_el_cumplimiento(self):
        indicador = self.crear(valor_medido=Decimal("30"))
        self.assertTrue(indicador.cumplido)

        indicador.valor_medido = Decimal("10")
        indicador.save()
        indicador.refresh_from_db()
        self.assertFalse(indicador.cumplido)

    def test_el_avance_se_expresa_entre_linea_base_y_meta(self):
        indicador = self.crear(linea_base=Decimal("10"), meta_valor=Decimal("30"), valor_medido=Decimal("20"))
        self.assertEqual(indicador.avance_porcentaje, 50)

    def test_el_avance_no_se_pasa_de_100_ni_baja_de_0(self):
        self.assertEqual(self.crear(valor_medido=Decimal("60")).avance_porcentaje, 100)
        self.assertEqual(
            self.crear(linea_base=Decimal("10"), valor_medido=Decimal("5")).avance_porcentaje, 0
        )

    def test_un_indicador_descriptivo_conserva_su_casilla(self):
        # Los que ya existian no se pueden calcular: ahi la persona es el
        # instrumento de medicion y la marca manual sigue mandando.
        indicador = IndicadorResultado.objects.create(
            resultado=self.resultado,
            descripcion="Informe aprobado por la contraparte",
            tipo=TipoIndicador.CUALITATIVO,
            orden=2,
            cumplido=True,
        )
        indicador.refresh_from_db()
        self.assertTrue(indicador.cumplido)
        self.assertFalse(indicador.es_medible)

    def test_guardar_con_update_fields_no_deja_el_cumplimiento_atrasado(self):
        indicador = self.crear()
        indicador.valor_medido = Decimal("30")
        indicador.save(update_fields=["valor_medido"])
        indicador.refresh_from_db()
        self.assertTrue(indicador.cumplido)

    def test_un_proyecto_no_admite_dos_indicadores_con_el_mismo_nombre(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IndicadorCatalogo.objects.create(
                    proyecto=self.proyecto,
                    nombre="Ensayos de humedad exitosos",
                )

    def test_dos_proyectos_pueden_tener_un_indicador_con_el_mismo_nombre(self):
        otro = Proyecto.objects.create(
            nombre="Otro proyecto",
            organizacion=self.organizacion,
            fecha_inicio=date(2026, 1, 1),
        )
        entrada = IndicadorCatalogo.objects.create(
            proyecto=otro, nombre="Ensayos de humedad exitosos"
        )
        self.assertNotEqual(entrada.pk, self.catalogo.pk)
