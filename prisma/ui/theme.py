"""
Prisma BMV - Sistema visual de la terminal.

Dirección: terminal de mercado. Grafito profundo, reglas finas de 1 px en lugar de
sombras, esquinas de 3 px, Inter para la interfaz y Roboto Mono para todo número,
ticker y hash. El naranja de marca se reserva para estructura y acciones; el verde y el
rojo solo codifican dirección de precio; el amarillo solo codifica divergencia.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

COLORES = {
    "fondo": "#0D1117",
    "panel": "#141A22",
    "panel_alto": "#1A222C",
    "regla": "#263040",
    "texto": "#E6EAF0",
    "tenue": "#8A93A3",
    "marca": "#FF9F1C",
    "sube": "#2EBD85",
    "baja": "#F0616D",
    "alerta": "#F5C542",
    "info": "#4CC3D9",
}
C = COLORES

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500;700&display=swap');

:root {{
  --fondo:{C['fondo']}; --panel:{C['panel']}; --panel-alto:{C['panel_alto']}; --regla:{C['regla']};
  --texto:{C['texto']}; --tenue:{C['tenue']}; --marca:{C['marca']};
  --sube:{C['sube']}; --baja:{C['baja']}; --alerta:{C['alerta']}; --info:{C['info']};
  --mono:'Roboto Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
/* Solo la raíz: los íconos de Streamlit usan su propia fuente (Material Symbols) y no deben heredarla. */
html, body, .stApp {{ font-family: var(--sans); }}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea {{ font-family: var(--sans); }}
.stApp {{ background: var(--fondo); color: var(--texto); }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 1.2rem; max-width: 1360px; }}
h1, h2, h3, h4 {{ font-family: var(--sans); letter-spacing: -0.01em; color: var(--texto); }}
code, .mono {{ font-family: var(--mono) !important; }}
a {{ color: var(--info); }}

/* Barra superior */
.pb-barra {{ display:flex; align-items:center; justify-content:space-between; gap:1rem;
  border-bottom:1px solid var(--regla); padding:0 0 .7rem 0; margin-bottom:.2rem; }}
.pb-marca {{ font-family:var(--mono); font-weight:700; font-size:1.05rem; letter-spacing:.14em; color:var(--marca); }}
.pb-marca small {{ color:var(--tenue); font-weight:400; letter-spacing:.02em; margin-left:.7rem; font-size:.78rem; }}
.pb-usuario {{ color:var(--tenue); font-size:.85rem; }}
.pb-usuario b {{ color:var(--texto); font-weight:600; }}
.pb-plan {{ font-family:var(--mono); font-size:.75rem; border:1px solid currentColor; border-radius:3px; padding:1px 7px; margin-left:.5rem; }}

/* Cinta de cotizaciones: el único elemento con movimiento autónomo */
.pb-cinta {{ overflow:hidden; white-space:nowrap; border-top:1px solid var(--regla); border-bottom:1px solid var(--regla);
  background:var(--panel); padding:.42rem 0; margin:.4rem 0 1.2rem 0; font-family:var(--mono); font-size:.82rem; }}
.pb-cinta-pista {{ display:inline-block; padding-left:100%; animation: pbCinta 70s linear infinite; }}
.pb-cinta:hover .pb-cinta-pista {{ animation-play-state: paused; }}
.pb-cinta span.it {{ margin-right:2.2rem; color:var(--texto); }}
.pb-cinta .tk {{ color:var(--tenue); margin-right:.45rem; }}
@keyframes pbCinta {{ from {{ transform:translateX(0); }} to {{ transform:translateX(-100%); }} }}
@media (prefers-reduced-motion: reduce) {{
  .pb-cinta-pista {{ animation:none; padding-left:0; }}
  .prismi-baile {{ animation:none !important; }}
}}

.sube {{ color:var(--sube); }} .baja {{ color:var(--baja); }} .alerta {{ color:var(--alerta); }} .tenue {{ color:var(--tenue); }}

/* Paneles y métricas */
.pb-panel {{ background:var(--panel); border:1px solid var(--regla); border-radius:3px; padding:.9rem 1rem; height:100%; }}
.pb-kpi-l {{ color:var(--tenue); font-size:.78rem; margin-bottom:.25rem; }}
.pb-kpi-v {{ font-family:var(--mono); font-size:1.55rem; font-weight:500; line-height:1.15; color:var(--texto); }}
.pb-kpi-s {{ font-family:var(--mono); font-size:.8rem; margin-top:.2rem; color:var(--tenue); }}
.pb-seccion {{ display:flex; align-items:baseline; gap:.8rem; border-bottom:1px solid var(--regla);
  padding-bottom:.35rem; margin:1.4rem 0 .8rem 0; }}
.pb-seccion h3 {{ font-size:1.02rem; font-weight:600; margin:0; }}
.pb-seccion span {{ color:var(--tenue); font-size:.82rem; }}
.pb-hash {{ font-family:var(--mono); font-size:.78rem; word-break:break-all; color:var(--texto); }}

/* Semáforo */
.pb-semaforo {{ display:flex; gap:.45rem; align-items:center; }}
.pb-luz {{ width:14px; height:14px; border-radius:50%; background:#232b36; border:1px solid var(--regla); }}
.pb-luz.on-sube {{ background:var(--sube); box-shadow:0 0 10px var(--sube); }}
.pb-luz.on-baja {{ background:var(--baja); box-shadow:0 0 10px var(--baja); }}
.pb-luz.on-alerta {{ background:var(--alerta); box-shadow:0 0 10px var(--alerta); }}
.pb-etq {{ font-family:var(--mono); font-size:.8rem; margin-left:.4rem; }}

/* Etiquetas de estado */
.pb-chip {{ font-family:var(--mono); font-size:.74rem; border-radius:3px; padding:2px 7px; border:1px solid; display:inline-block; }}
.pb-chip.sube {{ border-color:var(--sube); }} .pb-chip.baja {{ border-color:var(--baja); }}
.pb-chip.alerta {{ border-color:var(--alerta); }} .pb-chip.tenue {{ border-color:var(--regla); }}

/* Bloqueo por plan */
.pb-bloqueo {{ border:1px dashed var(--regla); border-left:3px solid var(--marca); border-radius:3px; padding:1.1rem 1.2rem; background:var(--panel); }}
.pb-bloqueo h4 {{ margin:0 0 .3rem 0; font-size:1rem; }}
.pb-bloqueo p {{ color:var(--tenue); margin:0; font-size:.9rem; }}

/* Portada */
.pb-hero h1 {{ font-size:2.6rem; line-height:1.08; font-weight:700; max-width:17ch; margin:.4rem 0 1rem 0; }}
.pb-hero p {{ color:var(--tenue); font-size:1.05rem; max-width:62ch; line-height:1.6; }}
.pb-precio {{ font-family:var(--mono); font-size:2rem; font-weight:500; }}
.pb-plan-col {{ border-top:2px solid var(--regla); padding-top:.9rem; }}
.pb-plan-col.destacado {{ border-top-color:var(--marca); }}
.pb-plan-col ul {{ padding-left:1.1rem; color:var(--texto); font-size:.9rem; line-height:1.7; }}
.pb-legal {{ color:var(--tenue); font-size:.78rem; line-height:1.55; border-top:1px solid var(--regla); padding-top:1rem; margin-top:3rem; max-width:90ch; }}

/* Prismi flotante (esquina inferior derecha) */
.st-key-prismi_flotante {{ position:fixed; right:1.4rem; bottom:1.3rem; z-index:1000; width:auto !important; }}
.st-key-prismi_flotante button {{ background:var(--panel-alto); border:1px solid var(--marca); color:var(--texto);
  font-family:var(--mono); border-radius:3px; }}
.prismi-baile {{ animation: prismiBaile 2.6s ease-in-out infinite; transform-origin: 50% 100%; display:inline-block; }}
@keyframes prismiBaile {{ 0%,100% {{ transform:translateY(0) rotate(0); }} 25% {{ transform:translateY(-5px) rotate(-4deg); }}
  75% {{ transform:translateY(-3px) rotate(4deg); }} }}
.prismi-msg {{ font-size:.88rem; line-height:1.5; padding:.45rem .6rem; border-radius:3px; margin-bottom:.4rem; }}
.prismi-msg.u {{ background:var(--panel-alto); }}
.prismi-msg.a {{ border-left:2px solid var(--marca); }}
.prismi-origen {{ font-family:var(--mono); font-size:.68rem; color:var(--tenue); }}

/* Pestañas y controles */
.stTabs [data-baseweb="tab-list"] {{ gap:0; border-bottom:1px solid var(--regla); }}
.stTabs [data-baseweb="tab"] {{ font-size:.9rem; padding:.55rem 1rem; }}
.stTabs [aria-selected="true"] {{ color:var(--marca) !important; }}
div[data-testid="stDataFrame"] {{ border:1px solid var(--regla); border-radius:3px; }}
:focus-visible {{ outline:2px solid var(--marca) !important; outline-offset:2px; }}
</style>
"""


def _plantilla_plotly() -> go.layout.Template:
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=C["texto"], size=12),
        xaxis=dict(gridcolor=C["regla"], zerolinecolor=C["regla"], linecolor=C["regla"],
                   tickfont=dict(family="Roboto Mono, monospace", size=11)),
        yaxis=dict(gridcolor=C["regla"], zerolinecolor=C["regla"], linecolor=C["regla"],
                   tickfont=dict(family="Roboto Mono, monospace", size=11)),
        hoverlabel=dict(bgcolor=C["panel_alto"], bordercolor=C["regla"],
                        font=dict(family="Roboto Mono, monospace", color=C["texto"])),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11)),
        colorway=[C["marca"], C["info"], C["sube"], C["baja"], C["alerta"], "#9AA4B5"],
    )
    return t


pio.templates["prisma"] = _plantilla_plotly()
PLANTILLA = "prisma"
