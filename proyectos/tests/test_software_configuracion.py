from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from proyectos.models import Organizacion, SoftwareConfiguracion

User = get_user_model()

class SoftwareConfiguracionTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.org = Organizacion.objects.create(nombre='Org Test', slug='org-test')
        self.user = User.objects.create_user('tester', password='1234', organizacion=self.org)
        self.client.login(username='tester', password='1234')

    def test_requiere_login(self):
        self.client.logout()
        resp = self.client.get(reverse('software_lista'))
        self.assertEqual(resp.status_code, 302)

    def test_crear_software_sin_archivo(self):
        resp = self.client.post(reverse('software_crear'), {
            'nombre': 'OrcaSlicer',
            'tipo': 'slicer',
            'descripcion': 'Para imprimir piezas 3D',
            'icono': 'ti-printer',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SoftwareConfiguracion.objects.filter(nombre='OrcaSlicer').exists())

    def test_organizacion_se_asigna_desde_el_usuario(self):
        self.client.post(reverse('software_crear'), {
            'nombre': 'Fusion',
            'tipo': 'modelado',
            'descripcion': 'Modelado 3D',
        })
        sw = SoftwareConfiguracion.objects.get(nombre='Fusion')
        self.assertEqual(sw.organizacion, self.org)

    def test_creado_por_se_asigna(self):
        self.client.post(reverse('software_crear'), {
            'nombre': 'KiCad', 'tipo': 'electronica', 'descripcion': 'PCB',
        })
        sw = SoftwareConfiguracion.objects.get(nombre='KiCad')
        self.assertEqual(sw.creado_por, self.user)

    def test_context_processor_inyecta_lista(self):
        SoftwareConfiguracion.objects.create(nombre='Blender', tipo='modelado', organizacion=self.org)
        resp = self.client.get(reverse('software_lista'))
        self.assertIn('software_estandar_list', resp.context)

    def test_editar_software(self):
        sw = SoftwareConfiguracion.objects.create(nombre='Test', tipo='otro', creado_por=self.user, organizacion=self.org)
        resp = self.client.post(reverse('software_editar', kwargs={'pk': sw.pk}), {
            'nombre': 'Test Editado', 'tipo': 'otro', 'descripcion': '',
        })
        sw.refresh_from_db()
        self.assertEqual(sw.nombre, 'Test Editado')

    def test_eliminar_software(self):
        sw = SoftwareConfiguracion.objects.create(nombre='Borrar', tipo='otro', organizacion=self.org)
        resp = self.client.post(reverse('software_eliminar', kwargs={'pk': sw.pk}))
        self.assertFalse(SoftwareConfiguracion.objects.filter(pk=sw.pk).exists())
