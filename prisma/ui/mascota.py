"""
Prismi, el billete superhéroe de Prisma BMV, en versión Streamlit.

Es el mismo personaje del sitio web (frontend/src/components/Mascot.jsx y mascot.css),
traducido a una cadena SVG para `st.markdown(..., unsafe_allow_html=True)`.
No importa Streamlit: solo genera HTML y CSS.
"""

from __future__ import annotations

from html import escape
from itertools import count

EXPRESIONES = ("happy", "idle", "thinking", "unsure", "surprised")
POSES = ("idle", "wave", "point-left", "point-right", "point-up", "point-down", "fly", "cheer")

_BOCAS = {
    "happy": '<path d="M53 53 Q60 61.5 67 53 Z" fill="#7F1D1D" stroke="#0B1020" stroke-width="1.6" stroke-linejoin="round"/>',
    "idle": '<path d="M54 54.5 Q60 58 66 54.5" fill="none" stroke="#0B1020" stroke-width="2" stroke-linecap="round"/>',
    "thinking": '<path d="M56 56 Q60 54.6 64.5 56.4" fill="none" stroke="#0B1020" stroke-width="2" stroke-linecap="round"/>',
    "unsure": '<path d="M53.5 56 Q57 53 60 55.2 Q63 57.4 66.5 54.2" fill="none" stroke="#0B1020" stroke-width="2" stroke-linecap="round"/>',
    "surprised": '<ellipse cx="60" cy="55.5" rx="2.8" ry="3.4" fill="#7F1D1D" stroke="#0B1020" stroke-width="1.4"/>',
}

_ESCUDO = "M60 64 L76 69 L74.5 85 Q71 94.5 60 99 Q49 94.5 45.5 85 L44 69 Z"
_ids = count(1)


def mascota(expresion: str = "happy", pose: str = "idle", tamano: int = 96,
            titulo: str = "Prismi, la guía de Prisma BMV") -> str:
    """SVG de Prismi centrado. Cada llamada usa ids propios para que varias copias convivan."""
    expresion = expresion if expresion in EXPRESIONES else "idle"
    pose = pose if pose in POSES else "idle"
    n = next(_ids)
    bill, cape, gold, clip = (f"prismi-{k}-{n}" for k in ("bill", "cape", "gold", "clip"))
    gx, gy = (1.4, -1.6) if expresion == "thinking" else (0, 0)
    t = escape(titulo)
    # Sin líneas en blanco ni sangría: el Markdown de Streamlit las convertiría en texto.
    partes = [
        f'<div class="prismi-marco"><svg class="prismi prismi-expr-{expresion} prismi-pose-{pose}" '
        f'width="{tamano}" height="{round(tamano * 1.25)}" viewBox="0 0 120 150" role="img" aria-label="{t}" '
        f'style="--gx:{gx}px;--gy:{gy}px" xmlns="http://www.w3.org/2000/svg"><title>{t}</title>',
        "<defs>",
        f'<linearGradient id="{bill}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6EE7A0"/>'
        '<stop offset="0.55" stop-color="#34B26F"/><stop offset="1" stop-color="#1F8A55"/></linearGradient>',
        f'<linearGradient id="{cape}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F43F5E"/>'
        '<stop offset="1" stop-color="#9F1239"/></linearGradient>',
        f'<linearGradient id="{gold}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FDE68A"/>'
        '<stop offset="1" stop-color="#F59E0B"/></linearGradient>',
        f'<clipPath id="{clip}"><path d="{_ESCUDO}"/></clipPath>',
        "</defs>",
        '<ellipse class="prismi-shadow" cx="60" cy="146" rx="24" ry="3.2" fill="#000" opacity="0.35"/>',
        '<g class="prismi-float">',
        # Capa
        '<path class="prismi-cape" d="M38 38 C 30 70, 22 100, 15 128 Q 27 121 38 129 Q 49 121 60 131 Q 71 121 82 129 '
        f'Q 93 121 105 128 C 98 100, 90 70, 82 38 Z" fill="url(#{cape})" stroke="#881337" stroke-width="1.4" '
        'stroke-linejoin="round"/>',
        # Piernas y botas
        '<g class="prismi-legs"><path class="prismi-leg-l" d="M50 112 L48 132" stroke="#14532D" stroke-width="5" '
        'stroke-linecap="round"/><path class="prismi-leg-r" d="M70 112 L72 132" stroke="#14532D" stroke-width="5" '
        'stroke-linecap="round"/><ellipse cx="46" cy="134.5" rx="7.5" ry="4.2" fill="#BE123C" stroke="#881337" '
        'stroke-width="1.2"/><ellipse cx="74" cy="134.5" rx="7.5" ry="4.2" fill="#BE123C" stroke="#881337" '
        'stroke-width="1.2"/></g>',
        # Cuerpo: el billete
        f'<rect x="32" y="20" width="56" height="94" rx="7" fill="url(#{bill})" stroke="#14532D" stroke-width="2"/>',
        '<rect x="36" y="24" width="48" height="86" rx="4" fill="none" stroke="#ECFCCB" stroke-opacity="0.75" '
        'stroke-width="1" stroke-dasharray="2 2"/>',
        '<text x="40" y="33" font-size="8" font-weight="800" fill="#ECFCCB" font-family="Inter, system-ui, sans-serif">$</text>',
        '<text x="80" y="107" font-size="8" font-weight="800" fill="#ECFCCB" text-anchor="end" '
        'font-family="Inter, system-ui, sans-serif">$</text>',
        '<path d="M38 104 Q 46 100 54 104" fill="none" stroke="#ECFCCB" stroke-opacity="0.5" stroke-width="0.9"/>',
        '<path d="M66 28 Q 74 32 82 28" fill="none" stroke="#ECFCCB" stroke-opacity="0.5" stroke-width="0.9"/>',
        # Brazos
        '<g class="prismi-arm prismi-arm-l"><path d="M34 62 Q 23 66 17 78" fill="none" stroke="#1F7A4A" '
        'stroke-width="5" stroke-linecap="round"/><circle cx="17" cy="78" r="5" fill="#FFFFFF" stroke="#0B1020" '
        'stroke-width="1.4"/></g>',
        '<g class="prismi-arm prismi-arm-r"><path d="M86 62 Q 97 66 103 78" fill="none" stroke="#1F7A4A" '
        'stroke-width="5" stroke-linecap="round"/><circle cx="103" cy="78" r="5" fill="#FFFFFF" stroke="#0B1020" '
        'stroke-width="1.4"/></g>',
        # Cara
        '<path d="M39.5 42 Q 44 33.5 60 38.6 Q 76 33.5 80.5 42 Q 77 50.5 67 47.6 Q 60 45.6 53 47.6 Q 43 50.5 39.5 42 Z" '
        'fill="#1E1B4B"/>',
        '<g class="prismi-eyes"><ellipse cx="51" cy="42.4" rx="4.6" ry="4.1" fill="#FFFFFF"/>'
        '<ellipse cx="69" cy="42.4" rx="4.6" ry="4.1" fill="#FFFFFF"/><g class="prismi-pupils">'
        '<circle cx="51.4" cy="42.8" r="2.3" fill="#0B1020"/><circle cx="69.4" cy="42.8" r="2.3" fill="#0B1020"/>'
        '<circle cx="52.3" cy="41.8" r="0.8" fill="#FFFFFF"/><circle cx="70.3" cy="41.8" r="0.8" fill="#FFFFFF"/>'
        "</g></g>",
        '<circle cx="43.5" cy="53.5" r="3" fill="#F472B6" opacity="0.45"/>',
        '<circle cx="76.5" cy="53.5" r="3" fill="#F472B6" opacity="0.45"/>',
        f'<g class="prismi-mouth">{_BOCAS[expresion]}</g>',
        # Emblema: gráfica al alza
        f'<g class="prismi-emblem"><path d="{_ESCUDO}" fill="url(#{gold})" stroke="#92400E" stroke-width="1.6" '
        'stroke-linejoin="round"/><rect x="50" y="85" width="4.2" height="7" rx="0.8" fill="#14532D"/>'
        '<rect x="56" y="81" width="4.2" height="11" rx="0.8" fill="#14532D"/>'
        '<rect x="62" y="77" width="4.2" height="15" rx="0.8" fill="#14532D"/>'
        '<path d="M48.5 80 L54.5 75 L59.5 77 L68.5 69.4" fill="none" stroke="#B91C1C" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/><path d="M70.6 67.6 L64.4 68.4 L69.6 73.4 Z" fill="#B91C1C"/>'
        f'<g clip-path="url(#{clip})"><rect class="prismi-glint" x="30" y="60" width="7" height="44" fill="#FFFFFF" '
        'opacity="0.55" transform="skewX(-20)"/></g></g>',
        "</g></svg></div>",
    ]
    return "".join(partes)


# Animaciones de frontend/src/components/mascot.css (sin llaves dobles: no es f-string).
CSS = """
/* Prismi: billete superhéroe (mismo personaje que el sitio web) */
.prismi-marco { display:flex; justify-content:center; }
.prismi { display:block; overflow:visible; }
.prismi * { transform-box:view-box; }
.prismi-float { animation:prismi-bob 3.2s ease-in-out infinite; }
@keyframes prismi-bob { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-4px); } }
.prismi-shadow { transform-origin:60px 146px; animation:prismi-shadow 3.2s ease-in-out infinite; }
@keyframes prismi-shadow { 0%,100% { transform:scaleX(1); opacity:.35; } 50% { transform:scaleX(.82); opacity:.2; } }
.prismi-cape { transform-origin:60px 38px; animation:prismi-cape 1.9s ease-in-out infinite; }
@keyframes prismi-cape { 0%,100% { transform:skewX(0deg) scaleY(1); } 50% { transform:skewX(5deg) scaleY(.97); } }
.prismi-eyes { transform-origin:60px 42.4px; animation:prismi-blink 4.8s infinite; }
@keyframes prismi-blink { 0%,93%,100% { transform:scaleY(1); } 95% { transform:scaleY(.12); } }
.prismi-pupils { transform:translate(var(--gx,0px), var(--gy,0px)); transition:transform .35s ease; }
.prismi-glint { animation:prismi-glint 3.6s ease-in-out infinite; }
@keyframes prismi-glint { 0%,60% { translate:0 0; } 85%,100% { translate:60px 0; } }
.prismi-arm { transition:transform .45s cubic-bezier(.34,1.56,.64,1); }
.prismi-arm-l { transform-origin:34px 62px; }
.prismi-arm-r { transform-origin:86px 62px; }
.prismi-leg-l, .prismi-leg-r { transition:transform .4s ease; }
.prismi-leg-l { transform-origin:50px 112px; }
.prismi-leg-r { transform-origin:70px 112px; }
.prismi-pose-point-right .prismi-arm-r { transform:rotate(-58deg); }
.prismi-pose-point-left .prismi-arm-l { transform:rotate(58deg); }
.prismi-pose-point-up .prismi-arm-r { transform:rotate(-128deg); }
.prismi-pose-point-down .prismi-arm-r { transform:rotate(28deg); }
.prismi-pose-cheer .prismi-arm-r { transform:rotate(-125deg); }
.prismi-pose-cheer .prismi-arm-l { transform:rotate(125deg); }
.prismi-pose-cheer .prismi-float { animation:prismi-jump .7s ease-in-out infinite; }
@keyframes prismi-jump { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-9px); } }
.prismi-pose-wave .prismi-arm-r { animation:prismi-wave .9s ease-in-out infinite; }
@keyframes prismi-wave { 0%,100% { transform:rotate(-112deg); } 50% { transform:rotate(-78deg); } }
.prismi-pose-fly .prismi-arm-r { transform:rotate(-96deg); }
.prismi-pose-fly .prismi-arm-l { transform:rotate(18deg); }
.prismi-pose-fly .prismi-leg-l { transform:rotate(22deg); }
.prismi-pose-fly .prismi-leg-r { transform:rotate(14deg); }
.prismi-pose-fly .prismi-cape { animation:prismi-cape-fly .32s ease-in-out infinite; }
@keyframes prismi-cape-fly { 0%,100% { transform:skewX(-9deg) scaleY(1.03); } 50% { transform:skewX(-15deg) scaleY(.98); } }
@media (prefers-reduced-motion: reduce) {
  .prismi *, .prismi-float { animation:none !important; transition:none !important; }
}
"""
