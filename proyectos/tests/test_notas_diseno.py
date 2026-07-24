# -*- coding: utf-8 -*-
"""Las notas de diseño son internas: sin sesion iniciada no se ven."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Organizacion

Usuario = get_user_model()


class NotasDisenoTests(TestCase):
    def setUp(self):
        self.url = reverse("notas_diseno")
        self.org = Organizacion.objects.create(nombre="DuocUC", slug="duoc-notas")

    def test_sin_sesion_manda_al_login(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.url)

    def test_con_sesion_se_muestra(self):
        usuario = Usuario.objects.create_user(
            username="victor", email="victor@duoc.cl", password="x",
            organizacion=self.org, rol=Usuario.Rol.PROFESOR,
        )
        self.client.force_login(usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Las cinco cosas que haría distinto")

    def test_cualquier_rol_con_cuenta_puede_leerlas(self):
        # El documento es para revisar el producto, no para administrarlo.
        usuario = Usuario.objects.create_user(
            username="ana", email="ana@duoc.cl", password="x",
            organizacion=self.org, rol=Usuario.Rol.INTEGRANTE,
        )
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(self.url).status_code, 200)
