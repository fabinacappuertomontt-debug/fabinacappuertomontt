"""Asistente conversacional de la creacion de proyectos.

Cada paso tiene su propio encargo: el asistente del paso de niveles TRL discute
madurez tecnologica, el de indicadores discute como medir. Un asistente generico
que opine de todo a la vez no ayuda a nadie.
"""

import json
import logging

from .gemini_service import (
    _con_marca,
    _limpiar_json_modelo,
    _llamar_groq_json,
    _texto_gemini,
)
from .models import ENTORNO_POR_TRL, TRL_DESCRIPCIONES

logger = logging.getLogger("proyectos.ia")

MAX_MENSAJES_DE_CONTEXTO = 8


BASE = """
Eres un asistente que acompana a un equipo de [ORGANIZACION] mientras crea un
proyecto en la plataforma. Hablas en espanol de Chile, tuteando, en tono cercano
y directo.

Reglas que no puedes romper:
- Responde corto: dos o tres frases, salvo que te pidan detalle.
- No inventes datos del proyecto. Si algo no esta escrito todavia, preguntalo.
- No hagas listas largas ni te vayas por las ramas.
- Si el equipo escribio algo que no calza con la metodologia, dilo con claridad
  pero sin sermonear.
- Nunca digas que vas a "guardar" o "modificar" cosas: tu solo orientas, quien
  escribe es el equipo.

Responde siempre en JSON valido:
{
  "respuesta": "",
  "sugerencias": []
}
donde "sugerencias" son 0 a 3 textos cortos que el equipo podria copiar tal cual
en el campo que esta llenando. Si no aplica, dejala vacia.
"""

ENCARGO_POR_PASO = {
    1: """
Estan en el primer paso: definir de que trata el proyecto y su objetivo
principal. Ayuda a que el nombre sea reconocible y a que el objetivo principal
sea una sola frase concreta, no una lista de intenciones. Si el proyecto suena a
desarrollo tecnologico que madura por etapas, sugiere seguimiento con TRL; si
suena a una actividad, un evento o una gestion, sugiere seguimiento simple.
""",
    2: """
Estan eligiendo desde que nivel TRL parte el proyecto y hasta cual quiere llegar.
Este es tu tema central: la escala mide madurez segun DONDE se valido, no cuanto
trabajo lleva hecho el equipo.

Si te describen lo que tienen hoy, estima el nivel y explica en una frase por
que. Se exigente con los saltos de entorno:
- Una idea o una revision bibliografica es TRL 1 o 2, no mas.
- Una prueba de concepto en el computador o en el banco es TRL 3.
- Componentes integrados y probados en laboratorio, TRL 4.
- Recien cuando se prueba en condiciones que simulan las reales se habla de
  TRL 5, y un taller propio no es un entorno relevante.
- TRL 7 exige el lugar y las condiciones de uso final, con usuarios reales.

Recuerdales que casi ningun proyecto parte en TRL 1 ni tiene que llegar a 9:
lo normal es un tramo de tres o cuatro niveles.
""",
    3: """
Estan escribiendo los objetivos especificos. Un objetivo especifico dice QUE se
quiere lograr, no como ni con que se mide. Ayuda a que sean pocos y distintos
entre si: dos o tres bien separados valen mas que seis que se repiten. Si te
piden ideas, proponlas en "sugerencias" listas para copiar.
""",
    4: """
Estan definiendo resultados esperados y como se comprueba cada uno.

Un resultado esperado tiene que poder darse por logrado o no logrado sin
discusion. Si te muestran uno vago ("mejorar el sistema"), ayudalos a
concretarlo.

Sobre los indicadores: un buen indicador dice como se va a comprobar el
resultado y de donde sale el dato. NO exijas que sea un numero. Muchos
indicadores validos son de si o no: "informe aprobado por la contraparte",
"prototipo operando en el centro de cultivo". Sugiere una cantidad solo cuando
salga natural del propio resultado, nunca por rellenar.

Cuando propongas indicadores en "sugerencias", escribe el nombre del indicador
tal cual se escribiria en el campo, sin explicaciones.
""",
    5: """
Estan revisando el proyecto antes de crearlo. Mira el conjunto y di si se
sostiene: si los resultados cubren el recorrido TRL declarado, si cada objetivo
tiene resultados y si los indicadores permiten comprobar de verdad lo que
prometen. Si algo no cierra, dilo concreto y breve.
""",
}


def _resumen_borrador(proyecto):
    """Lo que el asistente sabe del proyecto. Solo lo escrito, sin inventar."""
    datos = {
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "objetivo_principal": proyecto.objetivo_principal,
        "metodologia": proyecto.get_metodologia_display(),
        "usa_trl": proyecto.usa_trl,
    }

    if proyecto.usa_trl and proyecto.trl_inicial and proyecto.trl_objetivo:
        datos["recorrido_trl"] = {
            "parte_en": f"TRL {proyecto.trl_inicial}: {TRL_DESCRIPCIONES.get(proyecto.trl_inicial, '')}",
            "llega_a": f"TRL {proyecto.trl_objetivo}: {TRL_DESCRIPCIONES.get(proyecto.trl_objetivo, '')}",
            "entornos_que_exige": {
                f"TRL {trl}": texto
                for trl, texto in ENTORNO_POR_TRL.items()
                if proyecto.trl_inicial < trl <= proyecto.trl_objetivo
            },
        }

    objetivos = []
    for objetivo in proyecto.objetivos.prefetch_related("resultados__indicadores").order_by("orden"):
        objetivos.append(
            {
                "objetivo": objetivo.descripcion,
                "resultados": [
                    {
                        "resultado": resultado.descripcion,
                        "trl_que_desbloquea": resultado.trl_objetivo if proyecto.usa_trl else None,
                        "plazo": f"{resultado.plazo_meses} meses {resultado.plazo_dias} dias",
                        "indicadores": [ind.descripcion for ind in resultado.indicadores.all()],
                    }
                    for resultado in objetivo.resultados.all()
                ],
            }
        )
    datos["objetivos"] = objetivos
    datos["indicadores_ya_definidos"] = list(
        proyecto.indicadores_definidos.values_list("nombre", flat=True)
    )
    return datos


def _historial(proyecto, paso):
    """Ultimos mensajes del mismo paso, para que la conversacion tenga hilo."""
    mensajes = proyecto.mensajes_asistente.filter(paso=paso).order_by("-fecha")[
        :MAX_MENSAJES_DE_CONTEXTO
    ]
    return [
        {"quien": "equipo" if m.es_del_usuario else "asistente", "dijo": m.contenido}
        for m in reversed(list(mensajes))
    ]


def _normalizar(datos):
    if not isinstance(datos, dict):
        return {"respuesta": "", "sugerencias": []}
    sugerencias = datos.get("sugerencias")
    if not isinstance(sugerencias, list):
        sugerencias = []
    return {
        "respuesta": str(datos.get("respuesta", "")).strip(),
        "sugerencias": [str(s).strip() for s in sugerencias if str(s).strip()][:3],
    }


def responder(proyecto, paso, mensaje):
    """Contesta al equipo dentro del paso en el que esta trabajando."""
    encargo = ENCARGO_POR_PASO.get(paso, ENCARGO_POR_PASO[1])
    contexto = _con_marca(BASE, proyecto.organizacion) + encargo

    prompt = (
        f"{contexto}\n\n"
        f"Asi va el proyecto hasta ahora:\n"
        f"{json.dumps(_resumen_borrador(proyecto), ensure_ascii=False, indent=2)}\n\n"
        f"Conversacion previa en este paso:\n"
        f"{json.dumps(_historial(proyecto, paso), ensure_ascii=False, indent=2)}\n\n"
        f"El equipo dice ahora:\n{mensaje}"
    )

    try:
        texto = _texto_gemini(prompt, temperature=0.35, rapido=True)
        return _normalizar(json.loads(_limpiar_json_modelo(texto)))
    except Exception as exc:
        logger.warning("[IA] El asistente del paso %s fallo con Gemini: %s", paso, exc)

    respaldo = _llamar_groq_json(
        prompt, _normalizar, {"respuesta": "", "sugerencias": []}, temperature=0.35
    )
    if respaldo.get("respuesta"):
        return respaldo
    return {
        "respuesta": "No pude conectarme en este momento. Intenta de nuevo en unos segundos.",
        "sugerencias": [],
    }


def sugerir_indicadores(proyecto, resultado_texto, trl=None):
    """Propone indicadores para un resultado, sin exigir que sean numericos."""
    contexto = _con_marca(BASE, proyecto.organizacion) + ENCARGO_POR_PASO[4]
    detalle_trl = ""
    if trl:
        detalle_trl = (
            f"\nEl resultado desbloquea el TRL {trl}: {TRL_DESCRIPCIONES.get(int(trl), '')}."
            f"\nEse nivel exige: {ENTORNO_POR_TRL.get(int(trl), 'sin exigencia de entorno')}"
        )

    prompt = (
        f"{contexto}\n\n"
        f"Proyecto:\n{json.dumps(_resumen_borrador(proyecto), ensure_ascii=False, indent=2)}\n\n"
        f"El equipo escribio este resultado esperado:\n{resultado_texto}{detalle_trl}\n\n"
        "Propon en 'sugerencias' hasta tres indicadores para comprobarlo, escritos "
        "tal cual irian en el campo. En 'respuesta' explica en una frase que tienen "
        "en comun o que conviene mirar al elegir."
    )

    try:
        texto = _texto_gemini(prompt, temperature=0.3, rapido=True)
        return _normalizar(json.loads(_limpiar_json_modelo(texto)))
    except Exception as exc:
        logger.warning("[IA] No se pudieron sugerir indicadores: %s", exc)
        return {"respuesta": "", "sugerencias": []}
