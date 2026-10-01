# Documentación técnica — Plataforma de Seguimiento de Proyectos (FAB INACAP Puerto Montt)

Documento de traspaso para el equipo de práctica que continúa el proyecto.

---

## 1. Qué es y en qué estado se entrega

Aplicación web en **Django** para dar seguimiento a los proyectos del laboratorio: proyectos con metodología **simple** o **TRL** (nivel de madurez tecnológica), objetivos, resultados e indicadores, fases, tareas, avances, evidencias, observaciones, inventario con lector de código de barras, chat interno, notificaciones, exportación a PDF y un asistente de **IA** que propone estructura, tareas y revisa el avance TRL.

**Versión que se entrega:** el estado del sistema al **1 de julio de 2026** (final de la práctica anterior), más estos cambios de entrega:

- Se eliminó el **panel de superadmin** (`/control/...`), su login, el rol `superadmin` y el permiso que le dejaba ver todas las organizaciones.
- Se eliminó el comando `crear_usuarios_base` (creaba superusuarios con correos personales). El primer usuario se crea con `createsuperuser` (ver sección 4).
- Se eliminó la carpeta `scratch/` (scripts sueltos, uno mandaba correos masivos).
- Se quitó el aviso "Semana de prueba" de la bienvenida (tenía datos de contacto personales).
- El despliegue a Azure ahora es **solo manual** (antes se desplegaba en cada push a `main`).

La idea es que el equipo nuevo lo arregle y lo mejore. La sección 9 lista problemas conocidos para empezar.

---

## 2. Tecnologías

| Pieza | Qué se usa |
| --- | --- |
| Lenguaje | Python 3.11 / 3.12 |
| Framework | Django 5.2 |
| Base de datos | PostgreSQL |
| Frontend | Templates de Django + Bootstrap (CDN) + CSS propio en `static/css/` |
| IA | Google **Gemini** (principal) y **Groq** (respaldo), llamadas HTTP directas sin SDK |
| Correo | SMTP de **Brevo** |
| PDF | ReportLab |
| Archivos estáticos en producción | WhiteNoise |
| Servidor en producción | Gunicorn en Azure App Service (`startup.sh`) |

Dependencias exactas en `requirements.txt`.

---

## 3. Lo que tienen que configurar ustedes (claves y servicios)

Ninguna clave viene en el repositorio. Cada una va en el archivo `.env` (local) o en la configuración de Azure (producción). Partan copiando `.env.example` a `.env`.

### 3.1 IA — Gemini (obligatoria para que la IA funcione)

1. Entrar a **Google AI Studio**: https://aistudio.google.com/apikey
2. Iniciar sesión con una cuenta Google (idealmente la del laboratorio, no una personal).
3. *Create API key* → copiarla.
4. En `.env`:
   ```env
   GEMINI_API_KEY=la_clave_que_copiaron
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_MODEL_PRO=gemini-2.5-pro
   ```

`GEMINI_MODEL` se usa para análisis livianos (revisión TRL, etapas) y `GEMINI_MODEL_PRO` para la generación pesada (estructura del proyecto, mesa de trabajo). Google cambia y retira modelos seguido: si la IA responde error de modelo, revisen los nombres vigentes en AI Studio y cámbienlos en el `.env`.

### 3.2 IA — Groq (opcional, respaldo)

Si Gemini falla o no está configurado, el sistema intenta con Groq.

1. Entrar a https://console.groq.com/keys
2. *Create API Key* → copiarla.
3. En `.env`:
   ```env
   GROQ_API_KEY=la_clave_de_groq
   GROQ_MODEL=llama-3.1-8b-instant
   ```

**Sin ninguna clave de IA la app funciona igual**; las pantallas de IA muestran un aviso de que falta configurar `GEMINI_API_KEY` o `GROQ_API_KEY`.

### 3.3 Correo — Brevo

El sistema manda correos para: código de verificación al registrarse, aprobación de usuarios externos, recuperación de contraseña y notificaciones de proyectos.

**Para desarrollar no necesitan Brevo:** con `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` (el valor por defecto del `.env.example`) los correos se imprimen en la terminal donde corre el servidor, incluido el código de verificación.

Para enviar correos de verdad:

1. Crear cuenta en https://www.brevo.com (plan gratuito: ~300 correos/día).
2. **Verificar un remitente:** *Senders, Domains & Dedicated IPs → Senders → Add a sender*. Ese correo es el que va en `DEFAULT_FROM_EMAIL`. Si el remitente no está verificado, Brevo rechaza los correos.
3. **Obtener credenciales SMTP:** *SMTP & API → SMTP*. Ahí aparece el *Login* (algo como `xxxx@smtp-brevo.com`) y se genera una *SMTP key*.
4. En `.env`:
   ```env
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp-relay.brevo.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_USE_SSL=False
   EMAIL_HOST_USER=el_login_smtp_de_brevo
   EMAIL_HOST_PASSWORD=la_smtp_key_de_brevo
   DEFAULT_FROM_EMAIL=Plataforma de Proyectos <remitente_verificado@dominio.cl>
   ```
   Alternativa: puerto `465` con `EMAIL_USE_SSL=True` y `EMAIL_USE_TLS=False` (no pueden estar los dos en `True`).

Ojo: la *SMTP key* no es lo mismo que la *API key* de Brevo. Django usa SMTP, así que necesitan la SMTP key.

### 3.4 Resto de variables

| Variable | Para qué sirve |
| --- | --- |
| `SECRET_KEY` | Clave de Django. Obligatoria si `DEBUG=False` (si falta, la app no arranca). Generar con el comando que está en `.env.example`. |
| `DEBUG` | `True` en local, `False` en producción. |
| `ALLOWED_HOSTS` | Dominios permitidos, separados por coma. En producción, el dominio de Azure. |
| `CSRF_TRUSTED_ORIGINS` | En producción, la URL con `https://`, p. ej. `https://trl-fablab.azurewebsites.net`. |
| `PUBLIC_SITE_URL` | URL pública. Se usa para armar los enlaces de los correos (aprobar/rechazar registros). Si queda vacía, esos enlaces salen rotos. |
| `LAB_ADMIN_EMAILS` | Correos con permiso de administrador del laboratorio. Pueden **eliminar proyectos** y reciben las solicitudes de registro de usuarios externos. |
| `POSTGRES_*` | Conexión a PostgreSQL. |
| `AI_TIMEOUT_SECONDS` | Segundos máximos de espera a la IA. |

---

## 4. Levantar el proyecto en local

Requisitos: Python 3.11+, PostgreSQL y Git.

```powershell
git clone https://github.com/fabinacappuertomontt-debug/fabinacappuertomontt.git
cd fabinacappuertomontt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

1. Crear una base de datos **nueva y vacía** en PostgreSQL (con pgAdmin o `createdb seguimiento_proyectos`) y poner los datos en `.env`.
2. Migrar. Las migraciones crean solas las organizaciones *FAB INACAP Puerto Montt* y *Crea INACAP Osorno* con sus áreas:
   ```powershell
   python manage.py migrate
   ```
3. Crear el primer usuario administrador:
   ```powershell
   python manage.py createsuperuser
   ```
4. Levantar el servidor y entrar a http://127.0.0.1:8000/admin/ con ese usuario.
5. En **Usuarios**, editar el usuario creado y asignarle: **Organización**, **Área**, **Rol = Administrador**, *Correo verificado* y *Estado de registro = Aprobado*. Sin organización y área, el usuario no ve proyectos y no puede crear usuarios.
6. Entrar a la app en http://127.0.0.1:8000/login/ con el correo y la contraseña.

```powershell
python manage.py runserver
```

---

## 5. Estructura del código

```text
seguimiento/          Configuración de Django (settings, urls raíz, wsgi)
proyectos/            La única app: todo el sistema vive aquí
  models.py           Modelos (ver sección 6)
  views.py            Todas las vistas (~3.800 líneas, ver sección 9)
  forms.py            Formularios
  urls.py             Rutas de la app
  gemini_service.py   Toda la integración con IA (Gemini + Groq)
  auth_backends.py    Login con correo en vez de nombre de usuario
  middleware.py       Última actividad del usuario y tema visual (/pro/)
  context_processors.py  Datos que ven todos los templates (notificaciones, chat, etc.)
  admin.py            Configuración del /admin/ de Django
  management/commands/   migrar_archivos_software (migración puntual de datos antiguos)
  migrations/         Migraciones de base de datos
  tests/              Tests automáticos
templates/            HTML (base.html, proyectos/, registration/)
static/               CSS, imágenes, JS
media/                Archivos subidos por usuarios (no se versiona)
.github/workflows/    Despliegue a Azure (manual)
startup.sh            Comando de arranque en Azure
```

---

## 6. Modelo de datos (resumen)

- **Organizacion** → tiene **Areas** y **Usuarios**. Cada proyecto pertenece a una organización. Los datos se filtran por sede + organización del usuario.
- **Usuario** (modelo propio, `AUTH_USER_MODEL = proyectos.Usuario`): login por correo, rol, sede, organización, área, estado de registro.
- **Proyecto**: metodología `simple` o `trl`, TRL inicial/objetivo, responsables, creador, empresa externa opcional.
  - **ObjetivoEspecifico** → **ResultadoEsperado** → **IndicadorResultado**
  - **FaseProyecto** (fases TRL o fases de actividad), **Tarea**, **Avance**, **Observacion**, **Evidencia**
  - **RevisionIAEtapa**: lo que respondió la IA al revisar una etapa
- **Inventario**: **ItemInventario**, **UsoInventario**, **MovimientoStock**
- **Comunicación**: **MensajePrivado**, **GrupoChat**, **Notificacion**
- **Software**: **SoftwareConfiguracion**, **CarpetaArchivos**, **ArchivoAdjunto** (software estándar del laboratorio y sus archivos de configuración)

---

## 7. Roles y permisos

| Rol | Qué puede hacer |
| --- | --- |
| Administrador (`administrador`) / Admin de organización (`admin_organizacion`) | Gestionar usuarios de su organización, ver todos los proyectos de su organización, configurar la organización. |
| Profesor / Líder (`profesor`, `lider`) | Crear y llevar proyectos. |
| Alumno / Practicante / Integrante | Solo ven los proyectos donde son creadores o responsables. |
| Correos en `LAB_ADMIN_EMAILS` | Igual que administrador, además pueden eliminar proyectos y aprueban registros externos. |
| Superusuario de Django (`createsuperuser`) | Entra a `/admin/` y en la app actúa como administrador de **su** organización. |

**Registro de usuarios:** correos `@inacap.cl` / `@inacapmail.cl` reciben un código de verificación; los externos quedan pendientes hasta que un administrador del laboratorio los aprueba desde el enlace del correo.

Desde la app ya no se puede dar `is_staff` ni `is_superuser` a nadie; eso se hace solo desde `/admin/`.

---

## 8. Despliegue en Azure

El workflow `.github/workflows/main_trl-fablab.yml` despliega a la Web App **`trl-fablab`** usando credenciales guardadas como *secrets* del repositorio de GitHub.

- Ahora se ejecuta **solo a mano**: GitHub → *Actions* → *Build and deploy…* → *Run workflow*.
- Esos secrets y la suscripción de Azure pertenecen a la cuenta de la práctica anterior. Antes de desplegar, confirmen con el encargado del laboratorio si la Web App sigue existiendo y quién tiene acceso. Si no, creen la suya y regeneren el workflow desde el *Deployment Center* de Azure.
- **No reutilicen la base de datos de producción antigua.** Después de la práctica, esa base pudo recibir migraciones de una versión posterior que no está en este repositorio; mezclarla con este código puede romper la app. Usen una base nueva.
- En Azure, las variables de la sección 3 van en *Configuration → Application settings*. Además: `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_SITE_URL`, y `RUN_MIGRATIONS=true` si quieren que `startup.sh` aplique migraciones al arrancar.
- Comando de inicio de la Web App: `bash startup.sh`.
- Los archivos subidos (`media/`) se guardan en el disco de la Web App; si se recrea la app, se pierden. Mejora pendiente: moverlos a Azure Blob Storage.

---

## 9. Problemas conocidos y tareas sugeridas para empezar

1. **Test roto:** `proyectos/tests/test_software_configuracion.py::test_crear_software_con_archivo_config` usa el campo `archivo_configuracion`, que la migración 0039 eliminó. Hay que actualizar el test a `CarpetaArchivos`/`ArchivoAdjunto`. Los otros 65 tests pasan.
2. **`views.py` tiene ~3.800 líneas.** Conviene dividirlo por módulo (proyectos, inventario, usuarios, chat, IA, PDF).
3. **Datos de INACAP fijos en el código:** sedes (`Sede`: Puerto Montt / Osorno), dominios `@inacap.cl` en `forms.py`, alias de login `/login/inacap/`. Si se suma otra sede, hay que tocar código.
4. **Tema `/pro/` ("TrackFlow")**: existe un login y tema visual alternativo en `/pro/login/` (`middleware.py`, `static/css/tema_pro.css`). Decidan si se usa o se elimina.
5. **La IA corre en hilos de fondo** (`threading`) dentro del proceso web. Si el servidor se reinicia a mitad de la generación, se pierde. Mejora: cola de tareas (Celery, RQ o Django-Q).
6. **Nombres de modelos de IA** fijos por variable de entorno: revisar que sigan vigentes en Gemini y Groq.
7. **`requirements.txt`** trae `psycopg` 3 y `psycopg2-binary` a la vez; con uno basta.
8. **Archivos subidos en disco local** (ver sección 8).

---

## 10. Comandos útiles

```powershell
python manage.py check                 # revisar configuración
python manage.py test proyectos        # correr los tests
python manage.py makemigrations        # después de cambiar models.py
python manage.py migrate               # aplicar migraciones
python manage.py createsuperuser       # crear administrador
python manage.py runserver             # servidor local
```

Para correr los tests sin gastar cuota de IA, dejen `GEMINI_API_KEY` y `GROQ_API_KEY` vacías en el `.env` mientras corren.
