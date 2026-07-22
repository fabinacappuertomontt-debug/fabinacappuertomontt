"""El asistente de creacion de proyectos, paso a paso."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import (
    IndicadorCatalogo,
    ObjetivoEspecifico,
    Organizacion,
    Proyecto,
    TipoIndicador,
)

Usuario = get_user_model()


class WizardCreacionTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(nombre="DuocUC", slug="duoc-wizard")
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.organizacion, sede="puerto_montt",
            rol=Usuario.Rol.ADMIN_ORGANIZACION,
        )
        self.client.force_login(self.usuario)

    # ── paso 1 ────────────────────────────────────────────────────────────

    def datos_identidad(self, **extra):
        datos = {
            "nombre": "Sensor de riego",
            "descripcion": "Prototipo con sensores de humedad",
            "objetivo_principal": "Regar solo cuando el suelo lo necesita",
            "metodologia": Proyecto.Metodologia.TRL,
            "fecha_inicio": "2026-01-01",
            "responsables": [self.usuario.pk],
        }
        datos.update(extra)
        return datos

    def crear_borrador(self, **extra):
        self.client.post(reverse("wizard_inicio"), self.datos_identidad(**extra))
        return Proyecto.objects.get(nombre=extra.get("nombre", "Sensor de riego"))

    def test_el_primer_paso_crea_un_borrador(self):
        respuesta = self.client.post(reverse("wizard_inicio"), self.datos_identidad())

        proyecto = Proyecto.objects.get(nombre="Sensor de riego")
        self.assertEqual(proyecto.estado, Proyecto.Estado.BORRADOR)
        self.assertEqual(proyecto.creador, self.usuario)
        self.assertEqual(proyecto.organizacion, self.organizacion)
        self.assertRedirects(respuesta, reverse("wizard_paso", args=[proyecto.pk, 2]))

    def test_un_borrador_no_aparece_en_los_listados(self):
        self.crear_borrador()
        respuesta = self.client.get(reverse("proyecto_lista"))
        self.assertNotContains(respuesta, "Sensor de riego")

    def test_un_borrador_no_suma_en_los_contadores(self):
        self.crear_borrador()
        respuesta = self.client.get(reverse("dashboard"))
        self.assertEqual(respuesta.context["total_proyectos"], 0)

    # ── navegacion ────────────────────────────────────────────────────────

    def test_no_se_puede_saltar_a_un_paso_que_no_toca(self):
        proyecto = self.crear_borrador()
        respuesta = self.client.get(reverse("wizard_paso", args=[proyecto.pk, 5]))
        self.assertRedirects(respuesta, reverse("wizard_paso", args=[proyecto.pk, 2]))

    def test_se_puede_volver_a_un_paso_ya_completado(self):
        proyecto = self.crear_borrador()
        self.assertEqual(
            self.client.get(reverse("wizard_paso", args=[proyecto.pk, 1])).status_code, 200
        )

    def test_un_proyecto_simple_se_salta_el_paso_de_niveles(self):
        proyecto = self.crear_borrador(
            nombre="Taller de robotica", metodologia=Proyecto.Metodologia.SIMPLE
        )
        # Del paso 1 pasa directo al 3: no hay madurez TRL que declarar.
        self.assertEqual(proyecto.paso_wizard, 3)
        respuesta = self.client.get(reverse("wizard_paso", args=[proyecto.pk, 2]))
        self.assertEqual(respuesta.status_code, 302)

    def test_nadie_puede_seguir_el_borrador_de_otra_persona(self):
        proyecto = self.crear_borrador()
        otro = Usuario.objects.create_user(
            username="otro", email="otro@duoc.cl", password="password123",
            organizacion=self.organizacion,
        )
        self.client.force_login(otro)
        self.assertEqual(
            self.client.get(reverse("wizard_paso", args=[proyecto.pk, 1])).status_code, 404
        )

    # ── pasos 2 a 4 ───────────────────────────────────────────────────────

    def avanzar_hasta_resultados(self):
        proyecto = self.crear_borrador()
        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 2]),
            {"trl_inicial": 3, "trl_objetivo": 5},
        )
        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 3]),
            {"descripcion": "Validar el sensor en laboratorio"},
        )
        proyecto.refresh_from_db()
        return proyecto

    def test_el_nivel_objetivo_tiene_que_ser_mayor_que_el_inicial(self):
        proyecto = self.crear_borrador()
        respuesta = self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 2]),
            {"trl_inicial": 5, "trl_objetivo": 3},
        )
        self.assertContains(respuesta, "tiene que ser mayor")

    def test_los_objetivos_se_agregan_de_a_uno(self):
        proyecto = self.avanzar_hasta_resultados()
        self.assertEqual(proyecto.objetivos.count(), 1)

        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 3]),
            {"descripcion": "Probar en invernadero"},
        )
        self.assertEqual(proyecto.objetivos.count(), 2)

    def test_agregar_un_resultado_crea_su_indicador_en_el_proyecto(self):
        proyecto = self.avanzar_hasta_resultados()
        objetivo = proyecto.objetivos.first()

        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 4]),
            {
                "objetivo": objetivo.pk,
                "descripcion": "Sensor validado en laboratorio",
                "trl_objetivo": 4,
                "plazo_meses": 3,
                "plazo_dias": 0,
                "nombre": "Ensayos de humedad exitosos",
                "tipo": TipoIndicador.NUMERICO,
                "unidad": "ensayos",
                "meta_valor": "30",
                "linea_base": "0",
            },
        )

        resultado = objetivo.resultados.get()
        indicador = resultado.indicadores.get()
        self.assertEqual(indicador.meta_valor, 30)
        self.assertTrue(indicador.es_medible)
        # El indicador queda definido en el proyecto, disponible para reutilizar.
        self.assertEqual(proyecto.indicadores_definidos.count(), 1)

    def test_un_indicador_medible_exige_meta(self):
        proyecto = self.avanzar_hasta_resultados()
        respuesta = self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 4]),
            {
                "objetivo": proyecto.objetivos.first().pk,
                "descripcion": "Sensor validado",
                "trl_objetivo": 4,
                "plazo_meses": 3,
                "plazo_dias": 0,
                "nombre": "Ensayos exitosos",
                "tipo": TipoIndicador.NUMERICO,
                "unidad": "ensayos",
            },
        )
        self.assertContains(respuesta, "necesita una meta")

    def test_se_puede_reutilizar_un_indicador_ya_definido_en_el_proyecto(self):
        # Es lo que pidio el profesor: que exista antes de tener que asociarlo.
        proyecto = self.avanzar_hasta_resultados()
        objetivo = proyecto.objetivos.first()
        existente = IndicadorCatalogo.objects.create(
            proyecto=proyecto, nombre="Ensayos exitosos",
            tipo=TipoIndicador.NUMERICO, unidad="ensayos",
        )

        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 4]),
            {
                "objetivo": objetivo.pk,
                "descripcion": "Sensor validado",
                "trl_objetivo": 4,
                "plazo_meses": 2,
                "plazo_dias": 0,
                "existente": existente.pk,
                "meta_valor": "30",
            },
        )

        indicador = objetivo.resultados.get().indicadores.get()
        self.assertEqual(indicador.catalogo, existente)
        # No se duplico: sigue habiendo uno solo definido.
        self.assertEqual(proyecto.indicadores_definidos.count(), 1)

    # ── paso 5 ────────────────────────────────────────────────────────────

    def proyecto_completo(self):
        proyecto = self.avanzar_hasta_resultados()
        objetivo = proyecto.objetivos.first()
        for trl, nombre in [(4, "Ensayos en laboratorio"), (5, "Ensayos en terreno")]:
            self.client.post(
                reverse("wizard_paso", args=[proyecto.pk, 4]),
                {
                    "objetivo": objetivo.pk,
                    "descripcion": f"Resultado para TRL {trl}",
                    "trl_objetivo": trl,
                    "plazo_meses": trl,
                    "plazo_dias": 0,
                    "nombre": nombre,
                    "tipo": TipoIndicador.NUMERICO,
                    "unidad": "ensayos",
                    "meta_valor": "30",
                    "linea_base": "0",
                },
            )
        return proyecto

    def test_la_revision_avisa_si_falta_cubrir_un_nivel(self):
        proyecto = self.avanzar_hasta_resultados()
        objetivo = proyecto.objetivos.first()
        self.client.post(
            reverse("wizard_paso", args=[proyecto.pk, 4]),
            {
                "objetivo": objetivo.pk, "descripcion": "Solo cubre TRL 4",
                "trl_objetivo": 4, "plazo_meses": 2, "plazo_dias": 0,
                "nombre": "Ensayos", "tipo": TipoIndicador.NUMERICO,
                "unidad": "ensayos", "meta_valor": "30",
            },
        )
        respuesta = self.client.get(reverse("wizard_paso", args=[proyecto.pk, 5]))
        self.assertContains(respuesta, "TRL 5")
        self.assertFalse(respuesta.context["puede_crear"])

    def test_no_se_puede_publicar_un_proyecto_incompleto(self):
        proyecto = self.crear_borrador()
        proyecto.paso_wizard = 5
        proyecto.save(update_fields=["paso_wizard"])

        self.client.post(reverse("wizard_publicar", args=[proyecto.pk]))

        proyecto.refresh_from_db()
        self.assertEqual(proyecto.estado, Proyecto.Estado.BORRADOR)

    def test_publicar_convierte_el_borrador_en_proyecto(self):
        proyecto = self.proyecto_completo()
        respuesta = self.client.get(reverse("wizard_paso", args=[proyecto.pk, 5]))
        self.assertTrue(respuesta.context["puede_crear"])

        self.client.post(reverse("wizard_publicar", args=[proyecto.pk]))

        proyecto.refresh_from_db()
        self.assertEqual(proyecto.estado, Proyecto.Estado.EN_PROCESO)
        # Ya publicado, aparece en los listados.
        self.assertContains(self.client.get(reverse("proyecto_lista")), "Sensor de riego")

    def test_descartar_borra_el_borrador(self):
        proyecto = self.crear_borrador()
        self.client.post(reverse("wizard_descartar", args=[proyecto.pk]))
        self.assertFalse(Proyecto.objects.filter(pk=proyecto.pk).exists())

    def test_los_circulos_muestran_donde_va_el_usuario(self):
        proyecto = self.crear_borrador()
        respuesta = self.client.get(reverse("wizard_paso", args=[proyecto.pk, 2]))
        estados = {p["numero"]: p["estado"] for p in respuesta.context["pasos"]}

        self.assertEqual(estados[1], "completado")
        self.assertEqual(estados[2], "actual")
        self.assertEqual(estados[4], "bloqueado")
