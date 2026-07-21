"""El entorno de validacion es lo que separa un nivel TRL del siguiente."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.forms import FaseProyectoForm
from proyectos.models import ENTORNO_POR_TRL, Organizacion, Proyecto
from proyectos.views import crear_fases_para_proyecto

Usuario = get_user_model()


class EntornoValidacionTests(TestCase):
    def setUp(self):
        self.organizacion = Organizacion.objects.create(nombre="DuocUC", slug="duoc-entorno")
        self.usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="password123",
            organizacion=self.organizacion, rol=Usuario.Rol.ADMIN_ORGANIZACION,
        )
        self.proyecto = Proyecto.objects.create(
            nombre="Sensor de riego",
            organizacion=self.organizacion,
            metodologia=Proyecto.Metodologia.TRL,
            tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
            trl_inicial=3,
            trl_objetivo=7,
            fecha_inicio=date(2026, 1, 1),
        )
        crear_fases_para_proyecto(self.proyecto)
        self.proyecto.responsables.add(self.usuario)
        self.client.force_login(self.usuario)

    def test_cada_nivel_muestra_el_entorno_que_exige(self):
        # Es la definicion oficial: laboratorio, entorno relevante, entorno real.
        self.assertIn("Laboratorio", ENTORNO_POR_TRL[4])
        self.assertIn("relevante", ENTORNO_POR_TRL[5])
        self.assertIn("relevante", ENTORNO_POR_TRL[6])
        self.assertIn("real", ENTORNO_POR_TRL[7])

    def test_el_formulario_explica_el_entorno_del_nivel_que_se_edita(self):
        fase = self.proyecto.fases.get(trl=7)
        form = FaseProyectoForm(instance=fase)
        self.assertEqual(form.fields["entorno_validacion"].help_text, ENTORNO_POR_TRL[7])

    def test_los_niveles_sin_entorno_definido_no_piden_el_campo(self):
        # En TRL 1-3 todavia no hay nada que validar en terreno.
        fase = self.proyecto.fases.get(trl=3)
        form = FaseProyectoForm(instance=fase)
        self.assertNotIn("entorno_validacion", form.fields)

    def test_la_etapa_avisa_cuando_falta_declarar_el_entorno(self):
        # TRL 4 es la primera fase desbloqueada: el proyecto parte en TRL 3.
        fase = self.proyecto.fases.get(trl=4)
        respuesta = self.client.get(reverse("fase_detalle", kwargs={"pk": fase.pk}))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Falta declarar el entorno de validación")
        self.assertContains(respuesta, "condiciones controladas")

    def test_el_entorno_declarado_se_guarda_y_se_muestra(self):
        fase = self.proyecto.fases.get(trl=4)
        self.client.post(
            reverse("fase_detalle", kwargs={"pk": fase.pk}),
            {
                "estado": fase.estado,
                "realizado": "Instalado en el invernadero del cliente.",
                "entorno_validacion": "Invernadero comercial en Puerto Varas, 3 meses de operacion.",
            },
        )

        fase.refresh_from_db()
        self.assertIn("Invernadero comercial", fase.entorno_validacion)

        respuesta = self.client.get(reverse("fase_detalle", kwargs={"pk": fase.pk}))
        self.assertContains(respuesta, "Invernadero comercial")
