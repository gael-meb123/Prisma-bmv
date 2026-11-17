/**
 * Prisma BMV · Ilustraciones vectoriales propias (SVG en línea).
 * Paleta de marca: azul marino #062c50, turquesa #079baa, verde #10b981.
 * Cada componente genera ids propios para que varias copias convivan en la página.
 */
import React, { useId } from "react";

const NAVY = "#062c50";
const NAVY_9 = "#041f3a";
const TEAL = "#079baa";
const TEAL_L = "#5fd0dc";
const GREEN = "#10b981";

function useIds(...names) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  return Object.fromEntries(names.map((n) => [n, `${n}-${uid}`]));
}

/* --------------------------------------------------------------------------
   Hero: teléfono con la terminal + tarjeta Prisma + sello SHA-256
   -------------------------------------------------------------------------- */
export function HeroIllustration({ ppp = "$54.59", ticker = "WALMEX" }) {
  const id = useIds("blob", "screen", "card", "area", "shield", "chip");
  return (
    <svg className="bk-hero-svg" viewBox="0 0 560 470" role="img" aria-label="Terminal Prisma BMV en un teléfono junto a una tarjeta del plan">
      <defs>
        <radialGradient id={id.blob} cx="50%" cy="45%" r="60%">
          <stop offset="0" stopColor={TEAL} stopOpacity="0.28" />
          <stop offset="1" stopColor={TEAL} stopOpacity="0" />
        </radialGradient>
        <linearGradient id={id.screen} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#eef5f9" />
        </linearGradient>
        <linearGradient id={id.card} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={NAVY_9} />
          <stop offset="0.55" stopColor={NAVY} />
          <stop offset="1" stopColor="#0a6f86" />
        </linearGradient>
        <linearGradient id={id.area} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={TEAL} stopOpacity="0.35" />
          <stop offset="1" stopColor={TEAL} stopOpacity="0" />
        </linearGradient>
        <linearGradient id={id.shield} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#34d399" />
          <stop offset="1" stopColor="#059669" />
        </linearGradient>
        <linearGradient id={id.chip} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fde68a" />
          <stop offset="1" stopColor="#d4a017" />
        </linearGradient>
      </defs>

      {/* Fondo: halo y retícula de puntos */}
      <circle cx="300" cy="215" r="220" fill={`url(#${id.blob})`} />
      <g fill={NAVY} opacity="0.12">
        {Array.from({ length: 6 }).map((_, r) =>
          Array.from({ length: 6 }).map((__, c) => <circle key={`${r}-${c}`} cx={450 + c * 14} cy={300 + r * 14} r="2" />)
        )}
      </g>
      <circle cx="120" cy="90" r="10" fill={TEAL} opacity="0.25" />
      <circle cx="505" cy="120" r="6" fill={GREEN} opacity="0.4" />
      <path d="M70 330 q 30 -40 60 0 t 60 0" fill="none" stroke={TEAL} strokeWidth="3" strokeLinecap="round" opacity="0.35" />

      {/* Teléfono */}
      <g transform="translate(230 28)">
        <rect x="0" y="0" width="218" height="410" rx="34" fill={NAVY_9} />
        <rect x="9" y="9" width="200" height="392" rx="27" fill={`url(#${id.screen})`} />
        <rect x="80" y="18" width="58" height="8" rx="4" fill={NAVY_9} />
        {/* Encabezado de la app */}
        <rect x="22" y="40" width="174" height="74" rx="16" fill={NAVY} />
        <text x="36" y="62" fontSize="10" fill="#9fc0d6" fontFamily="Manrope, sans-serif" fontWeight="700">PPP OFICIAL · {ticker}</text>
        <text x="36" y="90" fontSize="24" fill="#ffffff" fontFamily="Manrope, sans-serif" fontWeight="800">{ppp}</text>
        <rect x="140" y="80" width="44" height="18" rx="9" fill="#10b981" opacity="0.2" />
        <text x="162" y="93" fontSize="10" fill="#6ee7b7" textAnchor="middle" fontFamily="Manrope, sans-serif" fontWeight="800">t+5</text>
        {/* Gráfica de área */}
        <path d="M22 210 L22 176 C 40 170, 52 182, 66 172 S 92 150, 108 158 S 136 140, 150 132 S 178 120, 196 112 L196 210 Z" fill={`url(#${id.area})`} />
        <path d="M22 176 C 40 170, 52 182, 66 172 S 92 150, 108 158 S 136 140, 150 132 S 178 120, 196 112" fill="none" stroke={TEAL} strokeWidth="3" strokeLinecap="round" />
        <path d="M188 107 l8 5 -8 5 -8 -5 Z" fill={GREEN} />
        {/* Barras de modelos */}
        {[
          [64, "V1"],
          [92, "V2"],
          [78, "V3"],
          [110, "V4"],
        ].map(([w, l], i) => (
          <g key={l} transform={`translate(22 ${226 + i * 20})`}>
            <text x="0" y="10" fontSize="9" fill="#5f7389" fontFamily="Manrope, sans-serif" fontWeight="700">{l}</text>
            <rect x="22" y="2" width="152" height="9" rx="4.5" fill="#e3ebf2" />
            <rect x="22" y="2" width={w} height="9" rx="4.5" fill={i === 3 ? GREEN : TEAL} />
          </g>
        ))}
        <line x1="98" y1="222" x2="98" y2="310" stroke={NAVY} strokeDasharray="3 3" opacity="0.5" />
        {/* Lista */}
        {[0, 1].map((i) => (
          <g key={i} transform={`translate(22 ${320 + i * 34})`}>
            <rect width="174" height="28" rx="9" fill="#ffffff" stroke="#dde6ef" />
            <circle cx="15" cy="14" r="8" fill={i ? "#fdecec" : "#e7f7f0"} />
            <rect x="30" y="9" width="62" height="5" rx="2.5" fill="#b8c7d6" />
            <rect x="30" y="17" width="40" height="4" rx="2" fill="#d6e0ea" />
            <rect x="136" y="11" width="30" height="6" rx="3" fill={i ? "#d64545" : GREEN} opacity="0.75" />
          </g>
        ))}
      </g>

      {/* Tarjeta Prisma inclinada */}
      <g transform="translate(46 238) rotate(-9)">
        <rect width="250" height="152" rx="18" fill={`url(#${id.card})`} />
        <path d="M0 110 C 70 80, 150 150, 250 96 L250 134 Q250 152 232 152 L18 152 Q0 152 0 134 Z" fill="#ffffff" opacity="0.06" />
        <polygon points="214,22 232,31 232,49 214,58 196,49 196,31" fill={TEAL} opacity="0.95" />
        <polygon points="214,22 232,31 214,40 196,31" fill="#ffffff" opacity="0.35" />
        <rect x="22" y="44" width="38" height="28" rx="6" fill={`url(#${id.chip})`} />
        <path d="M22 58 h38 M41 44 v28" stroke="#b7860b" strokeWidth="1.2" opacity="0.6" />
        <text x="22" y="30" fontSize="12" fill="#ffffff" fontFamily="Manrope, sans-serif" fontWeight="800" letterSpacing="1.5">PRISMA BMV</text>
        <text x="22" y="104" fontSize="15" fill="#d7eef6" fontFamily="ui-monospace, monospace" letterSpacing="3">•••• •••• 2026</text>
        <text x="22" y="132" fontSize="10" fill="#9fc0d6" fontFamily="Manrope, sans-serif" fontWeight="700" letterSpacing="1.2">PROFESSIONAL · PANEL G2</text>
      </g>

      {/* Sello SHA-256 */}
      <g transform="translate(468 40)">
        <path d="M34 0 L66 12 L63 44 Q58 66 34 78 Q10 66 5 44 L2 12 Z" fill={`url(#${id.shield})`} />
        <path d="M20 39 l10 10 18 -20" fill="none" stroke="#ffffff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/* Ola inferior del hero (usa currentColor = color de la siguiente sección) */
export function WaveDivider({ className = "bk-hero-waves" }) {
  return (
    <svg className={className} viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 50 C 240 90, 480 10, 720 40 S 1200 90, 1440 30 L1440 90 L0 90 Z" fill="currentColor" />
      <path d="M0 64 C 260 96, 520 30, 760 58 S 1220 96, 1440 52" fill="none" stroke="#079baa" strokeOpacity="0.18" strokeWidth="2" />
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Íconos duotono de los pasos (64 px)
   -------------------------------------------------------------------------- */
export function StepIcon({ kind = "boletin", size = 64 }) {
  const id = useIds("bg");
  const fondo = (
    <>
      <defs>
        <linearGradient id={id.bg} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ebf8fa" />
          <stop offset="1" stopColor="#d3f1f5" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${id.bg})`} />
    </>
  );
  const dibujos = {
    boletin: (
      <g>
        <rect x="18" y="12" width="28" height="38" rx="4" fill="#fff" stroke={NAVY} strokeWidth="2" />
        <path d="M24 22 h16 M24 28 h16 M24 34 h10" stroke={TEAL} strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="42" cy="46" r="9" fill={GREEN} />
        <path d="M38 46 l3 3 5 -6" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    ),
    lago: (
      <g>
        <path d="M32 14 L50 22 L32 30 L14 22 Z" fill="#d4a017" opacity="0.9" />
        <path d="M14 30 L32 38 L50 30" fill="none" stroke="#94a3b8" strokeWidth="3" strokeLinejoin="round" />
        <path d="M14 38 L32 46 L50 38" fill="none" stroke="#b07d48" strokeWidth="3" strokeLinejoin="round" />
        <path d="M14 22 L14 38 M50 22 L50 38" stroke={NAVY} strokeWidth="1.5" opacity="0.4" />
      </g>
    ),
    modelo: (
      <g>
        <path d="M14 46 L26 34 L36 40 L50 20" fill="none" stroke={TEAL} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {[
          [14, 46],
          [26, 34],
          [36, 40],
          [50, 20],
        ].map(([x, y]) => (
          <circle key={`${x}${y}`} cx={x} cy={y} r="4.5" fill="#fff" stroke={NAVY} strokeWidth="2" />
        ))}
        <path d="M14 52 h36" stroke={NAVY} strokeWidth="2" opacity="0.3" strokeLinecap="round" />
      </g>
    ),
    auditoria: (
      <g>
        <rect x="14" y="16" width="36" height="34" rx="6" fill="#fff" stroke={NAVY} strokeWidth="2" />
        <path d="M14 26 h36" stroke={NAVY} strokeWidth="2" />
        <path d="M22 12 v8 M42 12 v8" stroke={NAVY} strokeWidth="2.4" strokeLinecap="round" />
        {[0, 1, 2, 3, 4].map((i) => (
          <circle key={i} cx={20 + i * 6} cy="38" r="2.3" fill={i < 4 ? TEAL : GREEN} />
        ))}
        <text x="44" y="47" fontSize="8" fontWeight="800" fill={NAVY} fontFamily="Manrope, sans-serif" textAnchor="end">t+5</text>
      </g>
    ),
  };
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      {fondo}
      {dibujos[kind] || dibujos.boletin}
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Tarjeta de producto por plan (estilo tarjeta bancaria)
   -------------------------------------------------------------------------- */
const PLAN_ART = {
  explorer: { a: "#0a7f8c", b: "#5fd0dc", label: "EXPLORER", tag: "WALMEX · GRATIS" },
  professional: { a: NAVY_9, b: TEAL, label: "PROFESSIONAL", tag: "15 EMISORAS · PANEL G2" },
  enterprise: { a: "#020f1d", b: "#1c3d5a", label: "ENTERPRISE", tag: "ATHENA · API · SLA", gold: true },
};

export function PlanCardArt({ plan = "explorer" }) {
  const v = PLAN_ART[plan] || PLAN_ART.explorer;
  const id = useIds("g", "chip");
  return (
    <svg viewBox="0 0 320 170" role="img" aria-label={`Tarjeta del plan ${v.label}`}>
      <defs>
        <linearGradient id={id.g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={v.a} />
          <stop offset="1" stopColor={v.b} />
        </linearGradient>
        <linearGradient id={id.chip} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fde68a" />
          <stop offset="1" stopColor="#d4a017" />
        </linearGradient>
      </defs>
      <rect width="320" height="170" rx="16" fill={`url(#${id.g})`} />
      <circle cx="290" cy="-10" r="110" fill="#ffffff" opacity="0.07" />
      <circle cx="300" cy="190" r="80" fill="#ffffff" opacity="0.05" />
      <path d="M0 128 C 80 98, 160 160, 320 110" fill="none" stroke="#ffffff" strokeOpacity="0.18" strokeWidth="2" />
      <polygon points="282,20 298,28 298,44 282,52 266,44 266,28" fill={v.gold ? "#d4a017" : "#ffffff"} opacity="0.9" />
      <rect x="22" y="52" width="40" height="30" rx="6" fill={`url(#${id.chip})`} />
      <text x="22" y="34" fontSize="13" fill="#fff" fontWeight="800" fontFamily="Manrope, sans-serif" letterSpacing="1.5">PRISMA BMV</text>
      <text x="22" y="118" fontSize="16" fill="#e3f1fa" fontFamily="ui-monospace, monospace" letterSpacing="3">•••• •••• •••• 2026</text>
      <text x="22" y="148" fontSize="11" fill="#fff" fontWeight="800" fontFamily="Manrope, sans-serif" letterSpacing="1.4">{v.label}</text>
      <text x="298" y="148" fontSize="9.5" fill="#d7eef6" fontWeight="700" textAnchor="end" fontFamily="Manrope, sans-serif" letterSpacing="1">{v.tag}</text>
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Escudo de seguridad (banda azul de la landing)
   -------------------------------------------------------------------------- */
export function ShieldArt({ size = 260 }) {
  const id = useIds("s", "glow");
  return (
    <svg width={size} height={size} viewBox="0 0 260 260" role="img" aria-label="Sello de integridad SHA-256">
      <defs>
        <linearGradient id={id.s} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={TEAL_L} />
          <stop offset="1" stopColor={TEAL} />
        </linearGradient>
        <radialGradient id={id.glow}>
          <stop offset="0" stopColor={TEAL_L} stopOpacity="0.35" />
          <stop offset="1" stopColor={TEAL_L} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="130" cy="130" r="128" fill={`url(#${id.glow})`} />
      <circle cx="130" cy="130" r="96" fill="none" stroke="#ffffff" strokeOpacity="0.12" strokeDasharray="4 8" />
      <circle cx="130" cy="130" r="118" fill="none" stroke="#ffffff" strokeOpacity="0.08" />
      <path d="M130 44 L196 68 L190 136 Q180 186 130 214 Q80 186 70 136 L64 68 Z" fill={`url(#${id.s})`} />
      <path d="M130 58 L184 78 L179 134 Q171 176 130 200 Z" fill="#ffffff" opacity="0.12" />
      <rect x="104" y="118" width="52" height="42" rx="8" fill={NAVY} />
      <path d="M114 118 v-12 a16 16 0 0 1 32 0 v12" fill="none" stroke={NAVY} strokeWidth="8" strokeLinecap="round" />
      <circle cx="130" cy="136" r="6" fill={TEAL_L} />
      <rect x="127.5" y="138" width="5" height="12" rx="2.5" fill={TEAL_L} />
      {["a3f7…", "ea24…", "9c1d…"].map((t, i) => (
        <g key={t} transform={`translate(${[18, 188, 196][i]} ${[70, 40, 196][i]})`}>
          <rect width="56" height="22" rx="11" fill="#ffffff" opacity="0.1" />
          <text x="28" y="15" fontSize="10" fill="#d7eef6" textAnchor="middle" fontFamily="ui-monospace, monospace">{t}</text>
        </g>
      ))}
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Acceso: teléfono con candado y huella
   -------------------------------------------------------------------------- */
export function LoginArt() {
  const id = useIds("p", "g");
  return (
    <svg className="bk-access-svg" viewBox="0 0 420 300" role="img" aria-label="Acceso seguro a la terminal">
      <defs>
        <linearGradient id={id.p} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#e3eef5" />
        </linearGradient>
        <radialGradient id={id.g}>
          <stop offset="0" stopColor={TEAL_L} stopOpacity="0.35" />
          <stop offset="1" stopColor={TEAL_L} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="210" cy="150" r="150" fill={`url(#${id.g})`} />
      <path d="M20 230 C 90 190, 140 250, 210 210 S 330 170, 400 200" fill="none" stroke={TEAL_L} strokeOpacity="0.4" strokeWidth="3" />
      <g transform="translate(150 20)">
        <rect width="120" height="240" rx="22" fill={NAVY_9} stroke="#ffffff" strokeOpacity="0.15" />
        <rect x="7" y="7" width="106" height="226" rx="17" fill={`url(#${id.p})`} />
        <circle cx="60" cy="86" r="30" fill={NAVY} />
        <rect x="45" y="84" width="30" height="24" rx="5" fill={TEAL_L} />
        <path d="M50 84 v-8 a10 10 0 0 1 20 0 v8" fill="none" stroke={TEAL_L} strokeWidth="5" strokeLinecap="round" />
        <rect x="22" y="138" width="76" height="12" rx="6" fill="#d6e0ea" />
        <rect x="22" y="158" width="76" height="12" rx="6" fill="#d6e0ea" />
        <rect x="22" y="182" width="76" height="20" rx="10" fill={TEAL} />
      </g>
      <g transform="translate(300 70)" fill="none" stroke={TEAL_L} strokeWidth="3" strokeLinecap="round">
        <path d="M30 6 a24 24 0 0 1 24 24 v14" />
        <path d="M6 30 a24 24 0 0 1 12 -21" />
        <path d="M30 16 a14 14 0 0 1 14 14 v20" />
        <path d="M16 30 a14 14 0 0 1 4 -10 M16 30 v18" />
        <path d="M30 28 v26" />
      </g>
      <g transform="translate(46 96)">
        <rect width="84" height="56" rx="12" fill="#ffffff" opacity="0.1" />
        <path d="M14 40 L30 28 L44 34 L68 16" fill="none" stroke="#6ee7b7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Arte decorativo: banner de bienvenida de la terminal y encabezados internos
   -------------------------------------------------------------------------- */
export function WelcomeArt() {
  const velas = [
    [40, 60, 30, 1],
    [70, 48, 40, 1],
    [100, 64, 26, 0],
    [130, 40, 46, 1],
    [160, 52, 34, 0],
    [190, 30, 50, 1],
    [220, 36, 42, 1],
  ];
  return (
    <svg className="tm-welcome-art" viewBox="0 0 300 140" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      <g opacity="0.22">
        {velas.map(([x, y, h, up]) => (
          <g key={x}>
            <line x1={x} y1={y - 10} x2={x} y2={y + h + 10} stroke="#ffffff" strokeWidth="2" />
            <rect x={x - 7} y={y} width="14" height={h} rx="3" fill={up ? "#6ee7b7" : "#fca5a5"} />
          </g>
        ))}
      </g>
      <path d="M10 120 C 60 100, 90 110, 130 80 S 210 60, 290 20" fill="none" stroke={TEAL_L} strokeWidth="3" strokeLinecap="round" opacity="0.6" />
      <circle cx="290" cy="20" r="5" fill="#6ee7b7" />
    </svg>
  );
}

export function PageHeroArt() {
  return (
    <svg className="bk-page-hero-art" viewBox="0 0 520 220" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      <g stroke="#ffffff" strokeOpacity="0.07">
        {Array.from({ length: 12 }).map((_, i) => (
          <line key={`v${i}`} x1={i * 44} y1="0" x2={i * 44} y2="220" />
        ))}
        {Array.from({ length: 6 }).map((_, i) => (
          <line key={`h${i}`} x1="0" y1={i * 44} x2="520" y2={i * 44} />
        ))}
      </g>
      <path d="M0 190 C 80 170, 140 186, 200 140 S 320 120, 380 80 S 470 50, 520 30" fill="none" stroke={TEAL_L} strokeWidth="3" opacity="0.7" />
      <path d="M0 190 C 80 170, 140 186, 200 140 S 320 120, 380 80 S 470 50, 520 30 L520 220 L0 220 Z" fill={TEAL} opacity="0.12" />
      <polygon points="440,70 470,85 470,115 440,130 410,115 410,85" fill="none" stroke="#ffffff" strokeOpacity="0.25" strokeWidth="2" />
    </svg>
  );
}

/* Estado vacío o bloqueado */
export function EmptyArt({ locked = false, size = 120 }) {
  return (
    <svg width={size} height={size * 0.75} viewBox="0 0 160 120" aria-hidden="true">
      <rect x="10" y="20" width="120" height="84" rx="12" fill="#ffffff" stroke="#dde6ef" strokeWidth="2" />
      <path d="M24 84 L48 62 L66 72 L92 44 L116 54" fill="none" stroke="#c8d6e3" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={locked ? "0" : "6 6"} />
      {locked ? (
        <g transform="translate(104 58)">
          <circle r="26" fill={NAVY} />
          <rect x="-11" y="-3" width="22" height="17" rx="4" fill={TEAL_L} />
          <path d="M-7 -3 v-6 a7 7 0 0 1 14 0 v6" fill="none" stroke={TEAL_L} strokeWidth="3.5" strokeLinecap="round" />
        </g>
      ) : (
        <g transform="translate(110 60)">
          <circle r="20" fill="#ffffff" stroke={TEAL} strokeWidth="5" />
          <line x1="14" y1="14" x2="30" y2="30" stroke={TEAL} strokeWidth="7" strokeLinecap="round" />
        </g>
      )}
    </svg>
  );
}

/* Mini tendencia para tarjetas de saldo */
export function MiniSpark({ values = [], color = TEAL, width = 96, height = 34 }) {
  const vals = values.filter((v) => v != null && !Number.isNaN(v));
  if (vals.length < 2) return null;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const rng = max - min || 1;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * width},${height - 4 - ((v - min) / rng) * (height - 8)}`);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
