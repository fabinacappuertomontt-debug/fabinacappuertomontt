from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from proyectos.models import (
    Organizacion, Proyecto, FaseProyecto, Tarea, GrupoChat, Notificacion, MensajePrivado, Evidencia
)

Usuario = get_user_model()

class NotificationAndGroupChatTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organizacion.objects.create(nombre="Test Org", slug="test-org")
        
        # Creator
        self.creator = Usuario.objects.create_user(
            username="creator@test.cl",
            email="creator@test.cl",
            password="password123",
            sede="puerto_montt",
            organizacion=self.org,
            rol="profesor"
        )
        # Another user in the same sede
        self.user_sede = Usuario.objects.create_user(
            username="sede_user@test.cl",
            email="sede_user@test.cl",
            password="password123",
            sede="puerto_montt",
            organizacion=self.org,
            rol="profesor"
        )
        # Another user in a different sede
        self.user_diff_sede = Usuario.objects.create_user(
            username="diff_user@test.cl",
            email="diff_user@test.cl",
            password="password123",
            sede="santiago",
            organizacion=self.org,
            rol="profesor"
        )
        
        self.client.login(username="creator@test.cl", password="password123")

    def test_project_creation_triggers_notifications(self):
        # Create a project
        # El formulario de una sola pagina sigue existiendo; "proyecto_crear"
        # ahora es el wizard, asi que esta prueba apunta al clasico.
        url = reverse("proyecto_crear_clasico")
        post_data = {
            "nombre": "Proyecto de Prueba",
            "descripcion": "Descripción del proyecto de prueba.",
            "tipo_proyecto": "innovacion",
            "metodologia": "trl",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-06-30",
            "trl_inicial": 3,
            "trl_objetivo": 7,
            "responsables": [self.creator.pk, self.user_sede.pk],
        }
        response = self.client.post(url, post_data)
        # If response code is 200, let's print form errors to debug
        if response.status_code == 200:
            print("Form errors (project creation):", response.context.get("form").errors if "form" in response.context else "No form in context")
        self.assertEqual(response.status_code, 302)
        
        # Verify notifications
        # 1. user_sede (same sede) should get "Nuevo Proyecto Creado" and "Asignación a Proyecto"
        notifications_user_sede = Notificacion.objects.filter(usuario=self.user_sede)
        self.assertTrue(notifications_user_sede.filter(titulo="Nuevo Proyecto Creado").exists())
        self.assertTrue(notifications_user_sede.filter(titulo="Asignación a Proyecto").exists())
        
        # 2. user_diff_sede (different sede) should NOT get a notification
        notifications_diff = Notificacion.objects.filter(usuario=self.user_diff_sede)
        self.assertEqual(notifications_diff.count(), 0)

    def test_project_update_triggers_notifications(self):
        # Create a project first
        proyecto = Proyecto.objects.create(
            nombre="Proyecto Inicial",
            descripcion="Desc",
            tipo_proyecto="innovacion",
            metodologia="simple",
            sede="puerto_montt",
            organizacion=self.org,
            creador=self.creator,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 6, 30)
        )
        proyecto.responsables.add(self.creator)
        
        # Update project responsibles via client
        url = reverse("proyecto_editar", args=[proyecto.pk])
        post_data = {
            "nombre": "Proyecto Inicial Modificado",
            "descripcion": "Desc",
            "tipo_proyecto": "innovacion",
            "metodologia": "simple",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-06-30",
            "responsables": [self.creator.pk, self.user_sede.pk],
        }
        response = self.client.post(url, post_data)
        if response.status_code == 200:
            print("Form errors (project update):", response.context.get("form").errors if "form" in response.context else "No form in context")
        self.assertEqual(response.status_code, 302)
        
        # user_sede was newly assigned, they should get a notification
        self.assertTrue(Notificacion.objects.filter(
            usuario=self.user_sede,
            titulo="Asignación a Proyecto"
        ).exists())

    def test_task_assignment_triggers_notifications(self):
        proyecto = Proyecto.objects.create(
            nombre="Proyecto Tarea",
            descripcion="Desc",
            tipo_proyecto="innovacion",
            metodologia="simple",
            sede="puerto_montt",
            organizacion=self.org,
            creador=self.creator,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 6, 30)
        )
        proyecto.responsables.add(self.creator)
        
        # Create a task assigned to user_sede
        url = reverse("tarea_crear", args=[proyecto.pk])
        post_data = {
            "nombre": "Tarea de Prueba",
            "descripcion": "Detalle de tarea",
            "responsable": self.user_sede.pk,
            "estado": "pendiente"
        }
        response = self.client.post(url, post_data)
        if response.status_code == 200:
            print("Form errors (task assignment):", response.context.get("form").errors if "form" in response.context else "No form in context")
        self.assertEqual(response.status_code, 302)
        
        # Verify notification
        self.assertTrue(Notificacion.objects.filter(
            usuario=self.user_sede,
            titulo="Nueva Tarea Asignada"
        ).exists())

    def test_stage_completion_triggers_notifications(self):
        proyecto = Proyecto.objects.create(
            nombre="Proyecto Fase",
            descripcion="Desc",
            tipo_proyecto="innovacion",
            metodologia="simple",
            sede="puerto_montt",
            organizacion=self.org,
            creador=self.creator,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 6, 30)
        )
        proyecto.responsables.add(self.creator)
        
        # Create a fase
        fase = FaseProyecto.objects.create(
            proyecto=proyecto,
            nombre="Etapa 1",
            trl=1,
            estado=FaseProyecto.Estado.EN_PROCESO
        )
        
        # Create an evidence for the phase so FaseProyectoForm.clean() doesn't fail
        Evidencia.objects.create(
            proyecto=proyecto,
            fase=fase,
            nombre="Evidencia Test",
            usuario=self.creator
        )
        
        # Update stage to COMPLETED
        url = reverse("fase_detalle", args=[fase.pk])
        post_data = {
            "nombre": "Etapa 1 Modificada",
            "estado": FaseProyecto.Estado.COMPLETADA,
            "realizado": "Trabajo realizado"
        }
        response = self.client.post(url, post_data)
        if response.status_code == 200:
            print("Form errors (stage completion):", response.context.get("form").errors if "form" in response.context else "No form in context")
        self.assertEqual(response.status_code, 302)
        
        # The project creator (self.creator) should get a notification
        self.assertTrue(Notificacion.objects.filter(
            usuario=self.creator,
            titulo="Etapa Completada"
        ).exists())

    def test_mark_notifications_as_read(self):
        # Create some notifications
        Notificacion.objects.create(
            usuario=self.creator,
            titulo="Notif 1",
            mensaje="Mensaje 1"
        )
        Notificacion.objects.create(
            usuario=self.creator,
            titulo="Notif 2",
            mensaje="Mensaje 2"
        )
        
        # Ensure they are unread
        self.assertEqual(Notificacion.objects.filter(usuario=self.creator, leido=False).count(), 2)
        
        # Call mark as read endpoint
        url = reverse("marcar_notificaciones_leidas")
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        
        # Verify they are read
        self.assertEqual(Notificacion.objects.filter(usuario=self.creator, leido=False).count(), 0)

    def test_group_chat_workflow(self):
        # Create a group
        url_create_group = reverse("chat_grupo_nuevo")
        post_data = {
            "nombre": "Grupo de Innovación",
            "miembros": [self.creator.pk, self.user_sede.pk]
        }
        response = self.client.post(url_create_group, post_data)
        self.assertEqual(response.status_code, 302) # Redirect to chat_grupo
        
        # Verify Group exists
        grupo = GrupoChat.objects.get(nombre="Grupo de Innovación")
        self.assertEqual(grupo.nombre, "Grupo de Innovación")
        self.assertIn(self.user_sede, grupo.miembros.all())
        
        # Send a message in the group
        url_chat_group = reverse("chat_grupo", args=[grupo.pk])
        message_data = {
            "texto": "Hola grupo!"
        }
        response = self.client.post(url_chat_group, message_data)
        self.assertEqual(response.status_code, 302) # redirect back to chat_grupo
        
        # Verify message created and link to group
        self.assertTrue(MensajePrivado.objects.filter(
            remitente=self.creator,
            grupo=grupo,
            texto="Hola grupo!"
        ).exists())
        
        # Verify notification created for group member user_sede
        self.assertTrue(Notificacion.objects.filter(
            usuario=self.user_sede,
            titulo=f"Mensaje en grupo: {grupo.nombre}"
        ).exists())

    def test_group_chat_permission_denied(self):
        # Create a group where self.user_diff_sede is NOT a member
        grupo = GrupoChat.objects.create(
            nombre="Grupo Secreto",
            creado_por=self.creator,
            sede="puerto_montt"
        )
        grupo.miembros.add(self.creator)
        
        # Login as diff sede user (not a member)
        self.client.login(username="diff_user@test.cl", password="password123")
        url = reverse("chat_grupo", args=[grupo.pk])
        response = self.client.get(url)
        # Should raise 404
        self.assertEqual(response.status_code, 404)

    def test_login_redirect_for_authenticated_users(self):
        # We are already logged in as self.creator
        url = reverse("login")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Test organizacion_login redirect
        url_org = reverse("organizacion_login", args=["inacap"])
        response_org = self.client.get(url_org)
        self.assertEqual(response_org.status_code, 302)

    def test_descargar_proyecto_pdf(self):
        # Create a project in puerto_montt (same sede as self.creator)
        proyecto = Proyecto.objects.create(
            nombre="Proyecto PDF Test",
            descripcion="Prueba de generación de PDF.",
            tipo_proyecto="innovacion",
            metodologia="trl",
            sede="puerto_montt",
            organizacion=self.org,
            creador=self.creator,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 6, 30)
        )
        
        # Test 1: Authorized download - "todo" mode
        url = reverse("proyecto_descargar_pdf", args=[proyecto.pk])
        response = self.client.get(url + "?modo=todo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertIn("attachment; filename=", response.headers.get("Content-Disposition", ""))
        self.assertIn(f"proyecto_{proyecto.pk}_todo.pdf", response.headers.get("Content-Disposition", ""))

        # Test 2: Authorized download - "evidencias_objetivos" mode
        response = self.client.get(url + "?modo=evidencias_objetivos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertIn(f"proyecto_{proyecto.pk}_evidencias_objetivos.pdf", response.headers.get("Content-Disposition", ""))

        # Test 3: Authorized download - "imagenes" mode
        response = self.client.get(url + "?modo=imagenes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "application/pdf")
        self.assertIn(f"proyecto_{proyecto.pk}_imagenes.pdf", response.headers.get("Content-Disposition", ""))

        # Test 4: Unauthorized download - User from different sede (santiago)
        self.client.login(username="diff_user@test.cl", password="password123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
