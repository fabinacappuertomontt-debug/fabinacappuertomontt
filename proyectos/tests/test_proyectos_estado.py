from datetime import date
from django.test import TestCase
from django.urls import reverse
from proyectos.models import Organizacion, Proyecto, Usuario

class ProyectoEstadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organizacion.objects.create(nombre="Inacap Test")
        
        # Creador / Líder
        cls.creador = Usuario.objects.create_user(
            username="jefe_proyecto",
            password="password123",
            email="jefe@inacap.cl",
            nombre="Jefe de Proyecto",
            rol=Usuario.Rol.LIDER,
            organizacion=cls.org
        )
        
        # Miembro / Responsable normal
        cls.responsable = Usuario.objects.create_user(
            username="responsable_proyecto",
            password="password123",
            email="resp@inacap.cl",
            nombre="Responsable Proyecto",
            rol=Usuario.Rol.INTEGRANTE,
            organizacion=cls.org
        )

        # Admin de laboratorio
        cls.admin_lab = Usuario.objects.create_user(
            username="admin_lab",
            password="password123",
            email="admin@inacap.cl",
            nombre="Admin Lab",
            rol=Usuario.Rol.ADMINISTRADOR,
            organizacion=cls.org
        )

        # Usuario externo o no responsable
        cls.otro_usuario = Usuario.objects.create_user(
            username="otro_user",
            password="password123",
            email="otro@inacap.cl",
            nombre="Otro Usuario",
            rol=Usuario.Rol.INTEGRANTE,
            organizacion=cls.org
        )

    def setUp(self):
        # Creamos un proyecto finalizado para probar la reactivación
        self.proyecto = Proyecto.objects.create(
            nombre="Proyecto Terminado de Prueba",
            descripcion="Descripción del proyecto terminado.",
            creador=self.creador,
            estado=Proyecto.Estado.FINALIZADO,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 6, 1),
            organizacion=self.org
        )
        self.proyecto.responsables.add(self.creador, self.responsable)

    def test_proyecto_list_view_separates_active_and_finished(self):
        # Creamos un proyecto activo
        proyecto_activo = Proyecto.objects.create(
            nombre="Proyecto Activo",
            descripcion="Descripción activo.",
            creador=self.creador,
            estado=Proyecto.Estado.EN_PROCESO,
            fecha_inicio=date(2026, 1, 1),
            organizacion=self.org
        )
        
        self.client.login(username="jefe_proyecto", password="password123")
        response = self.client.get(reverse("proyecto_lista"))
        self.assertEqual(response.status_code, 200)
        
        # Deben estar cargados en el contexto
        activos = response.context["proyectos_activos"]
        terminados = response.context["proyectos_terminados"]
        
        self.assertIn(proyecto_activo, activos)
        self.assertNotIn(self.proyecto, activos)
        
        self.assertIn(self.proyecto, terminados)
        self.assertNotIn(proyecto_activo, terminados)

    def test_creador_can_reactivate_project(self):
        self.client.login(username="jefe_proyecto", password="password123")
        url = reverse("proyecto_estado", args=[self.proyecto.pk])
        
        # GET debería cargar el formulario
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST para reactivar (cambiar a EN_PROCESO)
        response = self.client.post(url, {
            "estado": Proyecto.Estado.EN_PROCESO,
            "porcentaje_avance": 80
        })
        self.assertEqual(response.status_code, 302) # Redirección
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.estado, Proyecto.Estado.EN_PROCESO)

    def test_admin_can_reactivate_project(self):
        self.client.login(username="admin_lab", password="password123")
        url = reverse("proyecto_estado", args=[self.proyecto.pk])
        
        # GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST
        response = self.client.post(url, {
            "estado": Proyecto.Estado.EN_PROCESO,
            "porcentaje_avance": 70
        })
        self.assertEqual(response.status_code, 302)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.estado, Proyecto.Estado.EN_PROCESO)

    def test_non_owner_member_cannot_reactivate_project(self):
        # Responsable es miembro pero no creador/admin
        self.client.login(username="responsable_proyecto", password="password123")
        url = reverse("proyecto_estado", args=[self.proyecto.pk])
        
        # GET debería redirigir con error
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Intentar POST
        response = self.client.post(url, {
            "estado": Proyecto.Estado.EN_PROCESO,
            "porcentaje_avance": 90
        })
        self.assertEqual(response.status_code, 302)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.estado, Proyecto.Estado.FINALIZADO) # Sigue FINALIZADO

    def test_unrelated_user_cannot_reactivate_project(self):
        self.client.login(username="otro_user", password="password123")
        url = reverse("proyecto_estado", args=[self.proyecto.pk])
        
        # GET retorna 404 ya que no pertenece al proyecto y no es admin
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        
        # POST retorna 404
        response = self.client.post(url, {
            "estado": Proyecto.Estado.EN_PROCESO,
            "porcentaje_avance": 90
        })
        self.assertEqual(response.status_code, 404)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.estado, Proyecto.Estado.FINALIZADO)
