import React, { useId } from "react";
import "./mascot.css";

/**
 * Prismi — el billete superhéroe de Prisma BMV.
 *
 * Props:
 *  - size:       ancho en px (el alto es size * 1.25)
 *  - expression: "happy" | "idle" | "thinking" | "unsure" | "surprised"
 *  - pose:       "idle" | "wave" | "point-left" | "point-right" | "point-up"
 *                | "point-down" | "fly" | "cheer"
 *  - gaze:       { x, y } entre -1 y 1, hacia dónde miran las pupilas
 */
const MOUTHS = {
  happy: <path d="M53 53 Q60 61.5 67 53 Z" fill="#7F1D1D" stroke="#0B1020" strokeWidth="1.6" strokeLinejoin="round" />,
  idle: <path d="M54 54.5 Q60 58 66 54.5" fill="none" stroke="#0B1020" strokeWidth="2" strokeLinecap="round" />,
  thinking: <path d="M56 56 Q60 54.6 64.5 56.4" fill="none" stroke="#0B1020" strokeWidth="2" strokeLinecap="round" />,
  unsure: <path d="M53.5 56 Q57 53 60 55.2 Q63 57.4 66.5 54.2" fill="none" stroke="#0B1020" strokeWidth="2" strokeLinecap="round" />,
  surprised: <ellipse cx="60" cy="55.5" rx="2.8" ry="3.4" fill="#7F1D1D" stroke="#0B1020" strokeWidth="1.4" />,
};

const SHIELD = "M60 64 L76 69 L74.5 85 Q71 94.5 60 99 Q49 94.5 45.5 85 L44 69 Z";

export function Mascot({
  size = 96,
  expression = "happy",
  pose = "idle",
  gaze = { x: 0, y: 0 },
  className = "",
  title = "Prismi, la guía de Prisma BMV",
}) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const ids = {
    bill: `prismi-bill-${uid}`,
    cape: `prismi-cape-${uid}`,
    gold: `prismi-gold-${uid}`,
    clip: `prismi-clip-${uid}`,
  };
  const gx = Math.max(-1, Math.min(1, gaze?.x || 0)) * 1.8;
  const gy = Math.max(-1, Math.min(1, gaze?.y || 0)) * 1.4;
  const thinkingGaze = expression === "thinking" ? { gx: 1.4, gy: -1.6 } : { gx, gy };

  return (
    <svg
      className={`prismi prismi-expr-${expression} prismi-pose-${pose} ${className}`}
      width={size}
      height={size * 1.25}
      viewBox="0 0 120 150"
      role="img"
      aria-label={title}
      style={{ "--gx": `${thinkingGaze.gx}px`, "--gy": `${thinkingGaze.gy}px` }}
    >
      <title>{title}</title>
      <defs>
        <linearGradient id={ids.bill} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6EE7A0" />
          <stop offset="0.55" stopColor="#34B26F" />
          <stop offset="1" stopColor="#1F8A55" />
        </linearGradient>
        <linearGradient id={ids.cape} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F43F5E" />
          <stop offset="1" stopColor="#9F1239" />
        </linearGradient>
        <linearGradient id={ids.gold} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FDE68A" />
          <stop offset="1" stopColor="#F59E0B" />
        </linearGradient>
        <clipPath id={ids.clip}>
          <path d={SHIELD} />
        </clipPath>
      </defs>

      <ellipse className="prismi-shadow" cx="60" cy="146" rx="24" ry="3.2" fill="#062c50" opacity="0.18" />

      <g className="prismi-float">
        {/* Capa */}
        <path
          className="prismi-cape"
          d="M38 38 C 30 70, 22 100, 15 128 Q 27 121 38 129 Q 49 121 60 131 Q 71 121 82 129 Q 93 121 105 128 C 98 100, 90 70, 82 38 Z"
          fill={`url(#${ids.cape})`}
          stroke="#881337"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />

        {/* Piernas y botas */}
        <g className="prismi-legs">
          <path className="prismi-leg-l" d="M50 112 L48 132" stroke="#14532D" strokeWidth="5" strokeLinecap="round" />
          <path className="prismi-leg-r" d="M70 112 L72 132" stroke="#14532D" strokeWidth="5" strokeLinecap="round" />
          <ellipse cx="46" cy="134.5" rx="7.5" ry="4.2" fill="#BE123C" stroke="#881337" strokeWidth="1.2" />
          <ellipse cx="74" cy="134.5" rx="7.5" ry="4.2" fill="#BE123C" stroke="#881337" strokeWidth="1.2" />
        </g>

        {/* Cuerpo: el billete */}
        <rect x="32" y="20" width="56" height="94" rx="7" fill={`url(#${ids.bill})`} stroke="#14532D" strokeWidth="2" />
        <rect x="36" y="24" width="48" height="86" rx="4" fill="none" stroke="#ECFCCB" strokeOpacity="0.75" strokeWidth="1" strokeDasharray="2 2" />
        <text x="40" y="33" fontSize="8" fontWeight="800" fill="#ECFCCB" fontFamily="Manrope, system-ui, sans-serif">$</text>
        <text x="80" y="107" fontSize="8" fontWeight="800" fill="#ECFCCB" textAnchor="end" fontFamily="Manrope, system-ui, sans-serif">$</text>
        <path d="M38 104 Q 46 100 54 104" fill="none" stroke="#ECFCCB" strokeOpacity="0.5" strokeWidth="0.9" />
        <path d="M66 28 Q 74 32 82 28" fill="none" stroke="#ECFCCB" strokeOpacity="0.5" strokeWidth="0.9" />

        {/* Brazos (giran desde el hombro) */}
        <g className="prismi-arm prismi-arm-l">
          <path d="M34 62 Q 23 66 17 78" fill="none" stroke="#1F7A4A" strokeWidth="5" strokeLinecap="round" />
          <circle cx="17" cy="78" r="5" fill="#FFFFFF" stroke="#0B1020" strokeWidth="1.4" />
        </g>
        <g className="prismi-arm prismi-arm-r">
          <path d="M86 62 Q 97 66 103 78" fill="none" stroke="#1F7A4A" strokeWidth="5" strokeLinecap="round" />
          <circle cx="103" cy="78" r="5" fill="#FFFFFF" stroke="#0B1020" strokeWidth="1.4" />
        </g>

        {/* Cara: antifaz, ojos, mejillas, boca */}
        <path
          d="M39.5 42 Q 44 33.5 60 38.6 Q 76 33.5 80.5 42 Q 77 50.5 67 47.6 Q 60 45.6 53 47.6 Q 43 50.5 39.5 42 Z"
          fill="#1E1B4B"
        />
        <g className="prismi-eyes">
          <ellipse cx="51" cy="42.4" rx="4.6" ry="4.1" fill="#FFFFFF" />
          <ellipse cx="69" cy="42.4" rx="4.6" ry="4.1" fill="#FFFFFF" />
          <g className="prismi-pupils">
            <circle cx="51.4" cy="42.8" r="2.3" fill="#0B1020" />
            <circle cx="69.4" cy="42.8" r="2.3" fill="#0B1020" />
            <circle cx="52.3" cy="41.8" r="0.8" fill="#FFFFFF" />
            <circle cx="70.3" cy="41.8" r="0.8" fill="#FFFFFF" />
          </g>
        </g>
        <circle cx="43.5" cy="53.5" r="3" fill="#F472B6" opacity="0.45" />
        <circle cx="76.5" cy="53.5" r="3" fill="#F472B6" opacity="0.45" />
        <g className="prismi-mouth">{MOUTHS[expression] ?? MOUTHS.idle}</g>

        {/* Emblema de superhéroe: gráfica al alza */}
        <g className="prismi-emblem">
          <path d={SHIELD} fill={`url(#${ids.gold})`} stroke="#92400E" strokeWidth="1.6" strokeLinejoin="round" />
          <rect x="50" y="85" width="4.2" height="7" rx="0.8" fill="#14532D" />
          <rect x="56" y="81" width="4.2" height="11" rx="0.8" fill="#14532D" />
          <rect x="62" y="77" width="4.2" height="15" rx="0.8" fill="#14532D" />
          <path d="M48.5 80 L54.5 75 L59.5 77 L68.5 69.4" fill="none" stroke="#B91C1C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M70.6 67.6 L64.4 68.4 L69.6 73.4 Z" fill="#B91C1C" />
          <g clipPath={`url(#${ids.clip})`}>
            <rect className="prismi-glint" x="30" y="60" width="7" height="44" fill="#FFFFFF" opacity="0.55" transform="skewX(-20)" />
          </g>
        </g>
      </g>
    </svg>
  );
}
