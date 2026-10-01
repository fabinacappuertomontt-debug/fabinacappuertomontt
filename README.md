# Seguimiento de Proyectos — FAB INACAP Puerto Montt

Aplicación web en Django para dar seguimiento a los proyectos del laboratorio: proyectos simples y TRL, objetivos e indicadores, fases, tareas, avances, evidencias, inventario, chat interno, exportación a PDF y un asistente de IA (Gemini / Groq).

**Documentación técnica completa (léanla primero): [docs/DOCUMENTACION_TECNICA.md](docs/DOCUMENTACION_TECNICA.md)**

## Antes de empezar: claves que tienen que poner ustedes

El repositorio no trae ninguna clave. Copien `.env.example` a `.env` y completen:

| Servicio | Variables | Dónde se obtiene |
| --- | --- | --- |
| IA principal (Gemini) | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| IA de respaldo (Groq, opcional) | `GROQ_API_KEY` | https://console.groq.com/keys |
| Correo (Brevo) | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | https://www.brevo.com → *SMTP & API* |
| Django | `SECRET_KEY` | Generarla (comando en `.env.example`) |
| Base de datos | `POSTGRES_*` | Su PostgreSQL local |

Para desarrollar no hace falta Brevo: con el backend de consola los correos salen impresos en la terminal. Sin claves de IA la app funciona igual, pero sin el asistente.

El paso a paso de cada servicio está en la [sección 3 de la documentación](docs/DOCUMENTACION_TECNICA.md#3-lo-que-tienen-que-configurar-ustedes-claves-y-servicios).

## Inicio rápido

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # y completar los valores
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Después de `createsuperuser`, entren a `/admin/` y asignen al usuario una organización, un área y el rol Administrador (detalle en la [sección 4](docs/DOCUMENTACION_TECNICA.md#4-levantar-el-proyecto-en-local)).

## Estado

Se entrega la versión del final de la práctica (julio 2026), sin el panel de superadmin. Hay una lista de problemas conocidos y tareas sugeridas en la [sección 9](docs/DOCUMENTACION_TECNICA.md#9-problemas-conocidos-y-tareas-sugeridas-para-empezar).

El despliegue a Azure es manual; lean la [sección 8](docs/DOCUMENTACION_TECNICA.md#8-despliegue-en-azure) antes de desplegar.
