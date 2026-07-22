"""Asistente de creacion de proyectos, paso a paso.

El formulario de una sola pagina pedia todo de una vez y era todo o nada: quien
lo abandonaba a la mitad perdia lo escrito. Aca cada paso guarda sobre un
borrador, se puede volver atras y los indicadores quedan en la base antes de
que el paso de resultados los ofrezca.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms_wizard import (
    IndicadorDelProyectoForm,
    ObjetivoEspecificoWizardForm,
    PasoIdentidadForm,
    PasoMadurezForm,
    ResultadoEsperadoWizardForm,
)
from .models import (
    IndicadorCatalogo,
    IndicadorResultado,
    MensajeAsistente,
    ObjetivoEspecifico,
    Proyecto,
    ResultadoEsperado,
    TipoIndicador,
)

PASOS = [
    (1, "El proyecto", "De qué se trata y quién lo lleva"),
    (2, "Punto de partida", "Desde qué nivel TRL parte y a cuál llega"),
    (3, "Objetivos", "Qué se quiere lograr"),
    (4, "Resultados", "Qué se espera y cómo se mide"),
    (5, "Revisión", "Confirmar y crear"),
]


def _pasos_visibles(proyecto):
    """Los proyectos simples no tienen paso de niveles TRL."""
    if proyecto is not None and not proyecto.usa_trl:
        return [paso for paso in PASOS if paso[0] != 2]
    return PASOS


def _paso_completo(proyecto, numero):
    """Si el contenido de ese paso esta realmente hecho.

    Se mira el dato, no por donde paso el usuario: haber abierto un paso no es
    haberlo completado, y marcarlo en verde antes de tiempo desorienta.
    """
    if proyecto is None:
        return False
    if numero == 1:
        return bool(proyecto.nombre and proyecto.descripcion)
    if numero == 2:
        return bool(proyecto.trl_inicial and proyecto.trl_objetivo)
    if numero == 3:
        return proyecto.objetivos.exists()
    if numero == 4:
        objetivos = list(proyecto.objetivos.prefetch_related("resultados__indicadores"))
        if not objetivos:
            return False
        for objetivo in objetivos:
            resultados = list(objetivo.resultados.all())
            if not resultados or any(not r.indicadores.exists() for r in resultados):
                return False
        return True
    # La revision solo se da por hecha cuando el proyecto queda creado.
    return False


def _contexto_pasos(proyecto, paso_actual):
    """Estado de cada circulo del indicador de progreso."""
    visibles = _pasos_visibles(proyecto)
    alcanzado = proyecto.paso_wizard if proyecto else 1
    items = []
    for numero, titulo, detalle in visibles:
        accesible = numero <= alcanzado
        if numero == paso_actual:
            estado = "actual"
        elif _paso_completo(proyecto, numero):
            estado = "completado"
        elif accesible:
            # Se puede entrar, pero todavia falta algo por hacer ahi.
            estado = "pendiente"
        else:
            estado = "bloqueado"
        items.append(
            {
                "numero": numero,
                "posicion": len(items) + 1,
                "titulo": titulo,
                "detalle": detalle,
                "estado": estado,
                "accesible": accesible,
            }
        )
    return items


def _siguiente_paso(proyecto, paso):
    numeros = [numero for numero, _, _ in _pasos_visibles(proyecto)]
    posicion = numeros.index(paso)
    return numeros[posicion + 1] if posicion + 1 < len(numeros) else paso


def _paso_anterior(proyecto, paso):
    numeros = [numero for numero, _, _ in _pasos_visibles(proyecto)]
    posicion = numeros.index(paso)
    return numeros[posicion - 1] if posicion > 0 else paso


def _borrador_del_usuario(request, pk):
    """Solo su autor puede seguir creando un borrador."""
    return get_object_or_404(
        Proyecto, pk=pk, creador=request.user, estado=Proyecto.Estado.BORRADOR
    )


def _marcar_avance(proyecto, paso):
    """Registra hasta donde llego, sin retroceder si vuelve atras a corregir."""
    alcanzado = max(proyecto.paso_wizard, paso)
    if alcanzado != proyecto.paso_wizard:
        proyecto.paso_wizard = alcanzado
        proyecto.save(update_fields=["paso_wizard"])


def _render(request, plantilla, proyecto, paso, extra=None):
    from .views import usuarios_de_sede

    contexto = {
        "proyecto": proyecto,
        "paso_actual": paso,
        "pasos": _contexto_pasos(proyecto, paso),
        "total_pasos": len(_pasos_visibles(proyecto)),
        "paso_anterior": _paso_anterior(proyecto, paso) if proyecto else None,
        "usuarios_disponibles": usuarios_de_sede(request.user),
        # El hilo vive en el borrador, asi que sobrevive al cambiar de paso.
        "mensajes_asistente": (
            proyecto.mensajes_asistente.filter(paso=paso) if proyecto else []
        ),
    }
    contexto.update(extra or {})
    return render(request, plantilla, contexto)


# ── Paso 1: el proyecto ───────────────────────────────────────────────────────


@login_required
def wizard_inicio(request):
    """Crea el borrador. Es el unico paso que funciona sin proyecto previo."""
    from .views import area_usuario, organizacion_usuario, sede_usuario, usuarios_de_sede

    form = PasoIdentidadForm(usuarios=usuarios_de_sede(request.user))
    if request.method == "POST":
        form = PasoIdentidadForm(request.POST, usuarios=usuarios_de_sede(request.user))
        if form.is_valid():
            with transaction.atomic():
                proyecto = form.save(commit=False)
                proyecto.estado = Proyecto.Estado.BORRADOR
                proyecto.sede = sede_usuario(request.user)
                proyecto.organizacion = organizacion_usuario(request.user)
                proyecto.area = area_usuario(request.user)
                proyecto.creador = request.user
                proyecto.tipo_proyecto = (
                    Proyecto.TipoProyecto.TECNOLOGICO
                    if proyecto.metodologia == Proyecto.Metodologia.TRL
                    else Proyecto.TipoProyecto.GENERAL
                )
                proyecto.paso_wizard = 1
                proyecto.save()
                form.save_m2m()
                proyecto.responsables.add(request.user)
            # Se desbloquea el paso siguiente antes de redirigir, si no el
            # guardia de wizard_paso devuelve al usuario al paso 1.
            siguiente = _siguiente_paso(proyecto, 1)
            _marcar_avance(proyecto, siguiente)
            return redirect("wizard_paso", pk=proyecto.pk, paso=siguiente)

    return _render(request, "proyectos/wizard/paso_identidad.html", None, 1, {"form": form})


@login_required
def wizard_paso(request, pk, paso):
    """Reparte cada paso a su manejador. Todos trabajan sobre el borrador."""
    proyecto = _borrador_del_usuario(request, pk)

    numeros = [numero for numero, _, _ in _pasos_visibles(proyecto)]
    if paso not in numeros:
        return redirect("wizard_paso", pk=proyecto.pk, paso=numeros[0])
    if paso > proyecto.paso_wizard:
        # No se puede saltar a un paso que todavia no se desbloquea.
        return redirect("wizard_paso", pk=proyecto.pk, paso=proyecto.paso_wizard)

    manejadores = {
        1: _paso_identidad,
        2: _paso_madurez,
        3: _paso_objetivos,
        4: _paso_resultados,
        5: _paso_revision,
    }
    return manejadores[paso](request, proyecto)


def _paso_identidad(request, proyecto):
    from .views import usuarios_de_sede

    usuarios = usuarios_de_sede(request.user)
    form = PasoIdentidadForm(instance=proyecto, usuarios=usuarios)
    if request.method == "POST":
        form = PasoIdentidadForm(request.POST, instance=proyecto, usuarios=usuarios)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.tipo_proyecto = (
                Proyecto.TipoProyecto.TECNOLOGICO
                if proyecto.metodologia == Proyecto.Metodologia.TRL
                else Proyecto.TipoProyecto.GENERAL
            )
            proyecto.save()
            form.save_m2m()
            _marcar_avance(proyecto, _siguiente_paso(proyecto, 1))
            return redirect("wizard_paso", pk=proyecto.pk, paso=_siguiente_paso(proyecto, 1))

    return _render(request, "proyectos/wizard/paso_identidad.html", proyecto, 1, {"form": form})


def _paso_madurez(request, proyecto):
    form = PasoMadurezForm(instance=proyecto)
    if request.method == "POST":
        form = PasoMadurezForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            _marcar_avance(proyecto, 3)
            return redirect("wizard_paso", pk=proyecto.pk, paso=3)

    return _render(request, "proyectos/wizard/paso_madurez.html", proyecto, 2, {"form": form})


def _paso_objetivos(request, proyecto):
    form = ObjetivoEspecificoWizardForm()
    if request.method == "POST":
        form = ObjetivoEspecificoWizardForm(request.POST)
        if form.is_valid():
            objetivo = form.save(commit=False)
            objetivo.proyecto = proyecto
            objetivo.orden = proyecto.objetivos.count() + 1
            objetivo.save()
            # Con al menos un objetivo ya tiene sentido pasar a los resultados.
            _marcar_avance(proyecto, 4)
            return redirect("wizard_paso", pk=proyecto.pk, paso=3)

    return _render(
        request,
        "proyectos/wizard/paso_objetivos.html",
        proyecto,
        3,
        {"form": form, "objetivos": proyecto.objetivos.order_by("orden")},
    )


def _paso_resultados(request, proyecto):
    form_resultado = ResultadoEsperadoWizardForm(proyecto=proyecto)
    form_indicador = IndicadorDelProyectoForm(proyecto=proyecto)

    if request.method == "POST":
        form_resultado = ResultadoEsperadoWizardForm(request.POST, proyecto=proyecto)
        form_indicador = IndicadorDelProyectoForm(request.POST, proyecto=proyecto)
        if form_resultado.is_valid() and form_indicador.is_valid():
            with transaction.atomic():
                resultado = form_resultado.save(commit=False)
                if not proyecto.usa_trl:
                    resultado.trl_objetivo = 1
                resultado.orden = (
                    ResultadoEsperado.objects.filter(objetivo=resultado.objetivo).count() + 1
                )
                resultado.save()
                _guardar_indicador(proyecto, resultado, form_indicador)
            # Con un resultado medido ya se puede ir a revisar.
            _marcar_avance(proyecto, 5)
            return redirect("wizard_paso", pk=proyecto.pk, paso=4)

    return _render(
        request,
        "proyectos/wizard/paso_resultados.html",
        proyecto,
        4,
        {
            "form_resultado": form_resultado,
            "form_indicador": form_indicador,
            "objetivos": proyecto.objetivos.prefetch_related(
                "resultados__indicadores"
            ).order_by("orden"),
            "indicadores_definidos": proyecto.indicadores_definidos.filter(activo=True),
        },
    )


def _guardar_indicador(proyecto, resultado, form):
    """Reutiliza el indicador elegido o crea uno nuevo para el proyecto."""
    entrada = form.cleaned_data.get("existente")
    if entrada is None:
        entrada = IndicadorCatalogo.objects.create(
            proyecto=proyecto,
            nombre=form.cleaned_data["nombre"].strip(),
            tipo=form.cleaned_data.get("tipo") or TipoIndicador.CUALITATIVO,
            unidad=form.cleaned_data.get("unidad", ""),
            medio_verificacion=form.cleaned_data.get("medio_verificacion", ""),
        )
        meta = form.cleaned_data.get("meta_valor")
        base = form.cleaned_data.get("linea_base")
    else:
        meta = form.cleaned_data.get("meta_valor")
        base = form.cleaned_data.get("linea_base")

    IndicadorResultado.objects.create(
        resultado=resultado,
        catalogo=entrada,
        descripcion=entrada.nombre,
        tipo=entrada.tipo,
        unidad=entrada.unidad,
        linea_base=base,
        meta_valor=meta,
        orden=1,
    )


def _paso_revision(request, proyecto):
    faltantes = _que_falta(proyecto)
    return _render(
        request,
        "proyectos/wizard/paso_revision.html",
        proyecto,
        5,
        {
            "objetivos": proyecto.objetivos.prefetch_related(
                "resultados__indicadores"
            ).order_by("orden"),
            "faltantes": faltantes,
            "puede_crear": not faltantes,
        },
    )


def _que_falta(proyecto):
    """Lo que impide crear el proyecto, en lenguaje de quien lo esta creando."""
    problemas = []
    objetivos = list(proyecto.objetivos.prefetch_related("resultados__indicadores"))

    if not objetivos:
        problemas.append("Falta agregar al menos un objetivo específico.")
        return problemas

    for objetivo in objetivos:
        resultados = list(objetivo.resultados.all())
        if not resultados:
            problemas.append(
                f"El objetivo «{objetivo.descripcion[:60]}» todavía no tiene resultados esperados."
            )
            continue
        for resultado in resultados:
            if not resultado.indicadores.exists():
                problemas.append(
                    f"El resultado «{resultado.descripcion[:60]}» no tiene indicador."
                )

    if proyecto.usa_trl:
        niveles = {r.trl_objetivo for o in objetivos for r in o.resultados.all()}
        for trl in range(proyecto.trl_inicial_efectivo + 1, proyecto.trl_objetivo_efectivo + 1):
            if trl not in niveles:
                problemas.append(
                    f"Ningún resultado desbloquea el TRL {trl}, así que el proyecto se "
                    f"quedaría trabado en ese nivel."
                )
    return problemas


@login_required
@require_POST
def wizard_publicar(request, pk):
    """Cierra la creacion: el borrador pasa a ser un proyecto de verdad."""
    from .views import (
        generar_mesa_trabajo_inicial,
        notificar_creador_proyecto,
        notificar_responsables_proyecto,
        sincronizar_avance_simple_desde_objetivos,
        sincronizar_trl_desde_resultados,
    )

    proyecto = _borrador_del_usuario(request, pk)
    faltantes = _que_falta(proyecto)
    if faltantes:
        messages.error(request, "Todavía falta algo para poder crear el proyecto.")
        return redirect("wizard_paso", pk=proyecto.pk, paso=5)

    proyecto.estado = Proyecto.Estado.EN_PROCESO
    proyecto.paso_wizard = 5
    proyecto.save(update_fields=["estado", "paso_wizard"])

    sincronizar_trl_desde_resultados(proyecto)
    sincronizar_avance_simple_desde_objetivos(proyecto)
    generar_mesa_trabajo_inicial(proyecto)
    notificar_creador_proyecto(request, proyecto)
    notificar_responsables_proyecto(request, proyecto)

    messages.success(request, f"«{proyecto.nombre}» quedó creado.")
    return redirect("proyecto_trabajo", pk=proyecto.pk)


@login_required
@require_POST
def wizard_asistente(request, pk):
    """Conversa con el equipo dentro del paso en el que esta trabajando."""
    from . import asistente_wizard

    proyecto = _borrador_del_usuario(request, pk)
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "No se pudo leer el mensaje."}, status=400)

    mensaje = str(datos.get("mensaje", "")).strip()
    if not mensaje:
        return JsonResponse({"ok": False, "error": "Escribe algo primero."}, status=400)

    try:
        paso = int(datos.get("paso") or 1)
    except (TypeError, ValueError):
        paso = 1

    # El mensaje del equipo se guarda aunque la IA falle: el hilo es del
    # proyecto, no de la respuesta.
    MensajeAsistente.objects.create(
        proyecto=proyecto, paso=paso, rol=MensajeAsistente.Rol.USUARIO, contenido=mensaje
    )
    salida = asistente_wizard.responder(proyecto, paso, mensaje)
    if salida.get("respuesta"):
        MensajeAsistente.objects.create(
            proyecto=proyecto,
            paso=paso,
            rol=MensajeAsistente.Rol.ASISTENTE,
            contenido=salida["respuesta"],
        )

    return JsonResponse({"ok": True, **salida})


@login_required
@require_POST
def wizard_sugerir_indicadores(request, pk):
    """Propone indicadores a partir del resultado que se esta escribiendo."""
    from . import asistente_wizard

    proyecto = _borrador_del_usuario(request, pk)
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "No se pudo leer el resultado."}, status=400)

    resultado = str(datos.get("resultado", "")).strip()
    if len(resultado) < 10:
        return JsonResponse(
            {"ok": False, "error": "Describe primero el resultado esperado."}, status=400
        )

    salida = asistente_wizard.analizar_resultado(proyecto, resultado, datos.get("trl"))
    return JsonResponse({"ok": True, **salida})


@login_required
@require_POST
def wizard_eliminar_objetivo(request, pk, objetivo_id):
    proyecto = _borrador_del_usuario(request, pk)
    get_object_or_404(ObjetivoEspecifico, pk=objetivo_id, proyecto=proyecto).delete()
    return redirect("wizard_paso", pk=proyecto.pk, paso=3)


@login_required
@require_POST
def wizard_eliminar_resultado(request, pk, resultado_id):
    proyecto = _borrador_del_usuario(request, pk)
    get_object_or_404(
        ResultadoEsperado, pk=resultado_id, objetivo__proyecto=proyecto
    ).delete()
    return redirect("wizard_paso", pk=proyecto.pk, paso=4)


@login_required
@require_POST
def wizard_descartar(request, pk):
    proyecto = _borrador_del_usuario(request, pk)
    nombre = proyecto.nombre
    proyecto.delete()
    messages.info(request, f"Se descartó el borrador «{nombre}».")
    return redirect("proyecto_lista")
