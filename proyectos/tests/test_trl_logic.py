import json
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from proyectos.forms import ProyectoForm
from proyectos.models import IndicadorResultado, ObjetivoEspecifico, Proyecto, ResultadoEsperado, Tarea, Usuario
from proyectos.views import calcular_avance_madurez, construir_tablero_trl, crear_fases_para_proyecto, notificar_responsables_proyecto, recalcular_avance_por_tareas, sincronizar_avance_simple_desde_objetivos, sincronizar_trl_desde_resultados


class TrlStressLogicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="logictester",
            password="secret123",
            email="logictester@example.com",
            nombre="Usuario Tester",
            sede=Usuario._meta.get_field("sede").default,
        )

    def crear_proyecto_trl(self):
        proyecto = Proyecto.objects.create(
            nombre="Proyecto TRL de prueba",
            descripcion="Proyecto para validar la logica de madurez.",
            metodologia=Proyecto.Metodologia.TRL,
            tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3,
            trl_objetivo=7,
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=180),
            estado=Proyecto.Estado.EN_PROCESO,
        )
        proyecto.responsables.add(self.usuario)
        crear_fases_para_proyecto(proyecto)
        return proyecto

    def crear_proyecto_simple(self):
        proyecto = Proyecto.objects.create(
            nombre="Proyecto simple de prueba",
            descripcion="Proyecto simple para validar avance por objetivos.",
            metodologia=Proyecto.Metodologia.SIMPLE,
            tipo_proyecto=Proyecto.TipoProyecto.GENERAL,
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=90),
            estado=Proyecto.Estado.EN_PROCESO,
        )
        proyecto.responsables.add(self.usuario)
        crear_fases_para_proyecto(proyecto)
        return proyecto

    def crear_estructura_trl(self, proyecto):
        objetivo_1 = ObjetivoEspecifico.objects.create(
            proyecto=proyecto,
            descripcion="Diseñar y validar la base del sistema.",
            orden=1,
        )
        objetivo_2 = ObjetivoEspecifico.objects.create(
            proyecto=proyecto,
            descripcion="Probar el prototipo en contexto real.",
            orden=2,
        )
        resultados = []
        for orden, trl, descripcion in [
            (1, 4, "Validar sensores en laboratorio."),
            (2, 5, "Validar lectura en entorno relevante."),
            (3, 6, "Demostrar prototipo en entorno relevante."),
            (4, 7, "Probar prototipo en entorno real."),
        ]:
            objetivo = objetivo_1 if trl <= 5 else objetivo_2
            resultado = ResultadoEsperado.objects.create(
                objetivo=objetivo,
                descripcion=descripcion,
                orden=orden,
                trl_objetivo=trl,
                plazo_meses=orden,
                plazo_dias=15,
                estado=ResultadoEsperado.Estado.PENDIENTE,
            )
            IndicadorResultado.objects.create(
                resultado=resultado,
                descripcion=f"Indicador principal TRL {trl}",
                orden=1,
                meta="100%",
                valor_actual="",
                cumplido=False,
            )
            IndicadorResultado.objects.create(
                resultado=resultado,
                descripcion=f"Evidencia tecnica TRL {trl}",
                orden=2,
                meta="2 pruebas",
                valor_actual="",
                cumplido=False,
            )
            resultados.append(resultado)
        return resultados

    def crear_estructura_simple(self, proyecto, cantidad=3):
        objetivo = ObjetivoEspecifico.objects.create(
            proyecto=proyecto,
            descripcion="Organizar el seguimiento operativo del proyecto.",
            orden=1,
        )
        resultados = []
        for orden in range(1, cantidad + 1):
            resultado = ResultadoEsperado.objects.create(
                objetivo=objetivo,
                descripcion=f"Resultado operativo {orden} validado.",
                orden=orden,
                trl_objetivo=1,
                plazo_meses=orden,
                plazo_dias=0,
                estado=ResultadoEsperado.Estado.PENDIENTE,
            )
            IndicadorResultado.objects.create(
                resultado=resultado,
                descripcion=f"Indicador operativo {orden}",
                orden=1,
                meta="Cumplimiento documentado",
                valor_actual="",
                cumplido=False,
            )
            resultados.append(resultado)
        return resultados

    def cumplir_resultado(self, resultado):
        resultado.indicadores.update(cumplido=True, valor_actual="OK")

    def test_trl_se_mueve_en_secuencia_por_resultados_e_indicadores(self):
        proyecto = self.crear_proyecto_trl()
        resultados = self.crear_estructura_trl(proyecto)

        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nivel_actual, 3)
        self.assertEqual(calcular_avance_madurez(proyecto), 0)

        self.cumplir_resultado(resultados[0])
        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nivel_actual, 4)
        self.assertEqual(calcular_avance_madurez(proyecto), 25)

        self.cumplir_resultado(resultados[1])
        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nivel_actual, 5)
        self.assertEqual(calcular_avance_madurez(proyecto), 50)

    def test_no_sube_trl_si_faltan_indicadores_aunque_resultado_diga_cumplido(self):
        proyecto = self.crear_proyecto_trl()
        resultado = self.crear_estructura_trl(proyecto)[0]

        indicador = resultado.indicadores.first()
        indicador.cumplido = True
        indicador.save(update_fields=["cumplido"])

        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.nivel_actual, 3)
        self.assertEqual(proyecto.fases.get(trl=4).estado, "en_proceso")

    def test_no_salta_trl_si_un_nivel_intermedio_sigue_pendiente(self):
        proyecto = self.crear_proyecto_trl()
        resultados = self.crear_estructura_trl(proyecto)

        self.cumplir_resultado(resultados[0])
        self.cumplir_resultado(resultados[2])
        self.cumplir_resultado(resultados[3])
        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.nivel_actual, 4)
        self.assertEqual(proyecto.fases.get(trl=6).estado, "en_proceso")
        self.assertEqual(proyecto.fases.get(trl=5).estado, "pendiente")

    def test_plazo_de_resultado_se_calcula_desde_fecha_inicio(self):
        proyecto = self.crear_proyecto_trl()
        resultado = self.crear_estructura_trl(proyecto)[0]

        self.assertEqual(resultado.fecha_objetivo, proyecto.fecha_inicio + timedelta(days=46))

    def test_tareas_en_masa_no_suben_trl_sin_resultados_cumplidos(self):
        proyecto = self.crear_proyecto_trl()
        self.crear_estructura_trl(proyecto)
        fases = list(proyecto.fases.filter(trl__gte=3, trl__lte=7).order_by("trl"))

        tareas = []
        for indice in range(120):
            tareas.append(
                Tarea(
                    proyecto=proyecto,
                    fase=fases[indice % len(fases)],
                    nombre=f"Tarea {indice + 1}",
                    descripcion="Carga masiva para estresar el seguimiento.",
                    estado=Tarea.Estado.COMPLETADA,
                    responsable=self.usuario,
                )
            )
        Tarea.objects.bulk_create(tareas)

        recalcular_avance_por_tareas(proyecto)
        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.porcentaje_avance, 0)
        self.assertEqual(proyecto.nivel_actual, 3)
        self.assertEqual(proyecto.estado, Proyecto.Estado.EN_PROCESO)

    def test_trl_inicial_no_aparece_como_etapa_completada_sin_resultados(self):
        proyecto = self.crear_proyecto_trl()
        proyecto.trl_objetivo = 6
        proyecto.save(update_fields=["trl_objetivo"])
        self.crear_estructura_trl(proyecto)

        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()
        tablero = construir_tablero_trl(proyecto)

        self.assertEqual(proyecto.nivel_actual, 3)
        self.assertEqual(proyecto.porcentaje_avance, 0)
        self.assertEqual(calcular_avance_madurez(proyecto), 0)
        self.assertFalse(any(etapa["inicio"] <= 3 <= etapa["fin"] for etapa in tablero))
        self.assertFalse(any(etapa["completa"] for etapa in tablero))
        self.assertTrue(any(etapa["inicio"] == 4 for etapa in tablero))

    def test_proyecto_trl_no_termina_hasta_alcanzar_el_ultimo_nivel(self):
        proyecto = self.crear_proyecto_trl()
        resultados = self.crear_estructura_trl(proyecto)

        for resultado in resultados[:3]:
            self.cumplir_resultado(resultado)

        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.nivel_actual, 6)
        self.assertEqual(proyecto.porcentaje_avance, 75)
        self.assertEqual(proyecto.estado, Proyecto.Estado.EN_PROCESO)

    def test_proyecto_trl_solo_termina_cuando_alcanza_el_trl_objetivo(self):
        proyecto = self.crear_proyecto_trl()
        resultados = self.crear_estructura_trl(proyecto)

        for resultado in resultados:
            self.cumplir_resultado(resultado)

        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.nivel_actual, 7)
        self.assertEqual(proyecto.porcentaje_avance, 100)
        self.assertEqual(proyecto.estado, Proyecto.Estado.FINALIZADO)

    def test_fase_trl_se_marca_en_proceso_si_hay_resultado_movido_pero_no_cumplido(self):
        proyecto = self.crear_proyecto_trl()
        resultado = self.crear_estructura_trl(proyecto)[0]
        indicador = resultado.indicadores.first()
        indicador.valor_actual = "avance parcial"
        indicador.save(update_fields=["valor_actual"])

        sincronizar_trl_desde_resultados(proyecto)

        self.assertEqual(proyecto.fases.get(trl=4).estado, "en_proceso")

    def test_proyecto_simple_sube_avance_por_objetivos_cumplidos(self):
        proyecto = self.crear_proyecto_simple()
        resultados = self.crear_estructura_trl(proyecto)

        self.cumplir_resultado(resultados[0])
        self.cumplir_resultado(resultados[1])
        sincronizar_avance_simple_desde_objetivos(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.porcentaje_avance, 50)
        self.assertEqual(calcular_avance_madurez(proyecto), 50)

    def test_tareas_no_pisan_avance_de_proyecto_simple(self):
        proyecto = self.crear_proyecto_simple()
        resultados = self.crear_estructura_trl(proyecto)
        self.cumplir_resultado(resultados[0])
        sincronizar_avance_simple_desde_objetivos(proyecto)

        Tarea.objects.create(
            proyecto=proyecto,
            fase=proyecto.fases.first(),
            nombre="Tarea simple",
            descripcion="No debe dominar el avance del proyecto simple.",
            estado=Tarea.Estado.COMPLETADA,
            responsable=self.usuario,
        )
        recalcular_avance_por_tareas(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.porcentaje_avance, 25)

    def test_formulario_simple_guarda_objetivos_sin_exigir_trl(self):
        payload = [{
            "descripcion": "Definir flujo de registro de avances.",
            "resultados": [{
                "descripcion": "Flujo simple validado con usuarios.",
                "meses": 1,
                "dias": 10,
                "observaciones": "Prueba funcional sin madurez tecnologica.",
                "indicadores": [{
                    "descripcion": "Usuarios pueden registrar avances.",
                    "meta": "Formulario probado",
                    "valor_actual": "",
                    "cumplido": False,
                }],
            }],
        }]
        form = ProyectoForm(data={
            "metodologia": Proyecto.Metodologia.SIMPLE,
            "nombre": "Proyecto simple desde formulario",
            "descripcion": "Seguimiento simple por objetivos.",
            "objetivo_principal": "Validar seguimiento simple.",
            "objetivo_especifico": json.dumps(payload),
            "resultados_esperados": json.dumps(payload),
            "indicadores": json.dumps(payload),
            "fecha_inicio": timezone.localdate().isoformat(),
            "fecha_fin": timezone.localdate().isoformat(),
            "responsables": [str(self.usuario.pk)],
        }, sede=self.usuario.sede)

        self.assertTrue(form.is_valid(), form.errors)
        proyecto = form.save()
        resultado = ResultadoEsperado.objects.get(objetivo__proyecto=proyecto)

        self.assertEqual(proyecto.metodologia, Proyecto.Metodologia.SIMPLE)
        self.assertIsNone(proyecto.trl_inicial)
        self.assertIsNone(proyecto.trl_objetivo)
        self.assertEqual(resultado.trl_objetivo, 1)
        self.assertEqual(proyecto.objetivos.count(), 1)

    def test_formulario_trl_guarda_objetivo_con_trl_desde_el_primer_resultado(self):
        payload = [{
            "descripcion": "Validar modulo tecnico del sistema.",
            "resultados": [{
                "descripcion": "Prototipo validado en laboratorio.",
                "trl": 4,
                "meses": 2,
                "dias": 0,
                "observaciones": "Resultado asociado a madurez tecnologica.",
                "indicadores": [{
                    "descripcion": "Prueba tecnica aprobada.",
                    "meta": "Evidencia de laboratorio",
                    "valor_actual": "",
                    "cumplido": False,
                }],
            }],
        }]
        form = ProyectoForm(data={
            "metodologia": Proyecto.Metodologia.TRL,
            "nombre": "Proyecto TRL desde formulario",
            "descripcion": "Seguimiento con madurez tecnologica.",
            "objetivo_principal": "Validar avance TRL.",
            "objetivo_especifico": json.dumps(payload),
            "resultados_esperados": json.dumps(payload),
            "indicadores": json.dumps(payload),
            "trl_inicial": 3,
            "trl_objetivo": 6,
            "fecha_inicio": timezone.localdate().isoformat(),
            "fecha_fin": timezone.localdate().isoformat(),
            "responsables": [str(self.usuario.pk)],
        }, sede=self.usuario.sede)

        self.assertTrue(form.is_valid(), form.errors)
        proyecto = form.save()
        resultado = ResultadoEsperado.objects.get(objetivo__proyecto=proyecto)

        self.assertEqual(proyecto.metodologia, Proyecto.Metodologia.TRL)
        self.assertEqual(proyecto.trl_inicial, 3)
        self.assertEqual(proyecto.trl_objetivo, 6)
        self.assertEqual(resultado.trl_objetivo, 4)

    def test_vistas_de_proyecto_simple_no_muestran_texto_trl(self):
        proyecto = self.crear_proyecto_simple()
        self.crear_estructura_simple(proyecto)
        self.client.force_login(self.usuario)

        for url_name in ["proyecto_detalle", "proyecto_trabajo"]:
            response = self.client.get(reverse(url_name, kwargs={"pk": proyecto.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "TRL")

    def test_estres_proyectos_simples_no_se_presentan_como_trl(self):
        self.client.force_login(self.usuario)
        for indice in range(25):
            proyecto = self.crear_proyecto_simple()
            proyecto.nombre = f"Proyecto simple operativo {indice + 1}"
            proyecto.save(update_fields=["nombre"])
            resultados = self.crear_estructura_simple(proyecto, cantidad=5)
            for resultado in resultados[:2]:
                self.cumplir_resultado(resultado)
            sincronizar_avance_simple_desde_objetivos(proyecto)

            detalle = self.client.get(reverse("proyecto_detalle", kwargs={"pk": proyecto.pk}))
            trabajo = self.client.get(reverse("proyecto_trabajo", kwargs={"pk": proyecto.pk}))

            self.assertEqual(detalle.status_code, 200)
            self.assertEqual(trabajo.status_code, 200)
            self.assertNotContains(detalle, "TRL")
            self.assertNotContains(trabajo, "TRL")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL="https://trl-fablab-h8dxgse0b2dadjc9.eastus-01.azurewebsites.net",
    )
    def test_correo_de_proyecto_usa_url_publica_y_html_inacap(self):
        proyecto = self.crear_proyecto_trl()
        request = RequestFactory().get("/")

        enviado = notificar_responsables_proyecto(request, proyecto)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn("https://trl-fablab-h8dxgse0b2dadjc9.eastus-01.azurewebsites.net", correo.body)
        self.assertNotIn("127.0.0.1", correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")
        self.assertIn("INACAP", correo.alternatives[0][0])
        self.assertIn("Revisar proyecto", correo.alternatives[0][0])
