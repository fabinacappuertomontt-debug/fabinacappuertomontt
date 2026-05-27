from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Area, Avance, Evidencia, FaseProyecto, IndicadorResultado, ItemInventario, MensajePrivado, ObjetivoEspecifico, Observacion, Proyecto, ResultadoEsperado, Tarea, TRL_DEFINICIONES, UsoInventario, Usuario, sumar_meses_y_dias


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
            "trl_objetivo": "Nivel TRL esperado",
            "responsables": "Responsables asociados al proyecto",
        }
        help_texts = {
            "metodologia": "Define si el avance sera simple por objetivos o con madurez TRL.",
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

    def __init__(self, *args, sede=None, organizacion=None, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        if area:
            self.fields["responsables"].queryset = Usuario.objects.filter(area=area).order_by("nombre", "username")
        elif organizacion:
            self.fields["responsables"].queryset = Usuario.objects.filter(organizacion=organizacion).order_by("nombre", "username")
        elif sede:
            self.fields["responsables"].queryset = Usuario.objects.filter(sede=sede).order_by("nombre", "username")
        trl_choices = self._choices_trl_con_numero()
        self.fields["trl_inicial"].choices = trl_choices
        self.fields["trl_objetivo"].choices = trl_choices
        self.fields["metodologia"].widget.attrs["data-project-methodology"] = "true"
        self.fields["trl_inicial"].widget.attrs["data-trl-field"] = "true"
        self.fields["trl_objetivo"].widget.attrs["data-trl-field"] = "true"
        self.fields["objetivo_especifico"].widget.attrs["data-structured-field"] = "objetivos"
        self.fields["resultados_esperados"].widget.attrs["data-structured-field"] = "resultados"
        self.fields["indicadores"].widget.attrs["data-structured-field"] = "indicadores"
        if self.instance.pk:
            self._cargar_estructura_existente()

    def _choices_trl_con_numero(self):
        return [("", "---------")] + [
            (valor, f"TRL {valor} - {etiqueta}")
            for valor, etiqueta in TRL_DEFINICIONES
        ]

    def _cargar_estructura_existente(self):
        payload = []
        objetivos = self.instance.objetivos.prefetch_related("resultados__indicadores").all()
        for objetivo in objetivos:
            objetivo_data = {
                "descripcion": objetivo.descripcion,
                "resultados": [],
            }
            for resultado in objetivo.resultados.all():
                objetivo_data["resultados"].append({
                    "descripcion": resultado.descripcion,
                    "trl": resultado.trl_objetivo,
                    "meses": resultado.plazo_meses,
                    "dias": resultado.plazo_dias,
                    "fecha_cumplimiento": resultado.fecha_cumplimiento.isoformat() if resultado.fecha_cumplimiento else "",
                    "observaciones": resultado.observaciones,
                    "indicadores": [
                        {
                            "descripcion": indicador.descripcion,
                            "meta": indicador.meta,
                            "valor_actual": indicador.valor_actual,
                            "cumplido": indicador.cumplido,
                        }
                        for indicador in resultado.indicadores.all()
                    ],
                })
            payload.append(objetivo_data)
        if payload:
            serialized = __import__("json").dumps(payload, ensure_ascii=True)
            self.initial["objetivo_especifico"] = serialized
            self.initial["resultados_esperados"] = serialized
            self.initial["indicadores"] = serialized

    def _parsear_payload_trl(self, raw_value, requiere_trl=True):
        try:
            payload = __import__("json").loads(raw_value or "[]")
        except ValueError as error:
            raise forms.ValidationError("La estructura de objetivos y resultados no tiene un formato valido.") from error
        if not isinstance(payload, list):
            raise forms.ValidationError("La estructura enviada debe ser una lista de objetivos.")
        objetivos_limpios = []
        for objetivo_index, objetivo in enumerate(payload, start=1):
            descripcion = str((objetivo or {}).get("descripcion", "")).strip()
            if not descripcion:
                continue
            resultados_limpios = []
            for resultado_index, resultado in enumerate((objetivo or {}).get("resultados", []), start=1):
                descripcion_resultado = str((resultado or {}).get("descripcion", "")).strip()
                if not descripcion_resultado:
                    continue
                trl = resultado.get("trl")
                meses = int(resultado.get("meses") or 0)
                dias = int(resultado.get("dias") or 0)
                if not trl and requiere_trl:
                    raise forms.ValidationError(f"Falta definir el TRL del resultado {resultado_index} del objetivo {objetivo_index}.")
                if not trl:
                    trl = 1
                if meses < 0 or dias < 0 or (meses == 0 and dias == 0):
                    raise forms.ValidationError(f"El resultado {resultado_index} del objetivo {objetivo_index} debe tener un plazo en meses o dias.")
                indicadores_limpios = []
                for indicador_index, indicador in enumerate((resultado or {}).get("indicadores", []), start=1):
                    descripcion_indicador = str((indicador or {}).get("descripcion", "")).strip()
                    if not descripcion_indicador:
                        continue
                    indicadores_limpios.append({
                        "descripcion": descripcion_indicador,
                        "meta": str((indicador or {}).get("meta", "")).strip(),
                        "valor_actual": str((indicador or {}).get("valor_actual", "")).strip(),
                        "cumplido": bool((indicador or {}).get("cumplido")),
                        "orden": indicador_index,
                    })
                if not indicadores_limpios:
                    raise forms.ValidationError(f"El resultado {resultado_index} del objetivo {objetivo_index} necesita al menos un indicador asociado.")
                resultados_limpios.append({
                    "descripcion": descripcion_resultado,
                    "trl": int(trl),
                    "meses": meses,
                    "dias": dias,
                    "fecha_cumplimiento": str((resultado or {}).get("fecha_cumplimiento", "")).strip(),
                    "observaciones": str((resultado or {}).get("observaciones", "")).strip(),
                    "indicadores": indicadores_limpios,
                    "orden": resultado_index,
                })
            if not resultados_limpios:
                raise forms.ValidationError(f"El objetivo {objetivo_index} necesita al menos un resultado esperado.")
            objetivos_limpios.append({
                "descripcion": descripcion,
                "resultados": resultados_limpios,
                "orden": objetivo_index,
            })
        return objetivos_limpios

    def clean(self):
        cleaned = super().clean()
        metodologia = cleaned.get("metodologia")
        trl_inicial = cleaned.get("trl_inicial")
        trl_objetivo = cleaned.get("trl_objetivo")
        empresa_externa = cleaned.get("empresa_externa")
        fecha_inicio = cleaned.get("fecha_inicio")
        payload_trl = []
        try:
            payload_trl = self._parsear_payload_trl(
                cleaned.get("objetivo_especifico"),
                requiere_trl=metodologia == Proyecto.Metodologia.TRL,
            )
        except forms.ValidationError as error:
            self.add_error("objetivo_especifico", error)

        if metodologia == Proyecto.Metodologia.TRL:
            if not trl_inicial:
                self.add_error("trl_inicial", "Indica el TRL inicial real del proyecto tecnológico.")
            if not trl_objetivo:
                self.add_error("trl_objetivo", "Indica el nivel TRL esperado del proyecto tecnológico.")
            if trl_inicial and trl_objetivo and trl_objetivo < trl_inicial:
                self.add_error("trl_objetivo", "El nivel TRL esperado no puede ser menor al TRL inicial.")
            for objetivo in payload_trl:
                for resultado in objetivo["resultados"]:
                    if trl_inicial and resultado["trl"] <= trl_inicial:
                        self.add_error("resultados_esperados", f"Cada resultado debe apuntar a un TRL superior al inicial. Revisa '{resultado['descripcion'][:40]}'.")
                    if trl_objetivo and resultado["trl"] > trl_objetivo:
                        self.add_error("resultados_esperados", f"Hay resultados sobre el nivel TRL esperado definido. Revisa '{resultado['descripcion'][:40]}'.")
            cleaned["tipo_proyecto"] = Proyecto.TipoProyecto.TECNOLOGICO
        else:
            cleaned["trl_inicial"] = None
            cleaned["trl_objetivo"] = None
            cleaned["tipo_proyecto"] = Proyecto.TipoProyecto.GENERAL
            for objetivo in payload_trl:
                for resultado in objetivo["resultados"]:
                    resultado["trl"] = 1

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
        cleaned["payload_trl"] = payload_trl
        if payload_trl:
            if fecha_inicio:
                fecha_fin_calculada = fecha_inicio
                for objetivo in payload_trl:
                    for resultado in objetivo["resultados"]:
                        fecha_fin_calculada = sumar_meses_y_dias(
                            fecha_fin_calculada,
                            resultado["meses"],
                            resultado["dias"],
                        )
                cleaned["fecha_fin"] = fecha_fin_calculada
            cleaned["objetivo_especifico"] = "\n".join(
                f"{objetivo['orden']}. {objetivo['descripcion']}" for objetivo in payload_trl
            )
            cleaned["resultados_esperados"] = "\n".join(
                f"OE{objetivo['orden']}.R{resultado['orden']}"
                f"{' - TRL %s' % resultado['trl'] if metodologia == Proyecto.Metodologia.TRL else ''}: "
                f"{resultado['descripcion']} (plazo: {resultado['meses']} meses, {resultado['dias']} dias)"
                for objetivo in payload_trl
                for resultado in objetivo["resultados"]
            )
            cleaned["indicadores"] = "\n".join(
                f"OE{objetivo['orden']}.R{resultado['orden']}.I{indicador['orden']}: {indicador['descripcion']}"
                for objetivo in payload_trl
                for resultado in objetivo["resultados"]
                for indicador in resultado["indicadores"]
            )
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
            self._guardar_estructura_trl(proyecto)
        return proyecto

    def _guardar_estructura_trl(self, proyecto):
        from .views import sincronizar_avance_simple_desde_objetivos, sincronizar_trl_desde_resultados

        payload_trl = self.cleaned_data.get("payload_trl") or []
        ObjetivoEspecifico.objects.filter(proyecto=proyecto).delete()
        for objetivo_data in payload_trl:
            objetivo = ObjetivoEspecifico.objects.create(
                proyecto=proyecto,
                descripcion=objetivo_data["descripcion"],
                orden=objetivo_data["orden"],
            )
            for resultado_data in objetivo_data["resultados"]:
                resultado = ResultadoEsperado.objects.create(
                    objetivo=objetivo,
                    descripcion=resultado_data["descripcion"],
                    orden=resultado_data["orden"],
                    trl_objetivo=resultado_data["trl"],
                    plazo_meses=resultado_data["meses"],
                    plazo_dias=resultado_data["dias"],
                    fecha_cumplimiento=forms.DateField().clean(resultado_data["fecha_cumplimiento"]) if resultado_data["fecha_cumplimiento"] else None,
                    observaciones=resultado_data["observaciones"],
                )
                for indicador_data in resultado_data["indicadores"]:
                    IndicadorResultado.objects.create(
                        resultado=resultado,
                        descripcion=indicador_data["descripcion"],
                        orden=indicador_data["orden"],
                        meta=indicador_data["meta"],
                        valor_actual=indicador_data["valor_actual"],
                        cumplido=indicador_data["cumplido"],
                    )
        if proyecto.metodologia == Proyecto.Metodologia.TRL:
            sincronizar_trl_desde_resultados(proyecto)
        else:
            sincronizar_avance_simple_desde_objetivos(proyecto)



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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.proyecto.usa_trl:
            self.fields["estado"].disabled = True
            self.fields["estado"].help_text = "El estado del TRL ahora se calcula automaticamente segun resultados e indicadores."

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
        fields = ["username", "nombre", "email", "rol", "organizacion", "area", "sede", "is_staff", "is_superuser"]
        labels = {
            "username": "Usuario",
            "organizacion": "Organizacion",
            "area": "Area",
            "sede": "Sede",
            "is_staff": "Puede entrar al admin",
            "is_superuser": "Administrador total",
        }

    def __init__(self, *args, **kwargs):
        organizacion = kwargs.pop("organizacion", None)
        super().__init__(*args, **kwargs)
        if organizacion:
            self.fields["organizacion"].initial = organizacion
            self.fields["area"].queryset = Area.objects.filter(organizacion=organizacion, activa=True).order_by("nombre")
        else:
            self.fields["area"].queryset = Area.objects.filter(activa=True).select_related("organizacion").order_by("organizacion__nombre", "nombre")
        self.fields["area"].required = True
        self.fields["password1"].widget.attrs.setdefault("class", "form-control")
        self.fields["password2"].widget.attrs.setdefault("class", "form-control")
        self.fields["is_staff"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["is_superuser"].widget.attrs.setdefault("class", "form-check-input")

    def clean(self):
        cleaned = super().clean()
        area = cleaned.get("area")
        organizacion = cleaned.get("organizacion")
        if area and not organizacion:
            cleaned["organizacion"] = area.organizacion
        elif area and organizacion and area.organizacion_id != organizacion.id:
            self.add_error("area", "El area debe pertenecer a la organizacion seleccionada.")
        return cleaned


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
            "organizacion",
            "area",
            "sede",
            "correo_verificado",
            "estado_registro",
            "is_active",
            "is_staff",
            "is_superuser",
        ]
        labels = {
            "username": "Usuario",
            "organizacion": "Organizacion",
            "area": "Area",
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
        organizacion = kwargs.pop("organizacion", None)
        super().__init__(*args, **kwargs)
        organizacion_actual = organizacion or getattr(self.instance, "organizacion", None)
        if organizacion_actual:
            self.fields["area"].queryset = Area.objects.filter(organizacion=organizacion_actual, activa=True).order_by("nombre")
        else:
            self.fields["area"].queryset = Area.objects.filter(activa=True).select_related("organizacion").order_by("organizacion__nombre", "nombre")
        self.fields["area"].required = True
        for field_name in ["correo_verificado", "is_active", "is_staff", "is_superuser"]:
            self.fields[field_name].widget.attrs.setdefault("class", "form-check-input")

    def clean(self):
        cleaned = super().clean()
        area = cleaned.get("area")
        organizacion = cleaned.get("organizacion")
        if area and not organizacion:
            cleaned["organizacion"] = area.organizacion
        elif area and organizacion and area.organizacion_id != organizacion.id:
            self.add_error("area", "El area debe pertenecer a la organizacion seleccionada.")
        return cleaned


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
        fields = ["nombre", "email", "institucion", "rol", "area", "sede", "password1", "password2"]
        labels = {
            "nombre": "Nombre completo",
            "email": "Correo institucional o laboral",
            "institucion": "Institución o empresa",
            "rol": "Tipo de usuario",
            "area": "Area",
            "sede": "Sede",
        }
        help_texts = {
            "institucion": "Obligatorio si no usas un correo INACAP.",
            "area": "Selecciona el area a la que perteneces. Tu cuenta quedara separada por esa area.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = Area.objects.filter(
            organizacion__slug="fab-inacap-puerto-montt",
            activa=True,
        ).order_by("nombre")
        self.fields["area"].empty_label = "Selecciona tu area"
        self.fields["area"].required = True
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
        if not cleaned.get("area"):
            self.add_error("area", "Selecciona el area a la que perteneces.")
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
        usuario.area = self.cleaned_data.get("area")
        if usuario.area:
            usuario.organizacion = usuario.area.organizacion
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
