"""
Prisma BMV - Configuración General, Temas UI y Modelos de Negocio
"""

from __future__ import annotations

APP_NAME = "Prisma BMV"
APP_SUBTITLE = "Quantitative Terminal & Predictive Intelligence"
APP_TAGLINE = "Inteligencia Cuantitativa Institucional sobre la Bolsa Mexicana de Valores"

# Modelos de Planes Freemium
PLANS = {
    "explorer": {
        "id": "explorer",
        "name": "Explorer",
        "price": "$0 USD",
        "period": "Gratis para siempre",
        "badge": "FREEMIUM",
        "color": "#94A3B8",
        "description": "Para observadores del mercado y analistas junior.",
        "features": [
            "Boletín oficial BMV diferido de 15 emisoras",
            "Inferencia de 1ª Generación para WALMEX *",
            "Mascota interactiva Prismi (Tutorial básico)",
            "Auditoría básica de hashes criptográficos SHA-256",
        ],
        "excluded": [
            "Panel multiemisora de 2ª Generación (G2)",
            "Modelos avanzados (Calibrado, Zona Neutral, Expandido)",
            "Indicadores de retorno relativo (ret_10_rel_panel)",
            "Consultas directas en Amazon Athena",
        ],
    },
    "professional": {
        "id": "professional",
        "name": "Professional",
        "price": "$49 USD",
        "period": "por mes",
        "badge": "RECOMENDADO",
        "color": "#10B981",
        "description": "Para traders activos, analistas de casa de bolsa y family offices.",
        "features": [
            "Boletín oficial BMV al cierre diario (16:45 CDMX)",
            "Panel multiemisora completo G2 (WALMEX, GMEXICO, GFNORTE, AMX)",
            "Modelos G2: Calibrado, Zona Neutral y Alta Discriminación",
            "Indicador de reversión relativa (ret_10_rel_panel)",
            "Matriz de consenso prospectivo y alertas de divergencia",
            "Seguimiento temporal dinámico de acierto en curso (t+1 a t+5)",
            "Asistente Prismi ilimitado con Claude API",
        ],
        "excluded": [
            "Descarga masiva de Parquet crudo en Amazon S3",
            "Endpoints directos de consulta SQL en Amazon Athena",
        ],
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "price": "$249 USD",
        "period": "por mes o anual",
        "badge": "INSTITUCIONAL",
        "color": "#6366F1",
        "description": "Para mesas de dinero, fondos cuantitativos y tesorerías corporativas.",
        "features": [
            "Todo lo incluido en el plan Professional",
            "Acceso directo a tablas del Data Lakehouse en Amazon S3",
            "Endpoints de consulta SQL interactiva en Amazon Athena",
            "Verificación forense completa de hashes SHA-256",
            "Exportación de datos estructurados en Parquet, CSV y JSON",
            "Calibración a la medida del umbral de zona neutral (tau)",
            "Soporte cuantitativo dedicado 24/7",
        ],
        "excluded": [],
    },
}

# Estilos CSS inyectados para experiencia FinTech oscura institucional
FINTECH_CSS = """
<style>
/* Importacion de fuentes modernas */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Ocultar elementos nativos innecesarios de Streamlit */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Fondo y tarjetas oscuras */
.stApp {
    background: radial-gradient(circle at 15% 15%, #0d1527 0%, #080c14 100%);
    color: #F1F5F9;
}

/* Tarjetas ejecutivas con efecto vidrio (Glassmorphism) */
.fintech-card {
    background: rgba(17, 24, 39, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    backdrop-filter: blur(8px);
    transition: transform 0.2s ease, border-color 0.2s ease;
    margin-bottom: 16px;
}
.fintech-card:hover {
    border-color: rgba(16, 185, 129, 0.35);
    transform: translateY(-2px);
}

.kpi-title {
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94A3B8;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
}
.kpi-delta-up {
    color: #10B981;
    font-size: 0.9rem;
    font-weight: 600;
}
.kpi-delta-down {
    color: #EF4444;
    font-size: 0.9rem;
    font-weight: 600;
}

/* Insignias de Consenso */
.badge-consenso-subida {
    background-color: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border: 1px solid #10B981;
    padding: 6px 14px;
    border-radius: 9999px;
    font-weight: 700;
    font-size: 0.85rem;
    display: inline-block;
}
.badge-consenso-baja {
    background-color: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    border: 1px solid #EF4444;
    padding: 6px 14px;
    border-radius: 9999px;
    font-weight: 700;
    font-size: 0.85rem;
    display: inline-block;
}
.badge-consenso-alerta {
    background-color: rgba(245, 158, 11, 0.15);
    color: #F59E0B;
    border: 1px solid #F59E0B;
    padding: 6px 14px;
    border-radius: 9999px;
    font-weight: 700;
    font-size: 0.85rem;
    display: inline-block;
}

/* Animacion y estilo para Prismi la Grafica Bailarina */
@keyframes danceBounce {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    25% { transform: translateY(-8px) rotate(-4deg); }
    50% { transform: translateY(0px) rotate(0deg); }
    75% { transform: translateY(-6px) rotate(4deg); }
}

@keyframes candlePulse {
    0%, 100% { opacity: 0.9; filter: drop-shadow(0 0 8px rgba(16, 185, 129, 0.5)); }
    50% { opacity: 1; filter: drop-shadow(0 0 16px rgba(16, 185, 129, 0.8)); }
}

.prismi-avatar-dance {
    display: inline-block;
    animation: danceBounce 2.5s infinite ease-in-out;
    transform-origin: bottom center;
}

.prismi-glow {
    animation: candlePulse 2s infinite ease-in-out;
}
</style>
"""
