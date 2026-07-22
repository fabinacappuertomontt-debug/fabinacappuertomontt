"""Formularios del asistente de creacion de proyectos.

Un formulario por paso, en vez de uno solo con veinte campos. Cada paso guarda
sobre el borrador, asi nadie pierde lo escrito si abandona a la mitad, y los
indicadores quedan en la base antes de que un paso posterior los ofrezca.
"""

from django import forms

from .forms import BootstrapFormMixin
from .models import (
    TIPOS_INDICADOR_MEDIBLES,
    TRL_DEFINICIONES,
    IndicadorCatalogo,
    ObjetivoEspecifico,
    Proyecto,
    ResultadoEsperado,
)


class PasoIdentidadForm(BootstrapFormMixin, forms.ModelForm):
    """Paso 1: de que trata el proyecto y quien lo lleva."""

    class Meta:
        model = Proyecto
        fields = [
            "nombre",
            "descripcion",
            "objetivo_principal",
            "metodologia",
            "fecha_inicio",
            "fecha_fin",
            "responsables",
        ]
        labels = {
            "nombre": "¿Cómo se llama el proyecto?",
            "descripcion": "¿De qué se trata?",
            "objetivo_principal": "¿Cuál es su objetivo principal?",
            "metodologia": "¿Cómo quieres seguir su avance?",
            "fecha_inicio": "¿Cuándo parte?",
            "fecha_fin": "¿Cuándo debería terminar?",
            "responsables": "¿Quiénes son responsables?",
        }
        help_texts = {
            "objetivo_principal": "En una frase: qué se quiere lograr con este proyecto.",
            "metodologia": (
                "Con TRL si es un desarrollo tecnológico que madura por niveles. "
                "Simple si avanza por objetivos cumplidos."
            ),
            "fecha_fin": "Opcional. Se recalcula sola con los plazos de los resultados.",
            "responsables": "Puedes agregar más después.",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "objetivo_principal": forms.Textarea(attrs={"rows": 2}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, usuarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_inicio"].input_formats = ["%Y-%m-%d"]
        self.fields["fecha_fin"].input_formats = ["%Y-%m-%d"]
        if usuarios is not None:
            self.fields["responsables"].queryset = usuarios
        self.fields["responsables"].required = False


class PasoMadurezForm(BootstrapFormMixin, forms.ModelForm):
    """Paso 2: desde que nivel TRL parte y hasta cual quiere llegar."""

    class Meta:
        model = Proyecto
        fields = ["trl_inicial", "trl_objetivo"]
        labels = {
            "trl_inicial": "¿En qué nivel está hoy?",
            "trl_objetivo": "¿A qué nivel quiere llegar?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = [("", "Selecciona un nivel")] + [
            (valor, f"TRL {valor} · {etiqueta}") for valor, etiqueta in TRL_DEFINICIONES
        ]
        for campo in ["trl_inicial", "trl_objetivo"]:
            self.fields[campo].choices = opciones
            self.fields[campo].required = True

    def clean(self):
        cleaned = super().clean()
        inicial = cleaned.get("trl_inicial")
        objetivo = cleaned.get("trl_objetivo")
        if inicial and objetivo and int(objetivo) <= int(inicial):
            self.add_error(
                "trl_objetivo",
                "El nivel al que quieres llegar tiene que ser mayor que el actual.",
            )
        return cleaned


class ObjetivoEspecificoWizardForm(BootstrapFormMixin, forms.ModelForm):
    """Paso 3: un objetivo especifico a la vez."""

    class Meta:
        model = ObjetivoEspecifico
        fields = ["descripcion"]
        labels = {"descripcion": "Objetivo específico"}
        widgets = {
            "descripcion": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Ej: Validar la precisión del sensor en laboratorio",
                }
            )
        }


class ResultadoEsperadoWizardForm(BootstrapFormMixin, forms.ModelForm):
    """Paso 4: un resultado esperado con su objetivo, su nivel y su plazo."""

    class Meta:
        model = ResultadoEsperado
        fields = ["objetivo", "descripcion", "trl_objetivo", "plazo_meses", "plazo_dias"]
        labels = {
            "objetivo": "¿A qué objetivo responde?",
            "descripcion": "¿Qué resultado concreto esperas?",
            "trl_objetivo": "¿Qué nivel TRL desbloquea?",
            "plazo_meses": "Meses",
            "plazo_dias": "Días",
        }
        help_texts = {
            "descripcion": "Algo que se pueda dar por logrado o no logrado, sin ambigüedad.",
            "plazo_meses": "Contados desde que parte el proyecto.",
        }
        widgets = {
            "descripcion": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Ej: Prototipo del sensor validado en laboratorio",
                }
            ),
        }

    def __init__(self, *args, proyecto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.proyecto = proyecto
        if proyecto is None:
            return

        self.fields["objetivo"].queryset = proyecto.objetivos.order_by("orden")
        self.fields["objetivo"].empty_label = None
        # Sin esto el desplegable usa el __str__ del modelo, que muestra el
        # nombre del proyecto y deja los objetivos indistinguibles entre si.
        self.fields["objetivo"].label_from_instance = lambda objetivo: (
            f"{objetivo.orden}. {objetivo.descripcion}"
            if len(objetivo.descripcion) <= 90
            else f"{objetivo.orden}. {objetivo.descripcion[:87]}..."
        )

        if proyecto.usa_trl:
            # Solo los niveles del recorrido del proyecto: ofrecer los nueve
            # invita a asignar resultados fuera del rango declarado.
            self.fields["trl_objetivo"].choices = [("", "Selecciona el nivel")] + [
                (valor, f"TRL {valor} · {etiqueta}")
                for valor, etiqueta in TRL_DEFINICIONES
                if proyecto.trl_inicial_efectivo < valor <= proyecto.trl_objetivo_efectivo
            ]
        else:
            # En proyectos simples no hay niveles de madurez que asignar.
            self.fields.pop("trl_objetivo")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("plazo_meses") and not cleaned.get("plazo_dias"):
            self.add_error("plazo_meses", "Indica un plazo en meses o en días.")
        return cleaned


class IndicadorDelProyectoForm(BootstrapFormMixin, forms.ModelForm):
    """Paso 4: como se comprueba que el resultado se logro.

    Se elige uno ya definido en este proyecto o se crea uno nuevo, que queda
    disponible para los demas resultados del mismo proyecto. Es lo que pidio el
    profesor: que el indicador exista antes de tener que asociarlo.
    """

    existente = forms.ModelChoiceField(
        queryset=IndicadorCatalogo.objects.none(),
        required=False,
        label="Usar un indicador ya definido en este proyecto",
        empty_label="— Crear uno nuevo —",
    )
    meta_valor = forms.DecimalField(
        required=False, label="Meta", help_text="Valor que hay que alcanzar."
    )
    linea_base = forms.DecimalField(
        required=False, label="Línea base", help_text="Valor de partida. Normalmente 0."
    )

    class Meta:
        model = IndicadorCatalogo
        fields = ["nombre", "tipo", "unidad", "medio_verificacion"]
        labels = {
            "nombre": "Nombre del indicador",
            "tipo": "¿Cómo se mide?",
            "unidad": "Unidad",
            "medio_verificacion": "¿De dónde sale el dato?",
        }
        help_texts = {
            "tipo": "Si es cantidad o porcentaje, el sistema calcula solo si se cumplió.",
            "unidad": "Ej: ensayos, horas, personas.",
            "medio_verificacion": "Ej: bitácora de laboratorio, informe de ensayo.",
        }

    def __init__(self, *args, proyecto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.proyecto = proyecto
        if proyecto is not None:
            self.fields["existente"].queryset = proyecto.indicadores_definidos.filter(
                activo=True
            )
        # Al reutilizar un indicador ya definido no se vuelve a describir: su
        # nombre y su forma de medirse ya estan decididos.
        self.fields["nombre"].required = False
        self.fields["tipo"].required = False

    def clean(self):
        cleaned = super().clean()
        existente = cleaned.get("existente")
        nombre = (cleaned.get("nombre") or "").strip()

        if existente:
            return cleaned

        if not nombre:
            self.add_error(
                "nombre", "Elige un indicador ya definido o escribe el nombre de uno nuevo."
            )
            return cleaned

        if self.proyecto and self.proyecto.indicadores_definidos.filter(
            nombre__iexact=nombre
        ).exists():
            self.add_error("nombre", "Este proyecto ya tiene un indicador con ese nombre.")

        if cleaned.get("tipo") in TIPOS_INDICADOR_MEDIBLES and cleaned.get("meta_valor") is None:
            self.add_error("meta_valor", "Un indicador que se mide necesita una meta.")

        return cleaned
