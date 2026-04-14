from django import forms

from .models import Avance, Evidencia, Observacion, Proyecto, Tarea


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                css_class = "responsables-checklist"
            field.widget.attrs.setdefault("class", css_class)


class ProyectoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = [
            "nombre",
            "descripcion",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "porcentaje_avance",
            "responsables",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def clean_porcentaje_avance(self):
        porcentaje = self.cleaned_data["porcentaje_avance"]
        if porcentaje > 100:
            raise forms.ValidationError("El avance no puede superar el 100%.")
        return porcentaje


class EstadoProyectoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ["estado", "porcentaje_avance"]


class AvanceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Avance
        fields = ["descripcion", "fecha", "responsable"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }


class TareaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Tarea
        fields = ["nombre", "descripcion", "estado", "responsable"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}


class ObservacionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Observacion
        fields = ["comentario"]
        widgets = {"comentario": forms.Textarea(attrs={"rows": 3})}


class EvidenciaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Evidencia
        fields = ["nombre", "descripcion", "archivo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}
