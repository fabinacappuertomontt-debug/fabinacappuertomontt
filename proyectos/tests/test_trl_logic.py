import json
from datetime import date, timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from proyectos.forms import EvidenciaForm, ProyectoForm, RegistroPublicoForm
from proyectos.gemini_service import analizar_borrador_trl
from proyectos.models import Area, FaseProyecto, IndicadorResultado, ObjetivoEspecifico, Organizacion, Proyecto, ResultadoEsperado, Tarea, Usuario
from proyectos.views import calcular_avance_madurez, construir_tablero_trl, crear_fases_para_proyecto, enviar_codigo_verificacion, enviar_solicitud_aprobacion_externa, generar_mesa_trabajo_inicial, notificar_creador_fase_completada, notificar_creador_proyecto, notificar_responsables_proyecto, recalcular_avance_por_tareas, sincronizar_avance_simple_desde_objetivos, sincronizar_trl_desde_resultados


TEST_PUBLIC_SITE_URL = "https://example.com"


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
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 1) + timedelta(days=180),
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
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 1) + timedelta(days=90),
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

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="")
    def test_mesa_inicial_por_reglas_crea_tareas_sin_avanzar_trl(self):
        proyecto = self.crear_proyecto_trl()
        self.crear_estructura_trl(proyecto)

        tareas_creadas = generar_mesa_trabajo_inicial(proyecto)
        sincronizar_trl_desde_resultados(proyecto)
        proyecto.refresh_from_db()

        self.assertGreater(tareas_creadas, 0)
        self.assertGreater(proyecto.tareas.count(), 0)
        self.assertTrue(any(fase.evidencias_sugeridas for fase in proyecto.fases.all()))
        self.assertEqual(proyecto.porcentaje_avance, 0)
        self.assertEqual(proyecto.nivel_actual, 3)

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="")
    def test_mesa_inicial_simple_no_crea_textos_trl(self):
        proyecto = self.crear_proyecto_simple()
        self.crear_estructura_simple(proyecto)

        generar_mesa_trabajo_inicial(proyecto)
        tablero = construir_tablero_trl(proyecto)
        textos = " ".join(
            [
                tarea.nombre + " " + tarea.descripcion
                for tarea in proyecto.tareas.all()
            ]
            + [
                " ".join(etapa["evidencias"])
                for etapa in tablero
            ]
        )

        self.assertNotIn("TRL", textos)
        self.assertGreater(proyecto.tareas.count(), 0)

    def test_fases_simples_actualizan_barra_de_avance(self):
        proyecto = self.crear_proyecto_simple()
        fase = proyecto.fases.order_by("trl").first()
        fase.estado = FaseProyecto.Estado.COMPLETADA
        fase.save(update_fields=["estado"])

        sincronizar_avance_simple_desde_objetivos(proyecto)
        proyecto.refresh_from_db()

        self.assertEqual(proyecto.fases_completadas_relevantes, 1)
        self.assertEqual(proyecto.total_fases_relevantes, 5)
        self.assertEqual(proyecto.porcentaje_avance, 20)
        self.assertEqual(calcular_avance_madurez(proyecto), 20)

    def test_formulario_evidencia_muestra_tareas_de_la_etapa(self):
        proyecto = self.crear_proyecto_simple()
        fase_1 = proyecto.fases.order_by("trl").first()
        fase_2 = proyecto.fases.order_by("trl")[1]
        tarea_1 = Tarea.objects.create(proyecto=proyecto, fase=fase_1, nombre="Levantar requisitos")
        tarea_2 = Tarea.objects.create(proyecto=proyecto, fase=fase_2, nombre="Planificar trabajo")

        form = EvidenciaForm(proyecto=proyecto, fase=fase_1)

        self.assertIn(tarea_1, form.fields["tarea"].queryset)
        self.assertNotIn(tarea_2, form.fields["tarea"].queryset)
        self.assertIn("Tarea 1", form.fields["tarea"].label_from_instance(tarea_1))

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
            for texto_trl in ["Proyecto con TRL", "TRL objetivo", "TRL inicial", "TRL a", "Asistente IA TRL"]:
                self.assertNotContains(response, texto_trl)

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
            for texto_trl in ["Proyecto con TRL", "TRL objetivo", "TRL inicial", "TRL a", "Asistente IA TRL"]:
                self.assertNotContains(detalle, texto_trl)
                self.assertNotContains(trabajo, texto_trl)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL=TEST_PUBLIC_SITE_URL,
    )
    def test_correo_de_proyecto_usa_url_publica_y_html_inacap(self):
        proyecto = self.crear_proyecto_trl()
        request = RequestFactory().get("/")

        enviado = notificar_responsables_proyecto(request, proyecto)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(TEST_PUBLIC_SITE_URL, correo.body)
        self.assertNotIn("127.0.0.1", correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")
        self.assertIn("INACAP", correo.alternatives[0][0])
        self.assertIn("Revisar proyecto", correo.alternatives[0][0])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL=TEST_PUBLIC_SITE_URL,
    )
    def test_correo_al_creador_resume_proyecto_y_responsables(self):
        proyecto = self.crear_proyecto_simple()
        proyecto.creador = self.usuario
        proyecto.objetivo_principal = "Gestionar un proyecto con responsables definidos."
        proyecto.save(update_fields=["creador", "objetivo_principal"])
        request = RequestFactory().get("/")

        enviado = notificar_creador_proyecto(request, proyecto)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(self.usuario.email, correo.to)
        self.assertIn("Proyecto creado", correo.subject)
        self.assertIn(proyecto.nombre, correo.body)
        self.assertIn("Responsables:", correo.body)
        self.assertIn(TEST_PUBLIC_SITE_URL, correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL=TEST_PUBLIC_SITE_URL,
    )
    def test_correo_al_creador_al_completar_etapa(self):
        proyecto = self.crear_proyecto_simple()
        proyecto.creador = self.usuario
        proyecto.save(update_fields=["creador"])
        fase = proyecto.fases.order_by("trl").first()
        fase.estado = fase.Estado.COMPLETADA
        fase.realizado = "Se completó el levantamiento y se cargaron evidencias."
        fase.save(update_fields=["estado", "realizado"])
        request = RequestFactory().get("/")

        enviado = notificar_creador_fase_completada(request, fase)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(self.usuario.email, correo.to)
        self.assertIn("Etapa completada", correo.subject)
        self.assertIn(fase.nombre, correo.body)
        self.assertIn("/etapas/", correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")


class AreaRegistroTests(TestCase):
    def setUp(self):
        self.organizacion, _ = Organizacion.objects.get_or_create(
            slug="fab-inacap-puerto-montt",
            defaults={
                "nombre": "FAB INACAP Puerto Montt",
            },
        )
        self.area_fab, _ = Area.objects.get_or_create(
            organizacion=self.organizacion,
            slug="fab-puerto-montt",
            defaults={
                "nombre": "FAB Puerto Montt",
                "correo_contacto": "fabinacappuertomontt@gmail.com",
                "es_fab": True,
            },
        )
        self.area_dae, _ = Area.objects.get_or_create(
            organizacion=self.organizacion,
            slug="direccion-vida-estudiantil-dae",
            defaults={
                "nombre": "Dirección de Vida Estudiantil (DAE)",
                "correo_contacto": "dae@inacap.cl",
            },
        )
        self.organizacion.nombre = "FAB INACAP Puerto Montt"
        self.organizacion.save(update_fields=["nombre"])
        self.area_fab.nombre = "FAB Puerto Montt"
        self.area_fab.save(update_fields=["nombre"])
        self.area_dae.nombre = "Dirección de Vida Estudiantil (DAE)"
        self.area_dae.save(update_fields=["nombre"])

    def test_registro_publico_asigna_area_y_organizacion(self):
        form = RegistroPublicoForm(data={
            "nombre": "Usuario DAE",
            "email": "usuario.dae@inacapmail.cl",
            "institucion": "",
            "rol": Usuario.Rol.ALUMNO,
            "area": str(self.area_dae.pk),
            "sede": "puerto_montt",
            "password1": "ClaveSegura123!",
            "password2": "ClaveSegura123!",
        })

        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()

        self.assertEqual(usuario.area, self.area_dae)
        self.assertEqual(usuario.organizacion, self.organizacion)
        self.assertEqual(usuario.estado_registro, Usuario.EstadoRegistro.VERIFICACION_CORREO)

    def test_proyecto_form_filtra_responsables_por_area(self):
        usuario_fab = Usuario.objects.create_user(
            username="fabuser",
            password="secret123",
            email="fab@example.com",
            nombre="Usuario FAB",
            organizacion=self.organizacion,
            area=self.area_fab,
        )
        Usuario.objects.create_user(
            username="daeuser",
            password="secret123",
            email="dae@example.com",
            nombre="Usuario DAE",
            organizacion=self.organizacion,
            area=self.area_dae,
        )

        form = ProyectoForm(sede="puerto_montt", organizacion=self.organizacion, area=self.area_fab)

        self.assertQuerySetEqual(
            form.fields["responsables"].queryset,
            [usuario_fab],
            transform=lambda usuario: usuario,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL=TEST_PUBLIC_SITE_URL,
        LAB_ADMIN_EMAILS={"admin@example.com"},
    )
    def test_correo_aprobacion_externa_usa_dominio_publico_y_html(self):
        usuario = Usuario.objects.create_user(
            username="externo",
            password="secret123",
            email="externo@gmail.com",
            nombre="Usuario Externo",
            institucion="Empresa externa",
            organizacion=self.organizacion,
            area=self.area_fab,
            estado_registro=Usuario.EstadoRegistro.PENDIENTE_APROBACION,
            is_active=False,
        )
        request = RequestFactory().get("/")

        enviado = enviar_solicitud_aprobacion_externa(request, usuario)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(TEST_PUBLIC_SITE_URL, correo.body)
        self.assertNotIn("127.0.0.1", correo.body)
        self.assertIn("Dominio oficial", correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")
        self.assertIn("Aprobar solicitud", correo.alternatives[0][0])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL=TEST_PUBLIC_SITE_URL,
    )
    def test_correo_verificacion_usa_dominio_publico_y_html(self):
        usuario = Usuario.objects.create_user(
            username="interno",
            password="secret123",
            email="interno@inacapmail.cl",
            nombre="Usuario Interno",
            organizacion=self.organizacion,
            area=self.area_fab,
            is_active=False,
        )
        request = RequestFactory().get("/")

        enviado = enviar_codigo_verificacion(request, usuario)

        self.assertTrue(enviado)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn(TEST_PUBLIC_SITE_URL, correo.body)
        self.assertNotIn("127.0.0.1", correo.body)
        self.assertEqual(correo.alternatives[0][1], "text/html")
        self.assertIn("Confirmar correo", correo.alternatives[0][0])


class GeminiAssistantTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="aiuser",
            password="secret123",
            email="aiuser@example.com",
            nombre="Usuario IA",
        )

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="")
    def test_servicio_gemini_sin_api_key_entrega_fallback(self):
        respuesta = analizar_borrador_trl({
            "nombre": "Proyecto sensor",
            "descripcion": "Prototipo para monitorear variables ambientales.",
        })

        self.assertEqual(respuesta["trl_estimado"], "")
        self.assertIn("GEMINI_API_KEY", respuesta["recomendaciones"])

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="clave-de-prueba", GROQ_MODEL="llama-test")
    @patch("proyectos.gemini_service.urllib.request.urlopen")
    def test_servicio_usa_groq_si_gemini_no_esta_configurado(self, urlopen_mock):
        contenido = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "trl_estimado": "TRL 3",
                            "justificacion": "Existe una prueba de concepto inicial.",
                            "recomendaciones": "Documentar la validacion experimental.",
                            "tareas_sugeridas": ["Registrar resultados de prueba"],
                        })
                    }
                }
            ]
        }
        urlopen_mock.return_value.__enter__.return_value.read.return_value = json.dumps(contenido).encode("utf-8")

        respuesta = analizar_borrador_trl({
            "nombre": "Proyecto sensor",
            "descripcion": "Prototipo inicial con sensores.",
        })

        self.assertEqual(respuesta["trl_estimado"], "TRL 3")
        self.assertEqual(respuesta["tareas_sugeridas"], ["Registrar resultados de prueba"])
        self.assertEqual(urlopen_mock.call_count, 1)

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="")
    def test_endpoint_asistente_ia_creacion_responde_json(self):
        self.client.force_login(self.usuario)
        response = self.client.post(
            reverse("proyecto_asistente_ia"),
            data=json.dumps({
                "metodologia": Proyecto.Metodologia.TRL,
                "nombre": "Proyecto sensor",
                "descripcion": "Prototipo para monitorear variables ambientales.",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("analisis", data)
        self.assertIn("GEMINI_API_KEY", data["analisis"]["recomendaciones"])

    @override_settings(GEMINI_API_KEY="", GROQ_API_KEY="")
    def test_vista_ia_proyecto_renderiza_fallback(self):
        proyecto = Proyecto.objects.create(
            nombre="Proyecto IA TRL",
            descripcion="Proyecto de prueba para analisis IA.",
            metodologia=Proyecto.Metodologia.TRL,
            tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3,
            trl_objetivo=6,
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=120),
            estado=Proyecto.Estado.EN_PROCESO,
        )
        proyecto.responsables.add(self.usuario)
        crear_fases_para_proyecto(proyecto)
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("proyecto_ia_trl", kwargs={"pk": proyecto.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asistente IA TRL")
        self.assertContains(response, "GEMINI_API_KEY")
