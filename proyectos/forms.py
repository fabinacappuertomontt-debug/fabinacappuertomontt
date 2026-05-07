from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Avance, Evidencia, FaseProyecto, ItemInventario, MensajePrivado, Observacion, Proyecto, Tarea, UsoInventario, Usuario


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                css_class = "responsables-checklist"
            field.widget.attrs.setdefault("class", css_class)


class ProyectoForm(BootstrapFormMixin, forms.ModelForm):
    empresa_externa = forms.BooleanField(
        required=False,
        label="¿Empresa externa?",
        help_text="Marca esta opción solo si el proyecto trabaja con una empresa o institución externa a INACAP.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    fecha_inicio = forms.DateField(
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    fecha_fin = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = Proyecto
        fields = [
            "metodologia",
            "nombre",
            "descripcion",
            "objetivo_principal",
            "objetivo_especifico",
            "resultados_esperados",
            "indicadores",
            "empresa_externa",
            "empresa_externa_nombre",
            "empresa_externa_rut",
            "empresa_externa_rubro",
            "empresa_externa_contacto",
            "empresa_externa_correo",
            "empresa_externa_telefono",
            "empresa_externa_rol",
            "empresa_externa_observaciones",
            "trl_inicial",
            "trl_objetivo",
            "fecha_inicio",
            "fecha_fin",
            "responsables",
        ]
        labels = {
            "metodologia": "Tipo de seguimiento",
            "objetivo_principal": "Objetivo principal",
            "objetivo_especifico": "Objetivo específico",
            "resultados_esperados": "Resultados esperados",
            "indicadores": "Indicadores",
            "empresa_externa_nombre": "Nombre de empresa o institución",
            "empresa_externa_rut": "RUT",
            "empresa_externa_rubro": "Rubro o área",
            "empresa_externa_contacto": "Contacto principal",
            "empresa_externa_correo": "Correo de contacto",
            "empresa_externa_telefono": "Teléfono",
            "empresa_externa_rol": "Rol en el proyecto",
            "empresa_externa_observaciones": "Observaciones de vinculación",
            "trl_inicial": "TRL inicial de referencia",
            "trl_objetivo": "TRL objetivo del proyecto",
            "responsables": "Responsables asociados al proyecto",
        }
        help_texts = {
            "metodologia": "Elige TRL solo si el proyecto necesita medir madurez tecnológica.",
            "empresa_externa_nombre": "Completa estos datos solo si marcaste empresa externa.",
            "empresa_externa_rol": "Ejemplo: cliente, aliado, beneficiario, proveedor, mentor o mandante.",
            "responsables": "Selecciona uno o más usuarios responsables del seguimiento.",
            "trl_inicial": "Para proyectos tecnológicos: nivel desde el que realmente parte el proyecto. No siempre comienza en TRL 1.",
            "trl_objetivo": "Para proyectos tecnológicos: nivel que se espera alcanzar. No siempre debe llegar a TRL 9.",
            "fecha_inicio": "Fecha real o planificada de inicio del proyecto.",
            "fecha_fin": "Fecha estimada o comprometida de cierre. Pausar o finalizar se gestiona aparte en el estado del proyecto.",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "objetivo_principal": forms.Textarea(attrs={"rows": 3}),
            "objetivo_especifico": forms.Textarea(attrs={"rows": 3}),
            "resultados_esperados": forms.Textarea(attrs={"rows": 3}),
            "indicadores": forms.Textarea(attrs={"rows": 3}),
            "empresa_externa_observaciones": forms.Textarea(attrs={"rows": 3}),
            "responsables": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, sede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sede:
            self.fields["responsables"].queryset = Usuario.objects.filter(sede=sede).order_by("nombre", "username")
        self.fields["metodologia"].widget.attrs["data-project-methodology"] = "true"
        self.fields["trl_inicial"].widget.attrs["data-trl-field"] = "true"
        self.fields["trl_objetivo"].widget.attrs["data-trl-field"] = "true"

    def clean(self):
        cleaned = super().clean()
        metodologia = cleaned.get("metodologia")
        trl_inicial = cleaned.get("trl_inicial")
        trl_objetivo = cleaned.get("trl_objetivo")
        empresa_externa = cleaned.get("empresa_externa")

        if metodologia == Proyecto.Metodologia.TRL:
            if not trl_inicial:
                self.add_error("trl_inicial", "Indica el TRL inicial real del proyecto tecnológico.")
            if not trl_objetivo:
                self.add_error("trl_objetivo", "Indica el TRL objetivo esperado del proyecto tecnológico.")
            if trl_inicial and trl_objetivo and trl_objetivo < trl_inicial:
                self.add_error("trl_objetivo", "El TRL objetivo no puede ser menor al TRL inicial.")
            cleaned["tipo_proyecto"] = Proyecto.TipoProyecto.TECNOLOGICO
        else:
            cleaned["trl_inicial"] = None
            cleaned["trl_objetivo"] = None
            cleaned["tipo_proyecto"] = Proyecto.TipoProyecto.GENERAL

        if not empresa_externa:
            for field_name in [
                "empresa_externa_nombre",
                "empresa_externa_rut",
                "empresa_externa_rubro",
                "empresa_externa_contacto",
                "empresa_externa_correo",
                "empresa_externa_telefono",
                "empresa_externa_rol",
                "empresa_externa_observaciones",
            ]:
                cleaned[field_name] = ""
        return cleaned

    def save(self, commit=True):
        proyecto = super().save(commit=False)
        metodologia = self.cleaned_data.get("metodologia")
        if metodologia == Proyecto.Metodologia.TRL:
            proyecto.tipo_proyecto = Proyecto.TipoProyecto.TECNOLOGICO
        else:
            proyecto.tipo_proyecto = Proyecto.TipoProyecto.GENERAL
            proyecto.trl_inicial = None
            proyecto.trl_objetivo = None
        if commit:
            proyecto.save()
            self.save_m2m()
        return proyecto



class EstadoProyectoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ["estado", "porcentaje_avance"]
        labels = {
            "porcentaje_avance": "Porcentaje de avance",
        }

    def clean_porcentaje_avance(self):
        porcentaje = self.cleaned_data["porcentaje_avance"]
        if porcentaje > 100:
            raise forms.ValidationError("El avance no puede superar el 100%.")
        return porcentaje


class AvanceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Avance
        fields = ["descripcion", "fecha", "responsable"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, sede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sede:
            self.fields["responsable"].queryset = Usuario.objects.filter(sede=sede).order_by("nombre", "username")


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

    def __init__(self, *args, sede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sede:
            self.fields["responsable"].queryset = Usuario.objects.filter(sede=sede).order_by("nombre", "username")


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


class ItemInventarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemInventario
        fields = [
            "nombre",
            "codigo_barra",
            "area",
            "categoria",
            "tipo",
            "cantidad",
            "unidad",
            "stock_minimo",
            "estado",
            "ubicacion",
            "observacion",
        ]
        labels = {
            "codigo_barra": "Codigo de barra",
            "stock_minimo": "Stock mínimo para alerta",
        }
        help_texts = {
            "codigo_barra": "Escanea o escribe el código del producto. Déjalo vacío si no tiene.",
            "cantidad": "Para stock variable puedes dejarlo vacío. Para filamento, idealmente usa gramos.",
            "stock_minimo": "Cuando el stock quede igual o bajo este número, aparece una alerta.",
        }
        widgets = {
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_codigo_barra(self):
        codigo = (self.cleaned_data.get("codigo_barra") or "").strip()
        return codigo or None


class LectorCodigoBarraForm(BootstrapFormMixin, forms.Form):
    codigo_barra = forms.CharField(
        label="Codigo de barra",
        max_length=80,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "off"}),
    )
    cantidad = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, label="Cantidad a agregar")
    observacion = forms.CharField(
        required=False,
        label="Observación",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_codigo_barra(self):
        return self.cleaned_data["codigo_barra"].strip()


class UsoInventarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = UsoInventario
        fields = ["item", "cantidad", "fecha", "observacion"]
        labels = {
            "item": "Material o recurso usado",
            "cantidad": "Cantidad usada",
        }
        help_texts = {
            "cantidad": "Si es fungible se descuenta del stock. Si no es fungible solo queda registrado el uso.",
        }
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, sede=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ItemInventario.objects.filter(activo=True)
        if sede:
            queryset = queryset.filter(sede=sede)
        self.fields["item"].queryset = queryset.order_by("area", "nombre")

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        cantidad = cleaned.get("cantidad")
        if cantidad is not None and cantidad <= 0:
            self.add_error("cantidad", "La cantidad debe ser mayor a cero.")
        if item and cantidad and item.descuenta_stock and item.cantidad is not None and cantidad > item.cantidad:
            self.add_error("cantidad", f"Stock insuficiente. Disponible: {item.cantidad_texto}.")
        return cleaned


class AjusteStockForm(BootstrapFormMixin, forms.Form):
    cantidad = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, label="Cantidad a agregar")
    observacion = forms.CharField(
        required=False,
        label="Observación",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class UsuarioRegistroForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = Usuario
        fields = ["username", "nombre", "email", "rol", "sede", "is_staff", "is_superuser"]
        labels = {
            "username": "Usuario",
            "sede": "Sede",
            "is_staff": "Puede entrar al admin",
            "is_superuser": "Administrador total",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.setdefault("class", "form-control")
        self.fields["password2"].widget.attrs.setdefault("class", "form-control")
        self.fields["is_staff"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["is_superuser"].widget.attrs.setdefault("class", "form-check-input")


class UsuarioUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "username",
            "nombre",
            "email",
            "institucion",
            "telefono",
            "cargo",
            "direccion",
            "biografia",
            "foto",
            "rol",
            "sede",
            "correo_verificado",
            "estado_registro",
            "is_active",
            "is_staff",
            "is_superuser",
        ]
        labels = {
            "username": "Usuario",
            "sede": "Sede",
            "institucion": "Institución o empresa",
            "telefono": "Teléfono",
            "cargo": "Cargo o área",
            "direccion": "Dirección o referencia",
            "biografia": "Datos personales importantes",
            "correo_verificado": "Correo verificado",
            "estado_registro": "Estado de registro",
            "is_active": "Cuenta activa",
            "is_staff": "Puede entrar al admin",
            "is_superuser": "Administrador total",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["correo_verificado", "is_active", "is_staff", "is_superuser"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-check-input")


class PerfilUsuarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "email", "telefono", "institucion", "cargo", "direccion", "biografia", "foto"]
        labels = {
            "nombre": "Nombre completo",
            "email": "Correo",
            "telefono": "Teléfono",
            "institucion": "Institución o empresa",
            "cargo": "Cargo o área",
            "direccion": "Dirección o referencia",
            "biografia": "Datos personales importantes",
            "foto": "Foto de perfil",
        }
        widgets = {
            "biografia": forms.Textarea(attrs={"rows": 4}),
        }


class RegistroPublicoForm(BootstrapFormMixin, UserCreationForm):
    rol = forms.ChoiceField(
        choices=[
            (Usuario.Rol.ALUMNO, "Alumno"),
            (Usuario.Rol.PRACTICANTE, "Practicante"),
            (Usuario.Rol.PROFESOR, "Profesor / Líder"),
        ],
        initial=Usuario.Rol.ALUMNO,
        label="Tipo de usuario",
        help_text="El rol Administrador lo asigna un administrador desde el panel interno.",
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "institucion", "rol", "sede", "password1", "password2"]
        labels = {
            "nombre": "Nombre completo",
            "email": "Correo institucional o laboral",
            "institucion": "Institución o empresa",
            "rol": "Tipo de usuario",
            "sede": "Sede",
        }
        help_texts = {
            "institucion": "Obligatorio si no usas un correo INACAP.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.setdefault("class", "form-control")
        self.fields["password2"].widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo.")
        return email

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        institucion = (cleaned.get("institucion") or "").strip()
        if email and not email.endswith(("@inacap.cl", "@inacapmail.cl")) and not institucion:
            self.add_error("institucion", "Indica tu institución o empresa para solicitar aprobación.")
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        email = self.cleaned_data["email"].strip().lower()
        base_username = email.split("@")[0]
        username = base_username
        counter = 1
        while Usuario.objects.filter(username=username).exists():
            counter += 1
            username = f"{base_username}{counter}"
        usuario.username = username
        usuario.email = email
        usuario.institucion = self.cleaned_data.get("institucion", "").strip()
        usuario.rol = self.cleaned_data.get("rol") or Usuario.Rol.ALUMNO
        usuario.is_active = False
        usuario.is_staff = False
        usuario.is_superuser = False
        if email.endswith(("@inacap.cl", "@inacapmail.cl")):
            usuario.correo_verificado = False
            usuario.estado_registro = Usuario.EstadoRegistro.VERIFICACION_CORREO
        else:
            usuario.correo_verificado = False
            usuario.estado_registro = Usuario.EstadoRegistro.PENDIENTE_APROBACION
        if commit:
            usuario.save()
        return usuario


class CodigoVerificacionForm(BootstrapFormMixin, forms.Form):
    codigo = forms.CharField(
        label="Código de confirmación",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip()


class MensajePrivadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MensajePrivado
        fields = ["texto", "archivo"]
        labels = {
            "texto": "Mensaje",
            "archivo": "Adjuntar archivo",
        }
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 3, "placeholder": "Escribe un mensaje privado..."}),
        }

    def clean(self):
        cleaned = super().clean()
        texto = (cleaned.get("texto") or "").strip()
        archivo = cleaned.get("archivo")
        if not texto and not archivo:
            raise forms.ValidationError("Escribe un mensaje o adjunta un archivo.")
        cleaned["texto"] = texto
        return cleaned
