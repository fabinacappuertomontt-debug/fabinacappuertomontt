from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path("usuarios/nuevo/", views.UsuarioCreateView.as_view(), name="usuario_crear"),
    path("proyectos/", views.ProyectoListView.as_view(), name="proyecto_lista"),
    path("proyectos/nuevo/", views.ProyectoCreateView.as_view(), name="proyecto_crear"),
    path("proyectos/<int:pk>/", views.proyecto_detalle, name="proyecto_detalle"),
    path("proyectos/<int:pk>/editar/", views.ProyectoUpdateView.as_view(), name="proyecto_editar"),
    path("fases/<int:pk>/", views.fase_detalle, name="fase_detalle"),
    path("proyectos/<int:pk>/estado/", views.actualizar_estado, name="proyecto_estado"),
    path("proyectos/<int:pk>/avances/nuevo/", views.crear_avance, name="avance_crear"),
    path("proyectos/<int:pk>/tareas/nueva/", views.crear_tarea, name="tarea_crear"),
    path("proyectos/<int:pk>/evidencias/nueva/", views.subir_evidencia, name="evidencia_crear"),
    path("tareas/<int:pk>/completar/", views.completar_tarea, name="tarea_completar"),
    path("proyectos/<int:pk>/observaciones/nueva/", views.crear_observacion, name="observacion_crear"),
]


