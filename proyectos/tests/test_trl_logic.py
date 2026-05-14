from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from proyectos.models import IndicadorResultado, ObjetivoEspecifico, Proyecto, ResultadoEsperado, Tarea, Usuario
from proyectos.views import calcular_avance_madurez, crear_fases_para_proyecto, recalcular_avance_por_tareas, sincronizar_avance_simple_desde_objetivos, sincronizar_trl_desde_resultados


class TrlStressLogicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="trltester",
            password="secret123",
            email="trltester@example.com",
            nombre="TRL Tester",
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
