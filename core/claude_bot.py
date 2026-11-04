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
1. TU ÚNICO DOMINIO: Responder sobre la plataforma Prisma BMV, el Precio Promedio Ponderado (PPP) oficial de la BMV, las 15 emisoras del IPC, la metodología de los modelos de 1ª Generación (Individuales WALMEX) y 2ª Generación (Panel Multiemisora: WALMEX, GMEXICO, GFNORTE, AMX), variables como ret_10_rel_panel, el estado de consenso y los planes de suscripción (Explorer, Professional, Enterprise).
2. FRONTERA INFRANQUEABLE: Si el usuario te pregunta sobre CUALQUIER tema ajeno a Prisma BMV (como recetas de cocina, películas, fútbol, política, tareas escolares, o acciones internacionales que no estén en la plataforma), DEBES DECLINAR AMABLEMENTE diciendo:
   'Disculpa, como asistente cuantitativo de Prisma BMV, mi conocimiento está estrictamente restringido a los modelos matemáticos, cotizaciones oficiales y funcionamiento de nuestra plataforma. No tengo información sobre temas externos.'
3. CERO ASESORÍA FINANCIERA IMPERATIVA: No digas 'debes comprar' o 'debes vender'; explica siempre las probabilidades estadísticas: 'El modelo G2_V3 asigna un 56.35% de probabilidad de subida basado en reversión a la media...'.
4. CERO MENCIONES ACADÉMICAS: Prisma BMV es una plataforma profesional institucional.
5. TONO: Ágil, riguroso, empático y profesional, con sutiles toques de personalidad alegre propios de una gráfica bailarina entusiasta de los datos bien estructurados.
"""

# Base de conocimiento local para contingencia (cuando no hay API Key)
BASE_CONOCIMIENTO_LOCAL = {
    "que es prisma bmv": (
        "¡Hola! Soy Prismi, la gráfica bailarina de **Prisma BMV**. Somos una terminal de "
        "inteligencia cuantitativa institucional que anticipa la dirección del Precio Promedio "
        "Ponderado (PPP) oficial de la Bolsa Mexicana de Valores a 5 sesiones hábiles ($t+5$), "
        "utilizando modelos de panel multivariado con estricta gobernanza de cero imputación y "
        "auditoría criptográfica SHA-256."
    ),
    "que es el ppp": (
        "El **PPP (Precio Promedio Ponderado)** es el precio oficial calculado por la BMV "
        "ponderando el volumen real de todas las operaciones de la jornada. A diferencia del "
        "precio de 'último hecho' (que puede ser manipulado en la subasta de cierre o por falta de liquidez), "
        "el PPP refleja el valor intrínseco real transaccionado en el mercado institucional."
    ),
    "como van los resultados": (
        "En nuestras señales vivas de finales de octubre de 2026: **GFNORTE** ha sido un éxito rotundo "
        "con 100% de aciertos parciales al anticipar la caída consecutiva (-1.90% acumulado). "
        "En **WALMEX**, el modelo base V1 y el retador G2_V3 capturaron exitosamente el rally alcista (+4.11%). "
        "En **GMEXICO**, los modelos detectaron sobreventa extrema y emitieron una fuerte señal de rebote."
    ),
    "que es ret_10_rel_panel": (
        "Es nuestra variable clave de **retorno relativo de mercado**. Calcula el rendimiento a 10 sesiones "
        "de una emisora menos el rendimiento promedio de las 4 emisoras del panel. Si este valor es muy "
        "negativo (como GMEXICO con -13.06%), el modelo detecta sobreventa y anticipa un rebote estadístico "
        "por reversión a la media."
    ),
    "cuales son los planes": (
        "Ofrecemos 3 niveles adaptados a cada necesidad institucional:\n"
        "- **Explorer ($0 USD):** Acceso al monitor BMV diferido e inferencia WALMEX G1.\n"
        "- **Professional ($49 USD/mes):** Acceso total al panel multiemisora G2 al cierre oficial, retornos relativos, semáforo de consenso y asistencia ilimitada conmigo.\n"
        "- **Enterprise ($249 USD/mes):** Acceso a tablas de S3/Athena, auditoría SHA-256 y exportación masiva."
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
