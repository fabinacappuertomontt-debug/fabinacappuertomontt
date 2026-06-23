import os
import django
import sys
from datetime import date, timedelta

sys.path.append('c:/Users/diego/Documents/FabPuertomontt')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seguimiento.settings')
django.setup()

from proyectos.models import Proyecto, ObjetivoEspecifico, ResultadoEsperado, IndicadorResultado, Usuario
from proyectos.views import crear_fases_para_proyecto, generar_mesa_trabajo_inicial, sincronizar_trl_desde_resultados

try:
    # 1. Encontrar usuario para asignar como responsable/creador
    # Buscaremos el usuario diego eduardo o en su defecto el primero
    user = Usuario.objects.filter(username__icontains='diego').first() or Usuario.objects.filter(email__icontains='diego').first() or Usuario.objects.first()
    
    if not user:
        print("Error: No se encontró ningún usuario en la base de datos.")
        sys.exit(1)
        
    print(f"Asignando proyecto a usuario: {user.username} ({user.email})")

    # 2. Crear Proyecto
    proyecto = Proyecto.objects.create(
        nombre="CardioNet AI: Telemonitoreo Cardíaco IoT y Aprendizaje Profundo",
        descripcion="Sistema inteligente de monitoreo remoto de ECG en tiempo real con alertas basadas en redes neuronales profundas para detección temprana de arritmias.",
        metodologia=Proyecto.Metodologia.TRL,
        tipo_proyecto=Proyecto.TipoProyecto.TECNOLOGICO,
        trl_inicial=2,
        trl_objetivo=7,
        fecha_inicio=date.today(),
        fecha_fin=date.today() + timedelta(days=270),
        estado=Proyecto.Estado.PENDIENTE,
        creador=user,
        objetivo_principal="Validar un sistema de telemonitoreo cardíaco de grado experimental en un entorno clínico real (TRL 7).",
        sede=user.sede,
        organizacion=user.organizacion,
    )
    proyecto.responsables.add(user)
    
    # 3. Crear Fases de Proyecto
    crear_fases_para_proyecto(proyecto)
    
    # 4. Crear Objetivos, Resultados e Indicadores
    
    # Objetivo 1 (TRL 3)
    o1 = ObjetivoEspecifico.objects.create(proyecto=proyecto, descripcion="Diseñar la arquitectura del sistema CardioNet AI.", orden=1)
    r1 = ResultadoEsperado.objects.create(
        objetivo=o1, 
        descripcion="Arquitectura de hardware y software del sensor e integración con Bluetooth de bajo consumo definida.", 
        orden=1, 
        trl_objetivo=3,
        plazo_meses=2,
        plazo_dias=0
    )
    IndicadorResultado.objects.create(
        resultado=r1, 
        descripcion="Documento de arquitectura de hardware y software aprobado.", 
        orden=1, 
        meta="Aprobación del comité", 
        cumplido=False
    )
    IndicadorResultado.objects.create(
        resultado=r1, 
        descripcion="Simulaciones de circuitos de acondicionamiento de señal ECG validadas.", 
        orden=2, 
        meta="100% de simulaciones correctas", 
        cumplido=False
    )
    
    # Objetivo 2 (TRL 4)
    o2 = ObjetivoEspecifico.objects.create(proyecto=proyecto, descripcion="Desarrollar y validar el prototipo físico de hardware y firmware.", orden=2)
    r2 = ResultadoEsperado.objects.create(
        objetivo=o2, 
        descripcion="PCB del CardioNet ensamblado y firmware de lectura de ADC programado.", 
        orden=1, 
        trl_objetivo=4,
        plazo_meses=4,
        plazo_dias=0
    )
    IndicadorResultado.objects.create(
        resultado=r2, 
        descripcion="Dispositivo físico CardioNet v1.0 ensamblado y operativo.", 
        orden=1, 
        meta="1 prototipo físico funcional", 
        cumplido=False
    )
    IndicadorResultado.objects.create(
        resultado=r2, 
        descripcion="Firmware documentado capaz de transmitir tramas de ECG vía BLE.", 
        orden=2, 
        meta="Firmware subido y verificado", 
        cumplido=False
    )
    
    # Objetivo 3 (TRL 5)
    o3 = ObjetivoEspecifico.objects.create(proyecto=proyecto, descripcion="Desarrollar los algoritmos de IA y la plataforma web de monitoreo.", orden=3)
    r3 = ResultadoEsperado.objects.create(
        objetivo=o3, 
        descripcion="Modelo de clasificación de arritmias entrenado y dashboard de visualización operativo.", 
        orden=1, 
        trl_objetivo=5,
        plazo_meses=6,
        plazo_dias=0
    )
    IndicadorResultado.objects.create(
        resultado=r3, 
        descripcion="Modelo de Deep Learning con Accuracy superior al 92% en clasificación de latidos.", 
        orden=1, 
        meta="Accuracy >= 92%", 
        cumplido=False
    )
    IndicadorResultado.objects.create(
        resultado=r3, 
        descripcion="Dashboard web integrado recibiendo y graficando datos en tiempo real.", 
        orden=2, 
        meta="Plataforma operativa en servidor local", 
        cumplido=False
    )
    
    # Objetivo 4 (TRL 6)
    o4 = ObjetivoEspecifico.objects.create(proyecto=proyecto, descripcion="Integrar el sistema completo y validar en entorno relevante de laboratorio.", orden=4)
    r4 = ResultadoEsperado.objects.create(
        objetivo=o4, 
        descripcion="Pruebas de integración del sistema CardioNet y validación en laboratorio.", 
        orden=1, 
        trl_objetivo=6,
        plazo_meses=8,
        plazo_dias=0
    )
    IndicadorResultado.objects.create(
        resultado=r4, 
        descripcion="Informe de pruebas de integración (End-to-End) aprobado.", 
        orden=1, 
        meta="Pruebas de latencia y pérdida de paquetes válidas", 
        cumplido=False
    )
    
    # Objetivo 5 (TRL 7)
    o5 = ObjetivoEspecifico.objects.create(proyecto=proyecto, descripcion="Validar el sistema CardioNet AI en entorno operativo clínico.", orden=5)
    r5 = ResultadoEsperado.objects.create(
        objetivo=o5, 
        descripcion="Prueba piloto del sistema con pacientes bajo control médico.", 
        orden=1, 
        trl_objetivo=7,
        plazo_meses=9,
        plazo_dias=0
    )
    IndicadorResultado.objects.create(
        resultado=r5, 
        descripcion="Informe clínico de usabilidad firmado por médico especialista.", 
        orden=1, 
        meta="1 informe de usabilidad aprobado", 
        cumplido=False
    )
    IndicadorResultado.objects.create(
        resultado=r5, 
        descripcion="Prueba de funcionamiento continuo de 72 horas sin desconexión.", 
        orden=2, 
        meta="Stresstest aprobado", 
        cumplido=False
    )

    # 5. Generar mesa de trabajo inicial (crea tareas sugeridas y directrices de fase basadas en reglas)
    print("Generating workspace and tasks...")
    generar_mesa_trabajo_inicial(proyecto)
    
    # 6. Sincronizar TRL inicial
    sincronizar_trl_desde_resultados(proyecto)
    
    proyecto.refresh_from_db()
    
    print("\n==================================================")
    print(f"PROYECTO CREADO CON ÉXITO (ID: {proyecto.id})")
    print(f"Nombre: {proyecto.nombre}")
    print(f"TRL Inicial: {proyecto.trl_inicial} | Nivel Actual: {proyecto.nivel_actual}")
    print("Para probarlo, navega a los siguientes enlaces:")
    print(f"1. Detalle del Proyecto: http://127.0.0.1:8000/proyectos/{proyecto.id}/")
    print(f"2. Mesa de Trabajo (Inicio - TRL 3): http://127.0.0.1:8000/proyectos/{proyecto.id}/etapas/inicio/")
    print("==================================================")

except Exception as e:
    import traceback
    traceback.print_exc()
