from django.test import TestCase, Client
from django.urls import reverse
from proyectos.models import SoftwareConfiguracion, CarpetaArchivos
from django.contrib.auth import get_user_model

User = get_user_model()

class CarpetasArchivosTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')
        
        self.sw = SoftwareConfiguracion.objects.create(
            nombre="Test Software",
            creado_por=self.user
        )
        
    def test_carpetas_y_archivos_creacion(self):
        carpeta = CarpetaArchivos.objects.create(
            software=self.sw,
            nombre="Documentos",
            creado_por=self.user
        )
        
        self.assertEqual(carpeta.nombre, "Documentos")
        self.assertEqual(self.sw.carpetas.count(), 1)
        
        url = reverse('software_detalle', args=[self.sw.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos")
