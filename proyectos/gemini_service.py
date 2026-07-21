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


# Se usa cuando el proyecto todavia no tiene organizacion; encaja en las frases
# "...de [ORGANIZACION]." sin nombrar a ninguna empresa.
MARCA_NEUTRA = "la organizacion usuaria"


def _con_marca(plantilla, organizacion=None):
    """Sustituye [ORGANIZACION] por el nombre real de la empresa.

    Se usa replace y no format porque las plantillas llevan llaves literales
    con los ejemplos de JSON que debe devolver el modelo.
    """
    nombre = (getattr(organizacion, "nombre", "") or "").strip() or MARCA_NEUTRA
    return plantilla.replace("[ORGANIZACION]", nombre)


TRL_CONTEXTO = """
Eres un asistente IA integrado en la plataforma de seguimiento de proyectos de [ORGANIZACION].
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

Si el usuario solicita generar/crear un proyecto desde cero, o si el formulario actual esta mayormente vacio y proporciona una idea o consulta de proyecto, debes proponer el borrador estructurado completo del proyecto.

Responde siempre en JSON valido con estas claves:
{
  "trl_estimado": "estimado del nivel TRL si aplica, o vacio",
  "justificacion": "explicacion/respuesta para el usuario",
  "recomendaciones": "consejos breves sobre la idea",
  "tareas_sugeridas": ["tarea 1", "tarea 2"],
  "formulario_sugerido": { // Incluir esta clave SOLO si la consulta del usuario es una idea para estructurar o si pide explicitamente rellenar/crear el proyecto
    "nombre": "Nombre creativo y profesional para el proyecto",
    "descripcion": "Descripcion detallada en 2 o 3 parrafos",
    "objetivo_principal": "Objetivo principal claro (debe iniciar con un verbo en infinitivo)",
    "trl_inicial": 1, // entero del 1 al 9, requerido solo si es metodologia TRL
    "trl_objetivo": 4, // entero del 1 al 9, requerido solo si es metodologia TRL
    "objetivos_especificos": [
      {
        "descripcion": "Objetivo especifico 1 (verbo infinitivo)",
        "resultados": [
          {
            "descripcion": "Resultado esperado 1 asociado al objetivo",
            "trl_objetivo": 2, // entero 1-9 si es TRL, o fase 1-5 si es Simple
            "plazo_meses": 2, // entero representativo del plazo sugerido en meses
            "dias": 0, // entero
            "observaciones": "Comentarios adicionales sobre el resultado",
            "indicadores": [
              {
                "descripcion": "Descripcion del indicador para medir el resultado",
                "meta": "Meta o valor objetivo concreto"
              }
            ]
          }
        ]
      }
    ]
  }
}
"""


ETAPA_IA_CONTEXTO = """
Eres un revisor tecnico IA dentro de la plataforma de proyectos de [ORGANIZACION].
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
Eres un planificador técnico IA para la plataforma de seguimiento de proyectos de [ORGANIZACION].
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


def _normalizar_formulario_sugerido(datos):
    if not isinstance(datos, dict):
        return None

    # 1. Campos basicos
    nombre = str(datos.get("nombre") or "").strip()
    descripcion = str(datos.get("descripcion") or "").strip()
    objetivo_principal = str(datos.get("objetivo_principal") or "").strip()

    if not nombre and not descripcion and not objetivo_principal:
        return None

    # 2. Campos TRL (opcionales)
    trl_inicial = datos.get("trl_inicial")
    if trl_inicial is not None:
        try:
            trl_inicial = int(trl_inicial)
        except (TypeError, ValueError):
            trl_inicial = None

    trl_objetivo = datos.get("trl_objetivo")
    if trl_objetivo is not None:
        try:
            trl_objetivo = int(trl_objetivo)
        except (TypeError, ValueError):
            trl_objetivo = None

    # 3. Objetivos especificos
    objetivos_raw = datos.get("objetivos_especificos") or datos.get("objetivos")
    if not isinstance(objetivos_raw, list):
        return None

    objetivos_out = []
    for obj_data in objetivos_raw:
        if not isinstance(obj_data, dict):
            continue
        desc_obj = str(obj_data.get("descripcion") or "").strip()
        if not desc_obj:
            continue

        resultados_raw = obj_data.get("resultados")
        if not isinstance(resultados_raw, list):
            resultados_raw = []

        resultados_out = []
        for res_data in resultados_raw:
            if not isinstance(res_data, dict):
                continue
            desc_res = str(res_data.get("descripcion") or "").strip()
            if not desc_res:
                continue

            # trl_objetivo de cada resultado (nivel TRL o numero de fase)
            trl_res = res_data.get("trl_objetivo") or res_data.get("trl")
            try:
                trl_res = int(trl_res) if trl_res is not None else 1
            except (TypeError, ValueError):
                trl_res = 1

            try:
                meses = max(0, min(36, int(res_data.get("plazo_meses") or res_data.get("meses") or 0)))
            except (TypeError, ValueError):
                meses = 0

            try:
                dias = max(0, min(30, int(res_data.get("dias") or 0)))
            except (TypeError, ValueError):
                dias = 0

            # Indicadores del resultado
            inds_raw = res_data.get("indicadores")
            if not isinstance(inds_raw, list):
                inds_raw = []

            inds_out = []
            for ind_data in inds_raw:
                if not isinstance(ind_data, dict):
                    continue
                desc_ind = str(ind_data.get("descripcion") or "").strip()
                meta_ind = str(ind_data.get("meta") or "").strip()
                if desc_ind or meta_ind:
                    inds_out.append({
                        "descripcion": desc_ind,
                        "meta": meta_ind,
                        "valor_actual": "",
                        "cumplido": False
                    })

            if not inds_out:
                inds_out.append({
                    "descripcion": "",
                    "meta": "",
                    "valor_actual": "",
                    "cumplido": False
                })

            resultados_out.append({
                "descripcion": desc_res,
                "trl": str(trl_res),
                "meses": meses,
                "dias": dias,
                "fecha_cumplimiento": "",
                "observaciones": str(res_data.get("observaciones") or "").strip(),
                "indicadores": inds_out
            })

        if not resultados_out:
            resultados_out.append({
                "descripcion": "",
                "trl": "",
                "meses": 0,
                "dias": 0,
                "fecha_cumplimiento": "",
                "observaciones": "",
                "indicadores": [{
                    "descripcion": "",
                    "meta": "",
                    "valor_actual": "",
                    "cumplido": False
                }]
            })

        objetivos_out.append({
            "descripcion": desc_obj,
            "resultados": resultados_out
        })

    if not objetivos_out:
        return None

    return {
        "nombre": nombre,
        "descripcion": descripcion,
        "objetivo_principal": objetivo_principal,
        "trl_inicial": trl_inicial,
        "trl_objetivo": trl_objetivo,
        "objetivos_especificos": objetivos_out
    }


def _normalizar_respuesta(datos):
    if not isinstance(datos, dict):
        return RESPUESTA_FALLBACK.copy()
    tareas = datos.get("tareas_sugeridas", [])
    if isinstance(tareas, str):
        tareas = [item.strip() for item in tareas.split("\n") if item.strip()]
    if not isinstance(tareas, list):
        tareas = []
    res = {
        "trl_estimado": str(datos.get("trl_estimado", "")).strip(),
        "justificacion": str(datos.get("justificacion", "")).strip(),
        "recomendaciones": str(datos.get("recomendaciones", "")).strip(),
        "tareas_sugeridas": [str(tarea).strip() for tarea in tareas if str(tarea).strip()],
    }
    form_sugerido = datos.get("formulario_sugerido")
    if form_sugerido:
        res["formulario_sugerido"] = _normalizar_formulario_sugerido(form_sugerido)
    return res


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
    contexto = _con_marca(TRL_CONTEXTO, getattr(proyecto, "organizacion", None))
    prompt = f"{contexto}\n\nAnaliza este proyecto real del sistema:\n{json.dumps(resumen, ensure_ascii=False, indent=2)}"
    respuesta = _llamar_gemini(prompt)
    if _respuesta_fallo_trl(respuesta):
        respuesta = _llamar_groq(prompt)
    return respuesta


def analizar_borrador_trl(datos, organizacion=None):
    pregunta = str(datos.get("mensaje") or "").strip()
    metodologia = str(datos.get("metodologia") or "").strip().lower()

    instruccion = "Analiza este borrador escrito en el formulario Crear proyecto."
    if metodologia:
        instruccion += f"\nMetodologia del proyecto a usar/generar: {metodologia}."
    if pregunta:
        instruccion += f"\nMensaje/Idea del usuario: {pregunta}"
        instruccion += (
            "\nIMPORTANTE: Si el usuario describe una idea, realiza una consulta sobre como estructurar "
            "su proyecto o pide explicitamente completarlo, DEBES generar la estructura de 'formulario_sugerido' "
            "siguiendo el esquema especificado en el contexto, adaptandola a la metodologia elegida."
        )
    contexto = _con_marca(TRL_CONTEXTO, organizacion)
    prompt = f"{contexto}\n\n{instruccion}\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    respuesta = _llamar_gemini(prompt)
    if _respuesta_fallo_trl(respuesta):
        respuesta = _llamar_groq(prompt)
    return respuesta


def analizar_etapa_trl(datos, organizacion=None):
    contexto = _con_marca(ETAPA_IA_CONTEXTO, organizacion)
    prompt = f"{contexto}\n\nAnaliza esta etapa real del sistema:\n{json.dumps(datos, ensure_ascii=False, indent=2)}"
    respuesta = _llamar_gemini_etapa(prompt)
    if _respuesta_fallo_etapa(respuesta):
        respuesta = _llamar_groq_etapa(prompt)
    return respuesta


def generar_mesa_trabajo_ia(proyecto, fases_validas):
    resumen = _resumen_proyecto_modelo(proyecto)
    resumen["fases_disponibles"] = list(fases_validas)
    contexto = _con_marca(MESA_TRABAJO_CONTEXTO, getattr(proyecto, "organizacion", None))
    prompt = f"{contexto}\n\nCrea la mesa de trabajo inicial para este proyecto:\n{json.dumps(resumen, ensure_ascii=False, indent=2)}"
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
Eres un planificador académico IA para la plataforma de [ORGANIZACION].
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
    contexto = _con_marca(ESTRUCTURA_PROYECTO_CONTEXTO, getattr(proyecto, "organizacion", None))
    prompt = (
        f"{contexto}\n\n"
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


# ──────────────────────────────────────────────────────────────────────────────
# SUGERENCIA DE TAREAS CON IA PARA ETAPAS DE TRABAJO
# ──────────────────────────────────────────────────────────────────────────────

TAREAS_ETAPA_CONTEXTO = """
Eres un planificador técnico IA para la plataforma de proyectos de [ORGANIZACION].
Tu tarea es generar sugerencias de tareas concretas y de corta duración para una fase de trabajo específica de un proyecto.

Proyecto:
- Nombre: {nombre_proyecto}
- Descripción: {descripcion_proyecto}
- Objetivo Principal: {objetivo_principal}

Fase/Etapa Actual:
- Nombre: {nombre_fase}
- Criterio de Logro: {objetivo_fase}

Genera entre 3 y 5 tareas concretas, realistas y directamente orientadas a que el equipo de trabajo cumpla con el criterio de logro de esta fase.
Cada tarea debe tener un nombre corto y claro (máximo 80 caracteres) y una descripción opcional muy breve (máximo 200 caracteres).

Responde únicamente en formato JSON con la siguiente estructura exacta:
{{
  "tareas": [
    {{
      "nombre": "Nombre de la tarea",
      "descripcion": "Breve descripción de la actividad"
    }}
  ]
}}
"""

def generar_tareas_etapa_ia(proyecto, fase):
    prompt = _con_marca(TAREAS_ETAPA_CONTEXTO, getattr(proyecto, "organizacion", None)).format(
        nombre_proyecto=proyecto.nombre,
        descripcion_proyecto=proyecto.descripcion,
        objetivo_principal=proyecto.objetivo_principal,
        nombre_fase=fase.nombre,
        objetivo_fase=fase.objetivo
    )
    
    def normalizador(datos):
        if not isinstance(datos, dict):
            return {"tareas": []}
        tareas_raw = datos.get("tareas")
        if not isinstance(tareas_raw, list):
            return {"tareas": []}
        tareas_out = []
        for t in tareas_raw:
            if not isinstance(t, dict):
                continue
            nombre = str(t.get("nombre") or "").strip()
            desc = str(t.get("descripcion") or "").strip()
            if nombre:
                tareas_out.append({
                    "nombre": nombre[:200],
                    "descripcion": desc[:400]
                })
        return {"tareas": tareas_out}

    # Intentar con Gemini
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if api_key:
        model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
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
            return normalizador(json.loads(_limpiar_json_modelo(text)))
        except Exception as e:
            logger.warning("[IA] Error llamando a Gemini para sugerencia de tareas: %s", e)

    # Fallback a Groq
    return _llamar_groq_json(
        prompt,
        normalizador,
        {"tareas": []},
        temperature=0.2,
    )



