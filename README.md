# Seguimiento de Proyectos INACAP Puerto Montt

Aplicación web desarrollada en Django para gestionar y dar seguimiento a proyectos académicos durante el año. El sistema permite registrar proyectos, asignar responsables, controlar estados, administrar tareas, subir evidencias, registrar avances y revisar un panel general con alertas y resumen del trabajo.

El proyecto está orientado inicialmente al equipo de INACAP Puerto Montt, con usuarios practicantes, profesor/líder y administrador. La arquitectura queda preparada para crecer a más equipos en el futuro.

## Objetivo del proyecto

Construir una plataforma web funcional para visualizar, organizar y controlar el avance de proyectos reales en un entorno académico, manteniendo evidencia del trabajo realizado y facilitando la revisión por parte de profesores o líderes.

## Usuarios del sistema

- Practicantes o equipo de trabajo: Diego Henríquez y Jorge Navarro.
- Profesor o líder de proyecto: Víctor Marín.
- Administrador: usuario con permisos para gestionar usuarios, proyectos y datos generales.

## Tecnologías utilizadas

- Lenguaje principal: Python.
- Framework backend: Django.
- Frontend: templates HTML de Django.
- Estilos: Bootstrap por CDN y CSS propio.
- Base de datos: PostgreSQL.
- ORM: Django ORM.
- Variables de entorno: python-dotenv con archivo `.env`.
- Gestión de archivos: `media/` para evidencias subidas por usuarios.

## Motor de base de datos

El proyecto utiliza PostgreSQL como motor de base de datos. La conexión se configura mediante variables de entorno en el archivo `.env`.

Ejemplo de configuración:

```env
POSTGRES_DB=seguimiento_proyectos
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu_password_seguro
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
PUBLIC_SITE_URL=https://tu-dominio-publico
LAB_ADMIN_EMAILS=correo_admin@dominio.cl
GEMINI_API_KEY=tu_clave_gemini
```

## Funcionalidades principales

- Inicio de sesión con correo institucional.
- Panel general con indicadores del estado de los proyectos.
- Listado de proyectos con filtros por estado y responsable.
- Creación y edición de proyectos.
- Asociación de responsables a cada proyecto.
- Cambio de estado del proyecto.
- Registro de porcentaje de avance.
- Registro de avances del proyecto.
- Creación y gestión de tareas.
- Separación de tareas pendientes y completadas.
- Registro de observaciones.
- Subida y descarga de evidencias.
- Módulo de usuarios.
- Alertas visuales para proyectos atrasados, con bajo avance o próximos a vencer.
- Fases de seguimiento por proyecto.
- Detección automática del tipo de proyecto para aplicar fases adecuadas.

## Fases y madurez del proyecto

El sistema diferencia entre proyectos tecnológicos y actividades académicas.

Si el proyecto corresponde a una solución tecnológica, por ejemplo sistema web, app móvil, software, sensor, prototipo, plataforma o solución con IA, se aplica la escala TRL.

La escala TRL representa el nivel de madurez tecnológica de un proyecto, desde una idea inicial hasta una solución probada en un entorno real.

Niveles TRL usados:

1. Principios básicos observados.
2. Concepto tecnológico formulado.
3. Prueba de concepto experimental.
4. Validación en laboratorio.
5. Validación en entorno relevante.
6. Prototipo demostrado en entorno relevante.
7. Prototipo demostrado en entorno real.
8. Sistema completo y validado.
9. Sistema probado con éxito en entorno real.

Si el proyecto corresponde a una actividad académica, como charla, reunión, presentación, capacitación, coordinación o evento, el sistema no fuerza TRL. En ese caso utiliza fases propias de actividad:

1. Planificación.
2. Preparación de materiales.
3. Coordinación y difusión.
4. Ejecución.
5. Evaluación.
6. Cierre.

Cada fase puede estar en estado pendiente, en proceso o completada. Al ingresar a una fase se puede registrar qué se hizo para justificar su estado.

## Historias de usuario cubiertas

El MVP cubre las principales historias de usuario:

- HU01: Ver proyectos.
- HU02: Crear proyecto.
- HU03: Editar información del proyecto.
- HU04: Ver detalle de proyecto.
- HU05: Asignar responsables.
- HU06: Actualizar estado.
- HU07: Registrar avances.
- HU08: Registrar observaciones.
- HU09: Ver porcentaje de avance.
- HU10: Ver proyectos por responsable.
- HU11: Ver proyectos por estado.
- HU12: Registrar tareas.
- HU13: Marcar tareas como completadas.
- HU14: Iniciar sesión.
- HU15: Ver panel general.
- HU16: Subir archivos o evidencias.
- HU20: Ver proyectos atrasados mediante alertas del panel.

Quedan como posibles mejoras futuras:

- HU17: Historial de cambios.
- HU18: Notificaciones.
- HU19: Comentarios internos avanzados.

## Requisitos previos

Antes de levantar el proyecto se necesita tener instalado:

- Python 3.12 o compatible.
- PostgreSQL.
- pgAdmin 4, opcional pero recomendado para administrar la base de datos.
- Git, opcional para clonar o versionar el proyecto.

## Crear base de datos en pgAdmin

1. Abrir pgAdmin.
2. Conectarse al servidor local de PostgreSQL.
3. Click derecho en `Databases`.
4. Seleccionar `Create` y luego `Database`.
5. Crear una base de datos, por ejemplo:

```text
seguimiento_proyectos
```

6. Confirmar que el usuario, contraseña, host y puerto coincidan con el archivo `.env`.

## Instalación del proyecto

1. Entrar a la carpeta del proyecto:

```powershell
cd "C:\Users\diego\Documents\FabPuertomontt"
```

2. Crear un entorno virtual:

```powershell
python -m venv .venv
```

3. Activar el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

5. Crear el archivo `.env` copiando `.env.example` y ajustando los datos de PostgreSQL.

6. Ejecutar migraciones:

```powershell
python manage.py migrate
```

7. Crear o actualizar usuarios base:

```powershell
python manage.py crear_usuarios_base --password "contrasena-temporal-segura"
```

8. Levantar el servidor:

```powershell
python manage.py runserver
```

9. Abrir en el navegador:

```text
http://127.0.0.1:8000/
```

## Usuarios base

El sistema incluye usuarios base para pruebas y demostración:

| Nombre | Correo | Rol |
| --- | --- | --- |
| Víctor Marín | vmarina@inacap.cl | Profesor / Administrador |
| Diego Henríquez | diego.henriquez34@inacapmail.cl | Practicante / Administrador |
| Jorge Navarro | jorge.navarrp@inacapmail.cl | Practicante / Administrador |

La contraseña inicial no queda escrita en el código. Debe indicarse al ejecutar el comando con `--password` o mediante la variable `BASE_USERS_PASSWORD`.

## Dependencias principales

Las dependencias están registradas en `requirements.txt` para permitir levantar el proyecto en otra máquina.

Contenido principal:

```text
Django>=5.0,<6.0
psycopg[binary]>=3.1,<4.0
python-dotenv>=1.0,<2.0
```

## Comandos útiles

Revisar errores de configuración:

```powershell
python manage.py check
```

Crear migraciones después de modificar modelos:

```powershell
python manage.py makemigrations
```

Aplicar migraciones:

```powershell
python manage.py migrate
```

Crear superusuario manual:

```powershell
python manage.py createsuperuser
```

Levantar servidor local:

```powershell
python manage.py runserver
```

## Estructura general del proyecto

```text
FabPuertomontt/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
├── seguimiento/
├── proyectos/
├── templates/
├── static/
└── media/
```

Carpetas principales:

- `seguimiento/`: configuración principal de Django.
- `proyectos/`: aplicación principal con modelos, vistas, formularios, rutas y migraciones.
- `templates/`: archivos HTML renderizados por Django.
- `static/`: archivos CSS y recursos estáticos.
- `media/`: evidencias y archivos subidos por usuarios.

## Estado actual

El proyecto se encuentra en etapa MVP funcional. Permite administrar proyectos académicos, controlar avances, responsables, tareas, evidencias, observaciones y fases de seguimiento. Además, diferencia entre proyectos tecnológicos con TRL y actividades académicas con fases propias.
