from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Avance, Evidencia, FaseProyecto, Observacion, Proyecto, Tarea, Usuario


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
        labels = {
            "responsables": "Responsables asociados al proyecto",
        }
        help_texts = {
            "responsables": "Selecciona uno o más usuarios responsables del seguimiento.",
        }
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


class FaseProyectoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FaseProyecto
        fields = ["estado", "realizado"]
        labels = {
            "realizado": "Qué se hizo en esta fase",
        }
        widgets = {
            "realizado": forms.Textarea(attrs={"rows": 5}),
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


class UsuarioRegistroForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = Usuario
        fields = ["username", "nombre", "email", "rol", "is_staff", "is_superuser"]
        labels = {
            "username": "Usuario",
            "is_staff": "Puede entrar al admin",
            "is_superuser": "Administrador total",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.setdefault("class", "form-control")
        self.fields["password2"].widget.attrs.setdefault("class", "form-control")
        self.fields["is_staff"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["is_superuser"].widget.attrs.setdefault("class", "form-check-input")
