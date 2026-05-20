from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Area, Avance, Evidencia, FaseProyecto, ItemInventario, MensajePrivado, Observacion, Organizacion, Proyecto, Tarea, UsoInventario, Usuario


@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "activa", "fecha_creacion")
    list_filter = ("activa",)
    search_fields = ("nombre", "slug")


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "organizacion", "correo_contacto", "activa", "es_fab")
    list_filter = ("organizacion", "activa", "es_fab")
    search_fields = ("nombre", "slug", "correo_contacto", "organizacion__nombre")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos del sistema", {"fields": ("nombre", "institucion", "telefono", "cargo", "direccion", "biografia", "foto", "rol", "organizacion", "area", "sede", "correo_verificado", "estado_registro")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos del sistema", {"fields": ("nombre", "email", "rol", "organizacion", "area", "sede")}),
    )
    list_display = ("username", "nombre", "email", "telefono", "institucion", "rol", "organizacion", "area", "sede", "estado_registro", "is_active", "is_staff")
    list_filter = ("organizacion", "area", "sede", "rol", "estado_registro", "correo_verificado", "is_active", "is_staff")
    search_fields = ("username", "nombre", "email", "institucion", "organizacion__nombre", "area__nombre")


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


class UsoInventarioInline(admin.TabularInline):
    model = UsoInventario
    extra = 0
    readonly_fields = ("creado_en",)


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "creador", "organizacion", "area", "sede", "estado", "empresa_externa", "porcentaje_avance", "fecha_inicio", "fecha_fin")
    list_filter = ("organizacion", "area", "sede", "estado", "empresa_externa", "fecha_inicio")
    search_fields = ("nombre", "descripcion", "empresa_externa_nombre", "empresa_externa_contacto", "organizacion__nombre", "area__nombre", "creador__nombre", "creador__email")
    filter_horizontal = ("responsables",)
    inlines = [FaseProyectoInline, TareaInline, AvanceInline, ObservacionInline, EvidenciaInline, UsoInventarioInline]


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



@admin.register(ItemInventario)
class ItemInventarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_barra", "sede", "area", "categoria", "tipo", "cantidad", "unidad", "stock_minimo", "estado")
    list_filter = ("sede", "area", "tipo", "estado", "activo")
    search_fields = ("nombre", "codigo_barra", "categoria", "ubicacion", "observacion")


@admin.register(UsoInventario)
class UsoInventarioAdmin(admin.ModelAdmin):
    list_display = ("item", "proyecto", "cantidad", "fecha", "usuario")
    list_filter = ("fecha", "item__area", "item__tipo")
    search_fields = ("item__nombre", "proyecto__nombre", "observacion")


@admin.register(MensajePrivado)
class MensajePrivadoAdmin(admin.ModelAdmin):
    list_display = ("remitente", "destinatario", "creado_en", "leido")
    list_filter = ("creado_en", "leido")
    search_fields = ("remitente__nombre", "remitente__email", "destinatario__nombre", "destinatario__email", "texto")
