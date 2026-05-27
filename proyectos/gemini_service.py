import json
import urllib.error
import urllib.request

from django.conf import settings


RESPUESTA_FALLBACK = {
    "trl_estimado": "",
    "justificacion": "El asistente IA no esta disponible porque falta configurar GEMINI_API_KEY.",
    "recomendaciones": "Agrega la variable GEMINI_API_KEY en Azure o en el archivo .env local.",
    "tareas_sugeridas": [],
}

RESPUESTA_ETAPA_FALLBACK = {
    "trl_sugerido": "",
    "recomienda_avanzar": False,
    "confianza": "Sin evaluacion",
    "justificacion": "La validacion IA no esta disponible porque falta configurar GEMINI_API_KEY.",
    "faltantes": ["Configurar GEMINI_API_KEY en Azure o en el archivo .env local."],
    "acciones_sugeridas": [],
}


TRL_CONTEXTO = """
Eres un asistente IA integrado en una plataforma Django de seguimiento de proyectos FAB INACAP Puerto Montt.
Tu objetivo es orientar, no decidir automaticamente.

La pagina gestiona proyectos simples y proyectos con TRL.
En metodologia TRL, el avance depende de objetivos especificos, resultados esperados e indicadores asociados.
Cada resultado puede desbloquear un TRL objetivo cuando sus indicadores estan cumplidos.
La IA debe sugerir, justificar y advertir brechas, pero no debe marcar avances ni cambiar datos.

Escala TRL:
TRL 1: Principios basicos observados.
TRL 2: Concepto tecnologico formulado.
TRL 3: Prueba de concepto experimental.
TRL 4: Validacion en laboratorio.
TRL 5: Validacion en entorno relevante.
TRL 6: Prototipo demostrado en entorno relevante.
TRL 7: Prototipo demostrado en entorno real.
TRL 8: Sistema completo y validado.
TRL 9: Sistema probado con exito en entorno real.

Responde siempre en JSON valido con estas claves:
{
  "trl_estimado": "",
  "justificacion": "",
  "recomendaciones": "",
  "tareas_sugeridas": []
}
"""


ETAPA_IA_CONTEXTO = """
Eres un revisor tecnico IA dentro de una plataforma Django de proyectos FAB INACAP Puerto Montt.
Tu tarea es revisar una etapa de trabajo usando criterios, avances, evidencias, tareas y observaciones.
No puedes aprobar automaticamente ni modificar el proyecto. Solo recomiendas.

Evalua si la etapa tiene evidencia suficiente para sugerir avanzar al siguiente nivel o fase.
Si falta evidencia, avances, tareas o coherencia con el criterio, recomienda no avanzar todavia.
La decision final siempre la toma una persona responsable.

Responde siempre en JSON valido con estas claves:
{
  "trl_sugerido": "",
  "recomienda_avanzar": false,
  "confianza": "",
  "justificacion": "",
  "faltantes": [],
  "acciones_sugeridas": []
}
"""


def _normalizar_respuesta(datos):
    if not isinstance(datos, dict):
        return RESPUESTA_FALLBACK.copy()
    tareas = datos.get("tareas_sugeridas", [])
    if isinstance(tareas, str):
        tareas = [item.strip() for item in tareas.split("\n") if item.strip()]
    if not isinstance(tareas, list):
        tareas = []
    return {
        "trl_estimado": str(datos.get("trl_estimado", "")).strip(),
        "justificacion": str(datos.get("justificacion", "")).strip(),
        "recomendaciones": str(datos.get("recomendaciones", "")).strip(),
        "tareas_sugeridas": [str(tarea).strip() for tarea in tareas if str(tarea).strip()],
    }


def _normalizar_respuesta_etapa(datos):
    if not isinstance(datos, dict):
        return RESPUESTA_ETAPA_FALLBACK.copy()

    def lista(valor):
        if isinstance(valor, str):
            return [item.strip() for item in valor.split("\n") if item.strip()]
        if isinstance(valor, list):
            return [str(item).strip() for item in valor if str(item).strip()]
        return []

    recomienda = datos.get("recomienda_avanzar", False)
    if isinstance(recomienda, str):
        recomienda = recomienda.strip().lower() in {"1", "true", "si", "sí", "yes", "recomienda", "avanzar"}

    return {
        "trl_sugerido": str(datos.get("trl_sugerido", "")).strip(),
        "recomienda_avanzar": bool(recomienda),
        "confianza": str(datos.get("confianza", "")).strip(),
        "justificacion": str(datos.get("justificacion", "")).strip(),
        "faltantes": lista(datos.get("faltantes", [])),
        "acciones_sugeridas": lista(datos.get("acciones_sugeridas", [])),
    }


def _extraer_texto_gemini(respuesta):
    candidates = respuesta.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    textos = [part.get("text", "") for part in parts if part.get("text")]
    return "\n".join(textos).strip()


def _llamar_gemini(prompt):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return RESPUESTA_FALLBACK.copy()

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {
            "trl_estimado": "",
            "justificacion": "No fue posible conectar con Gemini en este momento.",
            "recomendaciones": f"Revisa la variable GEMINI_API_KEY, conexion de red o permisos de Azure. Detalle: {exc}",
            "tareas_sugeridas": [],
        }

    try:
        data = json.loads(raw)
        text = _extraer_texto_gemini(data)
        return _normalizar_respuesta(json.loads(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "trl_estimado": "",
            "justificacion": "Gemini respondio, pero la respuesta no venia como JSON valido.",
            "recomendaciones": "Intenta nuevamente o revisa el prompt del asistente.",
            "tareas_sugeridas": [],
        }


def _llamar_gemini_etapa(prompt):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return RESPUESTA_ETAPA_FALLBACK.copy()

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {
            "trl_sugerido": "",
            "recomienda_avanzar": False,
            "confianza": "Sin conexion",
            "justificacion": "No fue posible conectar con Gemini en este momento.",
            "faltantes": [f"Revisar conexion, permisos o GEMINI_API_KEY. Detalle: {exc}"],
            "acciones_sugeridas": [],
        }

    try:
        data = json.loads(raw)
        text = _extraer_texto_gemini(data)
        return _normalizar_respuesta_etapa(json.loads(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "trl_sugerido": "",
            "recomienda_avanzar": False,
            "confianza": "Sin evaluacion",
            "justificacion": "Gemini respondio, pero la respuesta no venia como JSON valido.",
            "faltantes": ["Intentar nuevamente o revisar el prompt del revisor IA."],
            "acciones_sugeridas": [],
        }


def _resumen_proyecto_modelo(proyecto):
    objetivos = []
    for objetivo in proyecto.objetivos.prefetch_related("resultados__indicadores").all():
        resultados = []
        for resultado in objetivo.resultados.all():
            resultados.append({
                "resultado": resultado.descripcion,
                "trl_objetivo": resultado.trl_objetivo,
                "estado": resultado.get_estado_display(),
                "plazo_meses": resultado.plazo_meses,
                "plazo_dias": resultado.plazo_dias,
                "indicadores": [
                    {
                        "indicador": indicador.descripcion,
                        "meta": indicador.meta,
                        "valor_actual": indicador.valor_actual,
                        "cumplido": indicador.cumplido,
                    }
                    for indicador in resultado.indicadores.all()
                ],
            })
        objetivos.append({
            "objetivo": objetivo.descripcion,
            "resultados": resultados,
        })

    return {
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "metodologia": proyecto.get_metodologia_display(),
        "usa_trl": proyecto.usa_trl,
        "trl_inicial": proyecto.trl_inicial,
        "trl_objetivo": proyecto.trl_objetivo,
        "trl_actual_sistema": proyecto.trl_actual if proyecto.usa_trl else "",
        "porcentaje_avance": proyecto.porcentaje_avance,
        "objetivo_principal": proyecto.objetivo_principal,
        "objetivos": objetivos,
        "tareas": [
            {"nombre": tarea.nombre, "estado": tarea.get_estado_display(), "descripcion": tarea.descripcion}
            for tarea in proyecto.tareas.all()[:20]
        ],
        "avances": [
            {"fecha": avance.fecha.isoformat(), "descripcion": avance.descripcion}
            for avance in proyecto.avances.all()[:20]
        ],
        "evidencias": [
            {"nombre": evidencia.nombre, "descripcion": evidencia.descripcion}
            for evidencia in proyecto.evidencias.all()[:20]
        ],
    }


def analizar_trl(proyecto):
    resumen = _resumen_proyecto_modelo(proyecto)
    prompt = f"{TRL_CONTEXTO}\n\nAnaliza este proyecto real del sistema:\n{json.dumps(resumen, ensure_ascii=False, indent=2)}"
    return _llamar_gemini(prompt)


def analizar_borrador_trl(datos):
    pregunta = str(datos.get("mensaje") or "").strip()
    instruccion = "Analiza este borrador escrito en el formulario Crear proyecto."
    if pregunta:
        instruccion += f"\nPregunta del usuario: {pregunta}"
    prompt = f"{TRL_CONTEXTO}\n\n{instruccion}\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    return _llamar_gemini(prompt)


def analizar_etapa_trl(datos):
    prompt = f"{ETAPA_IA_CONTEXTO}\n\nAnaliza esta etapa real del sistema:\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    return _llamar_gemini_etapa(prompt)
