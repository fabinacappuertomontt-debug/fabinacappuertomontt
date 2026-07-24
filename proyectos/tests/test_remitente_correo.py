# -*- coding: utf-8 -*-
"""El correo sale a nombre de la empresa, desde la casilla verificada."""

from django.core import mail
from django.test import TestCase, override_settings

from proyectos.models import Organizacion
from proyectos.views import enviar_correo_simple, remitente_de_organizacion

REMITENTE = "Plataforma TRL <avisos@ejemplo.com>"


@override_settings(DEFAULT_FROM_EMAIL=REMITENTE, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RemitenteCorreoTests(TestCase):
    def setUp(self):
        self.duoc = Organizacion.objects.create(nombre="DuocUC", slug="duoc-remitente")

    def test_lleva_el_nombre_de_la_empresa(self):
        self.assertEqual(remitente_de_organizacion(self.duoc), "DuocUC <avisos@ejemplo.com>")

    def test_sin_empresa_usa_la_marca_neutra(self):
        self.assertEqual(remitente_de_organizacion(None), "Plataforma TRL <avisos@ejemplo.com>")

    def test_la_direccion_no_cambia_nunca(self):
        # Solo se puede enviar desde la casilla verificada en el proveedor.
        for organizacion in (self.duoc, None):
            self.assertIn("<avisos@ejemplo.com>", remitente_de_organizacion(organizacion))

    def test_un_nombre_con_coma_se_escapa(self):
        rara = Organizacion.objects.create(nombre="Duoc, UC", slug="duoc-coma")
        self.assertEqual(remitente_de_organizacion(rara), '"Duoc, UC" <avisos@ejemplo.com>')

    def test_el_envio_real_usa_el_remitente_de_la_empresa(self):
        enviar_correo_simple("Hola", ["ana@duoc.cl"], "texto", organizacion=self.duoc)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "DuocUC <avisos@ejemplo.com>")

    def test_ninguna_empresa_recibe_el_nombre_de_otra(self):
        otra = Organizacion.objects.create(nombre="INACAP", slug="inacap-remitente")
        enviar_correo_simple("Hola", ["a@duoc.cl"], "t", organizacion=self.duoc)
        enviar_correo_simple("Hola", ["b@inacap.cl"], "t", organizacion=otra)
        self.assertNotIn("INACAP", mail.outbox[0].from_email)
        self.assertNotIn("DuocUC", mail.outbox[1].from_email)
