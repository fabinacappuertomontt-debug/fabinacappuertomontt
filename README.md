# Seguimiento de proyectos INACAP

Aplicación web Django para gestionar proyectos académicos, responsables, estados, avances, tareas y observaciones.

## Tecnologías

- Django con templates HTML
- Bootstrap por CDN
- PostgreSQL
- Django ORM

## Puesta en marcha

1. Crear entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Crear archivo `.env` desde `.env.example` y ajustar credenciales de PostgreSQL.

4. Crear la base de datos en PostgreSQL, por ejemplo:

```sql
CREATE DATABASE seguimiento_proyectos;
```

5. Ejecutar migraciones y crear usuario administrador:

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

También puedes crear los usuarios base del proyecto:

```powershell
python manage.py crear_usuarios_base
```

Esto crea o actualiza a Víctor Marín, Diego Henríquez y Jorge Navarro como superusuarios. El inicio de sesión se realiza con correo institucional y contraseña `Inacap2026`.

6. Levantar servidor:

```powershell
python manage.py runserver
```

Luego ingresar a `http://127.0.0.1:8000/`.

## Funcionalidades del MVP

- Login con usuarios de Django.
- Panel general con conteos y avance promedio.
- Panel inteligente con proyectos en riesgo, últimos avances y tareas por responsable.
- Listado, búsqueda y filtros de proyectos por estado y responsable.
- Alertas visuales por estado del proyecto, bajo avance, atraso o proximidad de fecha fin.
- Creación y edición de proyectos.
- Asignación de responsables.
- Cambio de estado y porcentaje de avance.
- Registro de avances.
- Subida de evidencias y archivos por proyecto.
- Creación de tareas, separación entre pendientes/completadas y marcado con confirmación.
- Registro de observaciones.
- Módulo de usuarios para ver equipo, roles, proyectos y tareas pendientes.

## Alcance de historias

El MVP cubre HU01 a HU16 y HU20. Las historias HU17 a HU19 quedan como mejoras futuras: historial de cambios, notificaciones y comentarios internos avanzados.
