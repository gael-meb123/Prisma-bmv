"""
Prisma BMV - Asistente Cuantitativo Prismi (Claude API & Guardrails)
"""

from __future__ import annotations

import os
import urllib.request
import json
from typing import Any

SYSTEM_PROMPT = """Eres 'Prismi', la mascota y asistente cuantitativo oficial de la plataforma FinTech 'Prisma BMV'.
Tu apariencia es la de una simpática gráfica financiera viva y bailarina compuesta por velas bursátiles animadas.

REGLAS DE IDENTIDAD Y SEGURIDAD ESTRICTAS:
1. TU ÚNICO DOMINIO: Responder sobre la plataforma Prisma BMV, el Precio Promedio Ponderado (PPP) oficial de la BMV, las 15 emisoras del IPC, la metodología de los modelos de 1ª Generación (Individuales WALMEX) y 2ª Generación (Panel Multiemisora: WALMEX, GMEXICO, GFNORTE, AMX y FEMSA; modelos G2_V1 Calibrado, G2_V2 Zona Neutral, G2_V3 Alta Discriminación, G2_V4 Agotamiento Corto DM5, G2_V5 Adaptativo Régimen/Sector y G2_V4_F1_GAP con diferencial intradía UH-PPP), métricas institucionales (Brier Skill Score BSS, Rank IC, ECE, pendiente de calibración de Cox lambda_Cox, tamaño efectivo N_eff), la política de asignación de capital ¼-Kelly con matriz Ledoit-Wolf purgada (250d) y banda de inacción para superar fricción transaccional de 20 bps, el estado de consenso y los planes de suscripción (Explorer, Professional, Enterprise).
2. FRONTERA INFRANQUEABLE: Si el usuario te pregunta sobre CUALQUIER tema ajeno a Prisma BMV (como recetas de cocina, películas, fútbol, política, tareas escolares, o acciones internacionales que no estén en la plataforma), DEBES DECLINAR AMABLEMENTE diciendo:
   'Disculpa, como asistente cuantitativo de Prisma BMV, mi conocimiento está estrictamente restringido a los modelos matemáticos, cotizaciones oficiales y funcionamiento de nuestra plataforma. No tengo información sobre temas externos.'
3. CERO ASESORÍA FINANCIERA IMPERATIVA: No digas 'debes comprar' o 'debes vender'; explica siempre las probabilidades estadísticas: 'El modelo G2_V4_F1_GAP asigna una probabilidad calibrada basada en agotamiento a 5 sesiones y microestructura intradía...'.
4. CERO MENCIONES ACADÉMICAS: Prisma BMV es una plataforma profesional institucional.
5. TONO: Ágil, riguroso, empático y profesional, con sutiles toques de personalidad alegre propios de una gráfica bailarina entusiasta de los datos bien estructurados.
"""

# Base de conocimiento local para contingencia (cuando no hay API Key)
BASE_CONOCIMIENTO_LOCAL = {
    "que es prisma bmv": (
        "¡Hola! Soy Prismi, la gráfica bailarina de **Prisma BMV**. Somos una terminal de "
        "inteligencia cuantitativa institucional que anticipa la dirección del Precio Promedio "
        "Ponderado (PPP) oficial de la Bolsa Mexicana de Valores a 5 sesiones hábiles ($t+5$), "
        "utilizando un panel de 5 modelos de 2ª generación (`G2_V1` a `G2_V5` y `G2_V4_F1_GAP`) "
        "con estricta gobernanza de cero imputación, higiene de eventos corporativos y auditoría SHA-256."
    ),
    "que es el ppp": (
        "El **PPP (Precio Promedio Ponderado)** es el precio oficial calculado por la BMV "
        "ponderando el volumen real de todas las operaciones de la jornada. A diferencia del "
        "precio de 'último hecho' (que puede ser distorsionado en la subasta de cierre), "
        "el PPP refleja el valor intrínseco real transaccionado en el mercado institucional."
    ),
    "como van los resultados": (
        "En evaluación institucional fuera de muestra (`TEST`, $N=1,557$, $N_{\\text{eff}}=623.2$): "
        "**G2_V4_ADJ** alcanza **51.70%** de exactitud (`52.36%` en las emisoras foco, `BSS = +0.483%`, "
        "`ECE = 0.0123`, $\\lambda_{\\text{Cox}} = +0.533$), y al incorporar el diferencial intradía "
        "`gap_uh_ppp` (**G2_V4_F1_GAP**) sube a **52.60%** (`52.71%` en foco, `Rank IC = +0.0202`). "
        "En portafolio activo con **¼-Kelly** y costos de 20 bps, logra **+6.94% neto** (`Sharpe neto +1.04`, "
        "`Sharpe bruto +1.42`, `MaxDD -3.46%` y `Hit Rate 55.24%`)."
    ),
    "que es ret_10_rel_panel": (
        "Es nuestra variable estructural de **retorno relativo de mercado a 10 sesiones**. Calcula el rendimiento "
        "a 10 sesiones de una emisora menos el rendimiento promedio de las emisoras elegibles del panel. "
        "Complementada con `distancia_media_5_rel_panel` (en `G2_V4`) y `gap_uh_ppp` (en `G2_V4_F1_GAP`), "
        "captura reversiones de corto plazo y presión de subasta al cierre."
    ),
    "kelly": (
        "Nuestra política de asignación de capital (**Fase 5**) aplica **¼-Kelly multivariado** con "
        "matriz de covarianza de **Ledoit-Wolf purgada (250 sesiones)**, encogimiento de calibración "
        "previo a TEST ($\\lambda_0 = 0.2803$), banda de inacción $|\\Delta w_i| < 3\\%$ y tope de "
        "30% por emisora, superando la fricción de 20 bps ida y vuelta con un Hit Rate de **55.24%**."
    ),
    "cuales son los planes": (
        "Ofrecemos 3 niveles adaptados a cada necesidad institucional:\n"
        "- **Explorer ($0 USD):** Acceso al monitor BMV diferido e inferencia WALMEX.\n"
        "- **Professional ($49 USD/mes):** Acceso total al panel multiemisora G2 (`V1`–`V5` en las 15 emisoras), métricas institucionales (`BSS`, `IC`, `ECE`), pesos ¼-Kelly y asistencia conmigo.\n"
        "- **Enterprise ($199 USD/mes):** Acceso a tablas de S3/Athena, auditoría SHA-256 y exportación masiva."
    ),
}


def responder_con_claude(pregunta: str, historial: list[dict[str, str]] | None = None) -> str:
    """
    Envía la pregunta a la API de Claude (Anthropic). Si no hay API Key o falla la red,
    utiliza el motor de contingencia local con guardrails estrictos.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    
    if api_key:
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            
            mensajes = []
            if historial:
                for h in historial[-4:]:  # Ultimos 4 mensajes de contexto
                    mensajes.append({"role": h["role"], "content": h["content"]})
            mensajes.append({"role": "user", "content": pregunta})
            
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 600,
                "system": SYSTEM_PROMPT,
                "messages": mensajes,
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["content"][0]["text"]
        except Exception as e:
            # Fallback a local si hay timeout o error de API
            pass

    # Motor de contingencia local inteligente con Guardrails
    preg_clean = pregunta.strip().lower()
    
    # 1. Filtro estricto de frontera de dominio (Guardrails)
    palabras_prohibidas = [
        "receta", "cocina", "futbol", "pelicula", "cancion", "poema", "chiste",
        "politica", "elecciones", "tarea", "java", "javascript", "clima", "bitcoin",
        "cripto", "tesla", "apple", "nvidia", "meta", "google"
    ]
    if any(p in preg_clean for p in palabras_prohibidas):
        return (
            "Disculpa, como asistente cuantitativo oficial de **Prisma BMV**, mi conocimiento "
            "está estrictamente restringido a los modelos matemáticos, cotizaciones oficiales "
            "del mercado accionario mexicano y el funcionamiento de nuestra plataforma. "
            "No tengo información sobre temas externos."
        )

    # 2. Respuestas contextuales mapeadas
    for k, respuesta in BASE_CONOCIMIENTO_LOCAL.items():
        if k in preg_clean:
            return respuesta

    if "walmex" in preg_clean:
        return (
            "**WALMEX** cotizó en $50.39 MXN (+3.32% hoy, +4.11% acumulado). Tras romper la barrera de "
            "los 50 pesos, los modelos de 1ª y 2ª generación coinciden en un `CONSENSO_ALTO_NO_SUBIDA` "
            "anticipando una fase de consolidación técnica."
        )
    if "gmexico" in preg_clean:
        return (
            "**GMEXICO** cotizó en $224.31 MXN (-4.01% hoy). El panel G2 emitió un rotundo "
            "`CONSENSO_PANEL_G2_SUBIDA` (probabilidades entre 54.9% y 56.5%) debido a un rezago relativo "
            "extremo (-13.06% frente al mercado), proyectando un fuerte rebote estadístico."
        )
    if "gfnorte" in preg_clean:
        return (
            "**GFNORTE** cotizó en $209.04 MXN (-0.92%). Los modelos G2 predijeron con 100% de acierto "
            "su tendencia bajista continuada desde $213.09 MXN."
        )

    return (
        "Entendido. Como asistente de **Prisma BMV**, puedo explicarte la metodología del PPP, "
        "desglosar el consenso de los modelos de 1ª y 2ª generación para WALMEX, GMEXICO, GFNORTE y AMX, "
        "o detallarte nuestros planes de suscripción. ¿Sobre qué métrica te gustaría profundizar?"
    )
