import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seguimiento.settings')
django.setup()

from django.contrib.auth import get_user_model
from proyectos.models import Sede
from proyectos.views import enviar_correo_simple, correo_html_inacap

Usuario = get_user_model()

def enviar_tutorial():
    # Fetch all active users in Puerto Montt sede
    usuarios = Usuario.objects.filter(sede=Sede.PUERTO_MONTT, is_active=True)
    if not usuarios.exists():
        print("No se encontraron usuarios activos en la sede Puerto Montt.")
        return

    print(f"Se encontraron {usuarios.count()} usuarios activos en la sede Puerto Montt.")
    
    asunto = "Tutorial de la Plataforma: ¡Aprende a usar Crea INACAP!"
    subtitulo = "Guía rápida para la gestión de proyectos de innovación y desarrollo"
    
    # HTML content for the tutorial email
    contenido = """
        <p style="margin:0 0 16px 0;">Hola,</p>
        <p style="margin:0 0 16px 0;">Queremos darte la bienvenida y explicarte cómo sacarle el máximo provecho a la plataforma <strong>Crea INACAP Puerto Montt</strong> para gestionar y hacer seguimiento de tus proyectos.</p>
        
        <h3 style="color:#cf3f4f;font-size:16px;margin:20px 0 10px 0;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">1. Dos Formas de Gestionar tus Proyectos</h3>
        <ul>
            <li style="margin-bottom:8px;"><strong>Proyecto Simple:</strong> Diseñado para un seguimiento ágil y directo. Puedes definir metas, objetivos específicos y tareas concretas de forma flexible.</li>
            <li style="margin-bottom:8px;"><strong>Proyecto TRL (Technology Readiness Level):</strong> Basado en el estándar de madurez tecnológica. El avance se evalúa mediante indicadores de cumplimiento en 4 grandes etapas:
                <ul>
                    <li><strong>Inicio (TRL 1-3):</strong> Planificación, definición de necesidades y primeras pruebas de concepto.</li>
                    <li><strong>Validación (TRL 4-5):</strong> Ensayos técnicos de laboratorio y validaciones en entornos simulados.</li>
                    <li><strong>Pruebas (TRL 6-7):</strong> Prototipos funcionales operando en entornos reales o semi-reales.</li>
                    <li><strong>Finalización (TRL 8-9):</strong> Sistemas completamente terminados, validados y listos para su implementación.</li>
                </ul>
            </li>
        </ul>

        <h3 style="color:#cf3f4f;font-size:16px;margin:20px 0 10px 0;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">2. Asistente con Inteligencia Artificial (IA)</h3>
        <p style="margin:0 0 16px 0;">Al crear tu proyecto, la IA de la plataforma lee automáticamente el título, descripción y objetivos principales. Con esa información, genera de forma personalizada una propuesta de ruta metodológica de etapas, metas e indicadores recomendados. ¡Sólo debes esperar unos segundos tras la creación y recargar la página para ver tu mesa de trabajo lista!</p>

        <h3 style="color:#cf3f4f;font-size:16px;margin:20px 0 10px 0;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">3. Campana de Notificaciones</h3>
        <p style="margin:0 0 16px 0;">En la esquina superior derecha verás un icono de <strong>Campanita (?)</strong>. Te alertará de forma inmediata cuando:
            <ul>
                <li style="margin-bottom:4px;">Se cree un nuevo proyecto en tu sede.</li>
                <li style="margin-bottom:4px;">Te asignen como responsable de algún proyecto.</li>
                <li style="margin-bottom:4px;">Te asignen una tarea específica.</li>
                <li style="margin-bottom:4px;">Se complete una etapa o hito importante de tu proyecto.</li>
            </ul>
        </p>

        <h3 style="color:#cf3f4f;font-size:16px;margin:20px 0 10px 0;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">4. Chats Grupales Colaborativos</h3>
        <p style="margin:0 0 16px 0;">Ahora puedes crear grupos de conversación con múltiples colegas y alumnos de tu misma sede para coordinar actividades del proyecto en tiempo real. Ve a la sección <strong>Chat</strong>, presiona el botón <strong>+ Nuevo Grupo</strong>, selecciona los integrantes y ¡listo!</p>

        <p style="margin:20px 0 0 0;font-weight:bold;color:#142033;">¡Comienza a explorar y gestionar tus proyectos hoy mismo!</p>
    """
    
    for u in usuarios:
        if not u.email:
            continue
        
        # Customize the welcome message with their name
        nombre_saludo = u.nombre or u.username
        contenido_personalizado = contenido.replace("<p style=\"margin:0 0 16px 0;\">Hola,</p>", f"<p style=\"margin:0 0 16px 0;\">Hola <strong>{nombre_saludo}</strong>,</p>")
        
        html_mensaje = correo_html_inacap(
            titulo=asunto,
            subtitulo=subtitulo,
            contenido=contenido_personalizado,
            boton_texto="Ir a la Plataforma",
            boton_url="http://127.0.0.1:8000/"
        )
        
        # Simple plain text fallback
        mensaje_texto = (
            f"Hola {nombre_saludo},\n\n"
            f"Te damos la bienvenida a Crea INACAP Puerto Montt.\n\n"
            f"1. Proyectos Simples y TRL: Gestiona mediante metas simples o avanza a través de niveles de madurez tecnológica (TRL 1-9).\n"
            f"2. Asistente con IA: Tu mesa de trabajo inicial se genera automáticamente tras la creación.\n"
            f"3. Campanita de Notificaciones: Recibe alertas en tiempo real al asignarse proyectos, tareas o completarse etapas.\n"
            f"4. Chats Grupales: Crea salas grupales para coordinar tu equipo de trabajo.\n\n"
            f"Ingresa a la plataforma aquí: http://127.0.0.1:8000/\n\n"
            f"Crea INACAP Puerto Montt"
        )
        
        enviado = enviar_correo_simple(
            asunto=asunto,
            destinatarios=[u.email],
            mensaje=mensaje_texto,
            html=html_mensaje
        )
        if enviado:
            print(f"Correo enviado exitosamente a {u.email} ({nombre_saludo})")
        else:
            print(f"No se pudo enviar el correo a {u.email} ({nombre_saludo})")

if __name__ == "__main__":
    enviar_tutorial()
