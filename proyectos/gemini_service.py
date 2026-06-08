import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger("proyectos.ia")


RESPUESTA_FALLBACK = {
    "trl_estimado": "",
    "justificacion": "El asistente IA no esta disponible porque falta configurar GEMINI_API_KEY o GROQ_API_KEY.",
    "recomendaciones": "Agrega GEMINI_API_KEY o GROQ_API_KEY en Azure o en el archivo .env local.",
    "tareas_sugeridas": [],
}

RESPUESTA_ETAPA_FALLBACK = {
    "trl_sugerido": "",
    "recomienda_avanzar": False,
    "confianza": "Sin evaluacion",
    "justificacion": "La validacion IA no esta disponible porque falta configurar GEMINI_API_KEY o GROQ_API_KEY.",
    "faltantes": ["Configurar GEMINI_API_KEY o GROQ_API_KEY en Azure o en el archivo .env local."],
    "acciones_sugeridas": [],
}

PLAN_MESA_FALLBACK = {
    "ok": False,
    "origen": "fallback",
    "motivo": "Gemini y Groq no estan disponibles o no devolvieron una mesa valida.",
    "etapas": [],
}


TRL_CONTEXTO = """
Eres un asistente IA integrado en una plataforma Django de seguimiento de proyectos Crea INACAP Puerto Montt.
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
Eres un revisor tecnico IA dentro de una plataforma Django de proyectos Crea INACAP Puerto Montt.
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


MESA_TRABAJO_CONTEXTO = """
Eres un planificador técnico IA para una plataforma Django de seguimiento de proyectos de Crea INACAP.
El usuario ya completó el proyecto con su nombre, descripción, objetivo principal, objetivos específicos y resultados esperados. Tu tarea es generar la ruta de trabajo personalizada (las fases o etapas de desarrollo) y las tareas para la mesa de trabajo.

Reglas obligatorias:
1. Detecta si es un proyecto simple (usa_trl = False) o un proyecto tecnológico TRL (usa_trl = True).
2. Para Proyectos TRL:
   - Mantén los números de fase correspondientes a los niveles TRL solicitados en "fases_disponibles".
   - Genera un nombre y criterio de cumplimiento personalizado para cada nivel TRL que se adapte al contexto del proyecto (ej: en lugar de "Concepto tecnológico formulado", usa un nombre específico como "Prueba experimental del sensor de riego").
3. Para Proyectos Simples (no TRL):
   - Determina cuántas fases de desarrollo lógicas necesita el proyecto (mínimo 3, máximo 6). Asígnales números de fase secuenciales partiendo desde 1 (ej: 1, 2, 3, 4...).
   - Nombra cada fase de forma personalizada y profesional acorde al proyecto (ej: "Fase 1: Diseño del Prototipo", "Fase 2: Programación y Conexión de API").
   - Escribe un "criterio" claro de cumplimiento para cada fase, indicando qué se debe lograr para dar por finalizada la etapa.
4. Para cada fase (sea simple o TRL):
   - Genera entre 3 y 6 tareas concretas y accionables, directamente vinculadas al trabajo real del equipo para esa fase.
   - Especifica entre 1 y 3 evidencias sugeridas (archivos, capturas, informes, fotos) que demuestren el cumplimiento.

Responde siempre en JSON válido con esta estructura exacta:
{
  "etapas": [
    {
      "fase": 1,
      "nombre": "Nombre personalizado de la etapa",
      "criterio": "Descripción detallada del criterio de aceptación o logro de esta etapa",
      "tareas": [
        {
          "nombre": "Nombre corto de la tarea",
          "descripcion": "Descripción concreta de la actividad"
        }
      ],
      "evidencias_sugeridas": [
        "Tipo de archivo o registro que sirve como evidencia"
      ]
    }
  ]
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


def _normalizar_plan_mesa(datos, fases_validas):
    if not isinstance(datos, dict):
        return PLAN_MESA_FALLBACK.copy()
    fases_validas = {int(fase) for fase in fases_validas}
    etapas = []
    for etapa in datos.get("etapas", []):
        if not isinstance(etapa, dict):
            continue
        try:
            fase = int(etapa.get("fase") or etapa.get("trl") or 0)
        except (TypeError, ValueError):
            continue
        if fase not in fases_validas:
            continue
        tareas = []
        for tarea in etapa.get("tareas", []):
            if isinstance(tarea, str):
                nombre = tarea.strip()
                descripcion = ""
            elif isinstance(tarea, dict):
                nombre = str(tarea.get("nombre", "")).strip()
                descripcion = str(tarea.get("descripcion", "")).strip()
            else:
                continue
            if nombre:
                tareas.append({
                    "nombre": nombre[:180],
                    "descripcion": descripcion,
                })
        evidencias = etapa.get("evidencias_sugeridas", [])
        if isinstance(evidencias, str):
            evidencias = [item.strip() for item in evidencias.split("\n") if item.strip()]
        elif isinstance(evidencias, list):
            evidencias = [str(item).strip() for item in evidencias if str(item).strip()]
        else:
            evidencias = []
        etapas.append({
            "fase": fase,
            "nombre": str(etapa.get("nombre", "")).strip(),
            "criterio": str(etapa.get("criterio", "")).strip(),
            "tareas": tareas[:12],
            "evidencias_sugeridas": evidencias[:12],
        })
    if not etapas:
        return PLAN_MESA_FALLBACK.copy()
    return {
        "ok": True,
        "origen": "gemini",
        "motivo": "",
        "etapas": etapas,
    }


def _extraer_texto_gemini(respuesta):
    candidates = respuesta.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    textos = [part.get("text", "") for part in parts if part.get("text")]
    return "\n".join(textos).strip()


def _extraer_texto_groq(respuesta):
    choices = respuesta.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _limpiar_json_modelo(texto):
    texto = str(texto or "").strip()
    if texto.startswith("```"):
        texto = texto.strip("`").strip()
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()
    return texto


def _timeout_ia():
    return max(5, min(int(getattr(settings, "AI_TIMEOUT_SECONDS", 45)), 90))


def _respuesta_fallo_trl(respuesta):
    contenido = " ".join([
        str(respuesta.get("justificacion", "")),
        str(respuesta.get("recomendaciones", "")),
    ]).lower()
    return (
        not respuesta.get("trl_estimado")
        and (
            "api_key" in contenido
            or "no fue posible conectar" in contenido
            or "json valido" in contenido
            or "no está disponible" in contenido
            or "no esta disponible" in contenido
        )
    )


def _respuesta_fallo_etapa(respuesta):
    contenido = " ".join([
        str(respuesta.get("justificacion", "")),
        " ".join(str(item) for item in respuesta.get("faltantes", [])),
    ]).lower()
    return (
        not respuesta.get("trl_sugerido")
        and (
            "api_key" in contenido
            or "no fue posible conectar" in contenido
            or "json valido" in contenido
            or "no está disponible" in contenido
            or "no esta disponible" in contenido
        )
    )


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
        with urllib.request.urlopen(request, timeout=_timeout_ia()) as response:
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
        return _normalizar_respuesta(json.loads(_limpiar_json_modelo(text)))
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
        with urllib.request.urlopen(request, timeout=_timeout_ia()) as response:
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
        return _normalizar_respuesta_etapa(json.loads(_limpiar_json_modelo(text)))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "trl_sugerido": "",
            "recomienda_avanzar": False,
            "confianza": "Sin evaluacion",
            "justificacion": "Gemini respondio, pero la respuesta no venia como JSON valido.",
            "faltantes": ["Intentar nuevamente o revisar el prompt del revisor IA."],
            "acciones_sugeridas": [],
        }


def _llamar_gemini_mesa(prompt, fases_validas):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return PLAN_MESA_FALLBACK.copy()

    model = getattr(settings, "GEMINI_MODEL_PRO", "gemini-2.5-pro")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.18,
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
        with urllib.request.urlopen(request, timeout=_timeout_ia()) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Gemini mesa: error de red o timeout: %s", exc)
        return PLAN_MESA_FALLBACK.copy()

    try:
        data = json.loads(raw)
        text = _extraer_texto_gemini(data)
        return _normalizar_plan_mesa(json.loads(_limpiar_json_modelo(text)), fases_validas)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Gemini mesa: respuesta invalida: %s", exc)
        return PLAN_MESA_FALLBACK.copy()


def _llamar_groq_json(prompt, normalizador, fallback, temperature=0.2):
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        return fallback.copy()

    model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Responde solo JSON valido. No incluyas markdown ni texto fuera del JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_timeout_ia()) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        text = _extraer_texto_groq(data)
        return normalizador(json.loads(_limpiar_json_modelo(text)))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, TypeError):
        return fallback.copy()


def _llamar_groq(prompt):
    return _llamar_groq_json(prompt, _normalizar_respuesta, RESPUESTA_FALLBACK, temperature=0.2)


def _llamar_groq_etapa(prompt):
    return _llamar_groq_json(prompt, _normalizar_respuesta_etapa, RESPUESTA_ETAPA_FALLBACK, temperature=0.15)


def _llamar_groq_mesa(prompt, fases_validas):
    plan = _llamar_groq_json(
        prompt,
        lambda datos: _normalizar_plan_mesa(datos, fases_validas),
        PLAN_MESA_FALLBACK,
        temperature=0.18,
    )
    if plan.get("ok"):
        plan["origen"] = "groq"
    return plan

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
    respuesta = _llamar_gemini(prompt)
    if _respuesta_fallo_trl(respuesta):
        respuesta = _llamar_groq(prompt)
    return respuesta


def analizar_borrador_trl(datos):
    pregunta = str(datos.get("mensaje") or "").strip()
    instruccion = "Analiza este borrador escrito en el formulario Crear proyecto."
    if pregunta:
        instruccion += f"\nPregunta del usuario: {pregunta}"
    prompt = f"{TRL_CONTEXTO}\n\n{instruccion}\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    respuesta = _llamar_gemini(prompt)
    if _respuesta_fallo_trl(respuesta):
        respuesta = _llamar_groq(prompt)
    return respuesta


def analizar_etapa_trl(datos):
    prompt = f"{ETAPA_IA_CONTEXTO}\n\nAnaliza esta etapa real del sistema:\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    respuesta = _llamar_gemini_etapa(prompt)
    if _respuesta_fallo_etapa(respuesta):
        respuesta = _llamar_groq_etapa(prompt)
    return respuesta


def generar_mesa_trabajo_ia(proyecto, fases_validas):
    resumen = _resumen_proyecto_modelo(proyecto)
    resumen["fases_disponibles"] = list(fases_validas)
    prompt = f"{MESA_TRABAJO_CONTEXTO}\n\nCrea la mesa de trabajo inicial para este proyecto:\n{json.dumps(resumen, ensure_ascii=False, indent=2)}"
    logger.info("[IA] Generando mesa para proyecto %s (fases: %s)", proyecto.pk, fases_validas)
    plan = _llamar_gemini_mesa(prompt, fases_validas)
    if not plan.get("ok"):
        logger.warning("[IA] Gemini fallo para proyecto %s, intentando Groq...", proyecto.pk)
        plan = _llamar_groq_mesa(prompt, fases_validas)
        if not plan.get("ok"):
            logger.error("[IA] Groq tambien fallo para proyecto %s. Ambas IAs no respondieron.", proyecto.pk)
        else:
            logger.info("[IA] Groq exitoso para proyecto %s", proyecto.pk)
    else:
        logger.info("[IA] Gemini exitoso para proyecto %s", proyecto.pk)
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# GENERACIÓN IA: OBJETIVOS, RESULTADOS E INDICADORES DESDE FORMULARIO
# ──────────────────────────────────────────────────────────────────────────────

ESTRUCTURA_PROYECTO_CONTEXTO = """
Eres un planificador académico IA para la plataforma Crea INACAP Puerto Montt.
Tu tarea es crear la estructura de objetivos específicos, resultados esperados e indicadores
para un proyecto que acaba de ser registrado en el sistema.

Reglas obligatorias:
- Crea entre 1 y 3 objetivos específicos concretos y relevantes al proyecto.
- Cada objetivo debe tener entre 1 y 3 resultados esperados verificables.
- Cada resultado debe tener entre 1 y 2 indicadores medibles con una meta concreta.
- plazo_meses debe ser coherente con la duración total del proyecto (distribúyelo).
- Para proyectos con TRL: trl_objetivo de cada resultado debe ser un número entero
  entre trl_inicial y trl_objetivo del proyecto, distribuido progresivamente.
- Para proyectos simples (sin TRL): usa números de fase del 1 al 5 en trl_objetivo
  (1=Levantamiento, 2=Planificación, 3=Ejecución, 4=Validación, 5=Cierre).
- No inventes datos ni uses información fuera del contexto del proyecto.
- Si el proyecto es simple, NO menciones TRL en las descripciones.

Responde SOLO en JSON válido con esta estructura exacta:
{
  "objetivos": [
    {
      "descripcion": "texto del objetivo específico",
      "resultados": [
        {
          "descripcion": "texto del resultado esperado",
          "trl_objetivo": 3,
          "plazo_meses": 2,
          "indicadores": [
            {"descripcion": "texto del indicador", "meta": "valor o meta concreta medible"}
          ]
        }
      ]
    }
  ]
}
"""


def _normalizar_estructura_proyecto(datos):
    """Valida y normaliza la respuesta IA de estructura de proyecto."""
    if not isinstance(datos, dict):
        return {"ok": False, "objetivos": []}
    objetivos_out = []
    for obj_data in (datos.get("objetivos") or [])[:3]:
        if not isinstance(obj_data, dict):
            continue
        desc_obj = str(obj_data.get("descripcion") or "").strip()
        if not desc_obj:
            continue
        resultados_out = []
        for res_data in (obj_data.get("resultados") or [])[:3]:
            if not isinstance(res_data, dict):
                continue
            desc_res = str(res_data.get("descripcion") or "").strip()
            if not desc_res:
                continue
            try:
                trl_obj = max(1, min(9, int(res_data.get("trl_objetivo") or 1)))
            except (TypeError, ValueError):
                trl_obj = 1
            try:
                plazo_meses = max(0, min(36, int(res_data.get("plazo_meses") or 1)))
            except (TypeError, ValueError):
                plazo_meses = 1
            indicadores_out = []
            for ind_data in (res_data.get("indicadores") or [])[:3]:
                if isinstance(ind_data, str):
                    desc_ind, meta = ind_data.strip(), ""
                elif isinstance(ind_data, dict):
                    desc_ind = str(ind_data.get("descripcion") or "").strip()
                    meta = str(ind_data.get("meta") or "").strip()
                else:
                    continue
                if desc_ind:
                    indicadores_out.append({"descripcion": desc_ind[:400], "meta": meta[:200]})
            resultados_out.append({
                "descripcion": desc_res[:600],
                "trl_objetivo": trl_obj,
                "plazo_meses": plazo_meses,
                "indicadores": indicadores_out,
            })
        if resultados_out:
            objetivos_out.append({"descripcion": desc_obj[:600], "resultados": resultados_out})
    if not objetivos_out:
        return {"ok": False, "objetivos": []}
    return {"ok": True, "objetivos": objetivos_out}


def generar_estructura_proyecto_ia(proyecto):
    """Genera objetivos, resultados e indicadores con IA para un proyecto recién creado."""
    # Duracion en meses aproximada
    duracion_meses = 6
    if getattr(proyecto, "fecha_inicio", None) and getattr(proyecto, "fecha_fin", None):
        delta = (proyecto.fecha_fin - proyecto.fecha_inicio).days
        duracion_meses = max(1, round(delta / 30))

    resumen = {
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "objetivo_principal": getattr(proyecto, "objetivo_principal", ""),
        "metodologia": proyecto.get_metodologia_display(),
        "usa_trl": proyecto.usa_trl,
        "trl_inicial": proyecto.trl_inicial if proyecto.usa_trl else None,
        "trl_objetivo": proyecto.trl_objetivo if proyecto.usa_trl else None,
        "duracion_meses_estimada": duracion_meses,
    }
    prompt = (
        f"{ESTRUCTURA_PROYECTO_CONTEXTO}\n\n"
        f"Proyecto a estructurar:\n{json.dumps(resumen, ensure_ascii=False, indent=2)}"
    )

    # Intentar con Gemini
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if api_key:
        model = getattr(settings, "GEMINI_MODEL_PRO", "gemini-2.5-pro")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.22, "responseMimeType": "application/json"},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_timeout_ia()) as resp:
                raw = resp.read().decode("utf-8")
            text = _extraer_texto_gemini(json.loads(raw))
            resultado = _normalizar_estructura_proyecto(json.loads(_limpiar_json_modelo(text)))
            if resultado.get("ok"):
                return resultado
        except Exception:
            pass

    # Fallback a Groq
    return _llamar_groq_json(
        prompt,
        _normalizar_estructura_proyecto,
        {"ok": False, "objetivos": []},
        temperature=0.22,
    )


