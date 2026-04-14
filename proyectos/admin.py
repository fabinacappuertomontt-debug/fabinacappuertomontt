from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Avance, Evidencia, FaseProyecto, Observacion, Proyecto, Tarea, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos del sistema", {"fields": ("nombre", "rol")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos del sistema", {"fields": ("nombre", "email", "rol")}),
    )
    list_display = ("username", "nombre", "email", "rol", "is_staff")
    search_fields = ("username", "nombre", "email")


class FaseProyectoInline(admin.TabularInline):
    model = FaseProyecto
    extra = 0
    fields = ("trl", "nombre", "estado", "realizado")


class AvanceInline(admin.TabularInline):
    model = Avance
    extra = 0


class TareaInline(admin.TabularInline):
    model = Tarea
    extra = 0


class ObservacionInline(admin.TabularInline):
    model = Observacion
    extra = 0
    readonly_fields = ("fecha",)


class EvidenciaInline(admin.TabularInline):
    model = Evidencia
    extra = 0
    readonly_fields = ("fecha_subida",)


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "estado", "porcentaje_avance", "fecha_inicio", "fecha_fin")
    list_filter = ("estado", "fecha_inicio")
    search_fields = ("nombre", "descripcion")
    filter_horizontal = ("responsables",)
    inlines = [FaseProyectoInline, TareaInline, AvanceInline, ObservacionInline, EvidenciaInline]


@admin.register(FaseProyecto)
class FaseProyectoAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "trl", "nombre", "estado", "fecha_actualizacion")
    list_filter = ("trl", "estado")
    search_fields = ("proyecto__nombre", "nombre", "realizado")


@admin.register(Avance)
class AvanceAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "fecha", "responsable")
    list_filter = ("fecha", "responsable")
    search_fields = ("descripcion", "proyecto__nombre")


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "proyecto", "estado", "responsable")
    list_filter = ("estado", "responsable")
    search_fields = ("nombre", "descripcion", "proyecto__nombre")


@admin.register(Observacion)
class ObservacionAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "usuario", "fecha")
    list_filter = ("fecha", "usuario")
    search_fields = ("comentario", "proyecto__nombre")


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "proyecto", "usuario", "fecha_subida")
    list_filter = ("fecha_subida", "usuario")
    search_fields = ("nombre", "descripcion", "proyecto__nombre")
