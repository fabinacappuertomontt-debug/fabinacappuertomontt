from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from proyectos.models import ItemInventario, MovimientoStock, Organizacion

Usuario = get_user_model()

class InventarioTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organizacion.objects.create(nombre="Test Org", slug="test-org")
        self.user = Usuario.objects.create_user(
            username="diego@test.cl",
            email="diego@test.cl",
            password="password123",
            sede="puerto_montt",
            organizacion=self.org,
            rol="administrador"
        )
        self.client.login(username="diego@test.cl", password="password123")
        
        self.item = ItemInventario.objects.create(
            nombre="Resistencia 10k",
            tipo="material",
            area="telecomunicaciones",
            sede="puerto_montt",
            cantidad=10,
            unidad="unidades",
            activo=True
        )

    def test_buscar_item_json_por_nombre(self):
        response = self.client.get(reverse("inventario_buscar_json") + "?q=Resistencia")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["nombre"], "Resistencia 10k")

    def test_buscar_item_json_por_codigo(self):
        self.item.codigo_barra = "987654321"
        self.item.save()
        
        response = self.client.get(reverse("inventario_buscar_json") + "?codigo=987654321")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["nombre"], "Resistencia 10k")

    def test_ajustar_stock_individual_crea_movimiento(self):
        url = reverse("inventario_agregar_stock", args=[self.item.pk])
        # AjusteStockForm tiene cantidad, motivo, observacion
        post_data = {
            "cantidad": "5.50",
            "motivo": "compra",
            "observacion": "Factura 123"
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302) # Redirect to inventario_lista
        
        # Verificar item
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 15.5)
        self.assertIn("Factura 123", self.item.observacion)
        
        # Verificar movimiento
        movimientos = MovimientoStock.objects.filter(item=self.item)
        self.assertEqual(movimientos.count(), 1)
        mov = movimientos.first()
        self.assertEqual(mov.cantidad, 5.5)
        self.assertEqual(mov.motivo, "compra")
        self.assertEqual(mov.observacion, "Factura 123")
        self.assertEqual(mov.usuario, self.user)

    def test_agregar_stock_existente_lector_crea_movimiento(self):
        url = reverse("inventario_lector")
        # IngresoStockExistenteForm tiene item_id, cantidad, motivo, observacion
        post_data = {
            "item_id": self.item.pk,
            "cantidad": "20.00",
            "motivo": "donacion",
            "observacion": "Donado por Inacap"
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        
        # Verificar item
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 30.0)
        
        # Verificar movimiento
        mov = MovimientoStock.objects.get(item=self.item)
        self.assertEqual(mov.cantidad, 20.0)
        self.assertEqual(mov.motivo, "donacion")
        self.assertEqual(mov.usuario, self.user)
