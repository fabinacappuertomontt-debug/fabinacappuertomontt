"""Normalizacion y respaldo del servicio de IA."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from proyectos.gemini_service import (
    _nivel_trl,
    _presupuesto_razonamiento,
    _SinCuotaGemini,
    _texto_gemini,
)


class NivelTrlTests(TestCase):
    def test_acepta_las_formas_en_que_responde_el_modelo(self):
        # El modelo devuelve a veces el numero y a veces la frase completa.
        casos = {
            4: "4",
            "4": "4",
            "TRL 4": "4",
            "TRL 4: Validacion en laboratorio": "4",
            "nivel 9": "9",
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(_nivel_trl(entrada), esperado)

    def test_descarta_lo_que_no_es_un_nivel_valido(self):
        for entrada in [None, "", "sin evaluacion", 0, 10, "TRL 42"]:
            with self.subTest(entrada=entrada):
                self.assertEqual(_nivel_trl(entrada), "")


class PresupuestoRazonamientoTests(TestCase):
    @override_settings(AI_THINKING_BUDGET_RAPIDO=0, AI_THINKING_BUDGET_PESADO=1024)
    def test_lo_interactivo_no_razona_y_lo_pesado_si(self):
        self.assertEqual(_presupuesto_razonamiento(rapido=True), 0)
        self.assertEqual(_presupuesto_razonamiento(rapido=False), 1024)


@override_settings(
    GEMINI_API_KEY="clave-de-prueba",
    GEMINI_MODEL="gemini-2.5-flash",
    GEMINI_MODEL_PRO="gemini-2.5-pro",
)
class RespaldoPorCuotaTests(TestCase):
    def test_si_el_modelo_grande_no_tiene_cuota_se_usa_el_liviano(self):
        # El plan gratuito agota el modelo grande mucho antes que flash. Caer
        # directo a Groq bajaria mas la calidad que probar con flash.
        usados = []

        def falso_pedir(prompt, modelo, temperature, rapido):
            usados.append(modelo)
            if modelo == "gemini-2.5-pro":
                raise _SinCuotaGemini("sin cuota")
            return '{"ok": true}'

        with patch("proyectos.gemini_service._pedir_texto_gemini", falso_pedir):
            texto = _texto_gemini("hola", rapido=False, pesado=True)

        self.assertEqual(texto, '{"ok": true}')
        self.assertEqual(usados, ["gemini-2.5-pro", "gemini-2.5-flash"])

    def test_lo_interactivo_no_gasta_cuota_del_modelo_grande(self):
        usados = []

        def falso_pedir(prompt, modelo, temperature, rapido):
            usados.append(modelo)
            return "{}"

        with patch("proyectos.gemini_service._pedir_texto_gemini", falso_pedir):
            _texto_gemini("hola", rapido=True)

        self.assertEqual(usados, ["gemini-2.5-flash"])

    def test_si_ningun_modelo_tiene_cuota_se_propaga_el_error(self):
        def falso_pedir(prompt, modelo, temperature, rapido):
            raise _SinCuotaGemini("sin cuota")

        with patch("proyectos.gemini_service._pedir_texto_gemini", falso_pedir):
            with self.assertRaises(_SinCuotaGemini):
                _texto_gemini("hola", rapido=False, pesado=True)
