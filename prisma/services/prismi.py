"""
Prisma BMV - Asistente cuantitativo "Prismi".

Capas de control (defensa en profundidad):
1. Filtro de dominio local antes de llamar a la API (temas claramente externos).
2. Prompt de sistema con reglas estrictas y un CONTEXTO generado a partir de los datos
   reales del lakehouse: Prismi no inventa cifras ni resultados.
3. Filtro de salida: si la respuesta contiene órdenes de compra/venta, se reemplaza.
4. Respaldo local determinista cuando no hay ANTHROPIC_API_KEY, se agotó la cuota del plan
   o la API falla. Responde con las mismas cifras del contexto.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from prisma.data import analytics as an
from prisma.plans import PLANES

MENSAJE_FRONTERA = (
    "Mi alcance se limita a Prisma BMV: el PPP oficial, las 15 emisoras que monitoreamos, "
    "los modelos de 1ª y 2ª generación y el funcionamiento de la plataforma. "
    "No tengo información sobre temas externos."
)
MENSAJE_NO_ASESORIA = (
    "No doy recomendaciones de compra o venta. Lo que sí puedo hacer es explicarte qué "
    "probabilidad estadística asigna cada modelo y cómo se ha comportado la señal."
)
AVISO = "Probabilidades estadísticas; no constituyen asesoría de inversión."

_TEMAS_EXTERNOS = (
    "receta", "cocina", "futbol", "pelicula", "serie de tv", "cancion", "poema", "chiste",
    "politica", "elecciones", "presidente", "clima", "horoscopo", "bitcoin", "cripto",
    "ethereum", "tesla", "nvidia", "apple", "microsoft", "nasdaq", "s&p", "dow jones",
    "tarea", "ensayo", "traduce", "javascript",
)
_PIDE_ASESORIA = re.compile(
    r"\b(debo|deberia|conviene|me recomiendas|recomiendas|que hago)\b.*\b(comprar|vender|invertir|entrar|salir)\b"
    r"|\b(compro|vendo|invierto)\b",
)
_SALIDA_IMPERATIVA = re.compile(
    r"\b(compre|venda|compra ya|vende ya|le recomiendo (comprar|vender)|te recomiendo (comprar|vender)|"
    r"debes (comprar|vender))\b",
    re.IGNORECASE,
)


def _norm(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_acentos.lower().strip()


def es_tema_externo(pregunta: str) -> bool:
    p = _norm(pregunta)
    return any(re.search(rf"\b{re.escape(t)}", p) for t in _TEMAS_EXTERNOS)


def pide_asesoria(pregunta: str) -> bool:
    return bool(_PIDE_ASESORIA.search(_norm(pregunta)))


# ---------------------------------------------------------------------------
# Contexto a partir de datos reales
# ---------------------------------------------------------------------------
@dataclass
class ContextoMercado:
    texto: str
    por_emisora: dict[str, str]


def construir_contexto(precios: pd.DataFrame, g1: pd.DataFrame, g2: pd.DataFrame,
                       seg: pd.DataFrame, emisoras_visibles: tuple[str, ...]) -> ContextoMercado:
    lineas: list[str] = []
    por_emisora: dict[str, str] = {}
    if not precios.empty:
        f = precios["fecha"].max()
        k = an.kpis_sesion(precios[precios["fecha"] == f])
        lineas.append(f"Última sesión en el lakehouse: {f}. PPP verificados: {k['verificadas']} de {k['total']}; "
                      f"huecos documentados: {k['huecos']}.")
    if not g2.empty:
        ult = g2["fecha_senal"].max()
        for em, g in g2[g2["fecha_senal"] == ult].groupby("emisora"):
            if em not in emisoras_visibles:
                continue
            probs = ", ".join(f"{an.NOMBRES_MODELO.get(m, m)} {p * 100:.1f}%"
                              for m, p in zip(g["modelo_g2"], g["probabilidad_subida"]))
            cons = an.consenso_desde_clases(g["prediccion_clase"].astype(int).tolist())
            rel = g["ret_10_rel_panel"].iloc[0] * 100
            txt = (f"{em} (señal {ult}, objetivo {g['fecha_objetivo_h5'].iloc[0]}): PPP base "
                   f"${g['ppp_base_t'].iloc[0]:.2f}; consenso G2 {cons}; {probs}; "
                   f"ret_10_rel_panel {rel:+.2f} pp.")
            por_emisora[em] = txt
            lineas.append(txt)
    if not seg.empty:
        abiertas = seg[seg["acierto_parcial_en_curso"].notna()]
        for (em, f), g in abiertas.groupby(["emisora", "fecha_senal"]):
            if em not in emisoras_visibles:
                continue
            r = g.iloc[0]
            ok = int(g["acierto_parcial_en_curso"].sum())
            txt = (f"Seguimiento {em} señal {f}: {r['estado_resolucion']}, retorno parcial "
                   f"{r['retorno_parcial_pct']:+.2f}% al {r['fecha_parcial_reciente']}; "
                   f"{ok} de {len(g)} modelos van acertando.")
            por_emisora[em] = por_emisora.get(em, "") + " " + txt
            lineas.append(txt)
    if g1 is not None and not g1.empty:
        anuladas = g1[~g1["valida"]]
        if len(anuladas):
            lineas.append(f"Señales G1 anuladas por gobernanza: {', '.join(anuladas['id_senal'])}.")
    return ContextoMercado("\n".join(lineas) or "Sin datos cargados.", por_emisora)


def prompt_sistema(contexto: ContextoMercado, plan_id: str) -> str:
    return f"""Eres Prismi, el asistente cuantitativo de la plataforma Prisma BMV, una terminal de \
inteligencia cuantitativa sobre el mercado accionario mexicano. Respondes en español, con precisión y brevedad \
(máximo 180 palabras), en un tono profesional y cercano.

ALCANCE PERMITIDO: funcionamiento de Prisma BMV; el Precio Promedio Ponderado (PPP) oficial de la BMV; las 15 \
emisoras monitoreadas; los modelos de 1ª generación (WALMEX) y 2ª generación (panel WALMEX, GMEXICO, GFNORTE, AMX); \
variables como ret_10_rel_panel; consenso y divergencias; seguimiento t+1 a t+5; política de cero imputación; \
firmas SHA-256; la arquitectura de datos en AWS (S3, Lambda, EventBridge, Athena); y los planes Explorer, \
Professional y Enterprise.

REGLAS:
1. Si la pregunta está fuera del alcance, responde exactamente: "{MENSAJE_FRONTERA}"
2. Nunca des órdenes ni recomendaciones de compra, venta o inversión. Interpreta probabilidades \
estadísticas, por ejemplo: "El modelo G2-V3 asigna 54.9% de probabilidad de que el PPP a 5 sesiones supere \
al de hoy". Si te piden una recomendación, explica que no la das y ofrece la lectura estadística.
3. Usa solo las cifras del CONTEXTO. Si un dato no está, dilo; no lo inventes ni lo estimes.
4. No menciones instituciones educativas ni proyectos escolares.
5. El usuario tiene plan {PLANES.get(plan_id, PLANES['explorer']).nombre}; si pregunta por algo que su plan no \
incluye, explícalo sin insistir en vender.

CONTEXTO (datos del lakehouse, generados automáticamente):
{contexto.texto}
"""


# ---------------------------------------------------------------------------
# Motor local de respaldo
# ---------------------------------------------------------------------------
_RESPUESTAS_FIJAS = {
    ("ppp", "precio promedio"): (
        "El PPP (Precio Promedio Ponderado) es el precio oficial que publica la BMV ponderando el volumen de "
        "todas las operaciones de la sesión. A diferencia del último hecho, que puede moverse con pocas "
        "operaciones en el cierre, el PPP refleja dónde se negoció realmente el volumen del día."
    ),
    ("ret_10_rel", "relativo", "reversion"): (
        "ret_10_rel_panel es el retorno de 10 sesiones de la emisora menos el promedio del panel elegible ese día. "
        "Los modelos G2 tienen coeficiente negativo en esta variable: un rezago fuerte frente al panel eleva la "
        "probabilidad de subida (reversión a la media) y una sobreextensión la reduce."
    ),
    ("hueco", "imputa", "no publicada"): (
        "Cuando una emisora no aparece en el boletín del día se registra como NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA. "
        "No rellenamos ese precio. Si falta alguna de las 21 sesiones de la ventana, la emisora no recibe señal "
        "ese día, y si falta el PPP exactamente en t+5, la señal queda como no evaluable."
    ),
    ("sha", "hash", "firma", "integridad"): (
        "Cada boletín HTML se guarda tal cual en la capa Bronze de S3 junto con su SHA-256. Ese hash viaja con cada "
        "precio hasta Silver, de modo que cualquier cifra se puede rastrear hasta el archivo exacto del que salió."
    ),
    ("aws", "lambda", "athena", "s3", "eventbridge", "arquitectura"): (
        "EventBridge Scheduler dispara la Lambda recolector-diario-bmv a las 16:45 de lunes a viernes (hora de "
        "Ciudad de México). La Lambda guarda el boletín en Bronze, las 15 cotizaciones en Silver y las señales en "
        "Gold; Athena consulta Silver y Gold con SQL estándar."
    ),
    ("plan", "precio", "suscrip", "explorer", "professional", "enterprise"): (
        "Explorer ($0): boletín con una sesión de retraso y el modelo base de WALMEX. Professional ($49/mes): "
        "boletín al cierre, panel G2 completo, ret_10_rel_panel y Prismi ilimitado. Enterprise ($249/mes): además, "
        "consola SQL sobre Athena/S3, exportación masiva y auditoría forense SHA-256."
    ),
}


def responder_local(pregunta: str, contexto: ContextoMercado) -> str:
    p = _norm(pregunta)
    for em, txt in contexto.por_emisora.items():
        if em.lower() in p:
            return f"{txt.strip()} {AVISO}"
    if any(k in p for k in ("resultado", "acierto", "como van", "marcador")):
        seg = [t for t in contexto.texto.splitlines() if t.startswith("Seguimiento")]
        if seg:
            return " ".join(seg[:4]) + f" {AVISO}"
    for claves, resp in _RESPUESTAS_FIJAS.items():
        if any(k in p for k in claves):
            return resp
    return ("Puedo explicarte el PPP, la señal y el consenso de WALMEX, GMEXICO, GFNORTE o AMX, el seguimiento "
            "t+1 a t+5, la política de cero imputación o los planes. ¿Qué quieres revisar?")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
@dataclass
class RespuestaPrismi:
    texto: str
    origen: str  # CLAUDE | LOCAL | GUARDRAIL


def responder(pregunta: str, historial: list[dict[str, str]], contexto: ContextoMercado, plan_id: str,
              api_key: str, modelo: str, usar_claude: bool) -> RespuestaPrismi:
    pregunta = pregunta.strip()[:1500]
    if not pregunta:
        return RespuestaPrismi("Escribe tu pregunta sobre Prisma BMV.", "GUARDRAIL")
    if es_tema_externo(pregunta):
        return RespuestaPrismi(MENSAJE_FRONTERA, "GUARDRAIL")
    if pide_asesoria(pregunta):
        detalle = responder_local(pregunta, contexto)
        return RespuestaPrismi(f"{MENSAJE_NO_ASESORIA}\n\n{detalle}", "GUARDRAIL")

    if usar_claude and api_key:
        try:
            import anthropic

            cliente = anthropic.Anthropic(api_key=api_key, timeout=20.0, max_retries=1)
            mensajes = [m for m in historial[-6:] if m.get("role") in ("user", "assistant")]
            # La API exige que la conversación empiece con un turno del usuario.
            while mensajes and mensajes[0]["role"] != "user":
                mensajes.pop(0)
            mensajes.append({"role": "user", "content": pregunta})
            r = cliente.messages.create(
                model=modelo, max_tokens=700, system=prompt_sistema(contexto, plan_id), messages=mensajes,
            )
            texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
            if _SALIDA_IMPERATIVA.search(texto):
                return RespuestaPrismi(f"{MENSAJE_NO_ASESORIA}\n\n{responder_local(pregunta, contexto)}", "GUARDRAIL")
            return RespuestaPrismi(texto or responder_local(pregunta, contexto), "CLAUDE")
        except Exception:
            pass  # cae al motor local; el error no se muestra al usuario
    return RespuestaPrismi(responder_local(pregunta, contexto), "LOCAL")
