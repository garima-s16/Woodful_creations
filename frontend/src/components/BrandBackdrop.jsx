import React from 'react';

/**
 * Login brand-panel backdrop.
 *
 * Composed from Woodful's actual visual vocabulary rather than generic
 * decoration: a cabinet/drawer-front elevation (proportions a cabinetmaker
 * would actually draw), a finger-joint seam, corner joinery notches, and
 * fine architectural dimension lines. No photography exists for the
 * product, so this is original vector art, not a stock substitute.
 */
function BrandBackdrop() {
  return (
    <svg className="brand-backdrop" viewBox="0 0 800 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="focalGlow" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="var(--color-gold)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--color-gold)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Soft glow grounding the focal composition, upper-left */}
      <circle cx="300" cy="330" r="320" fill="url(#focalGlow)" />

      {/* Focal piece: a cabinet/drawer-front elevation, drawn the way a
          joiner would spec it - carcass, reveals, pulls, joinery marks */}
      <g transform="translate(130,150)" opacity="0.85">
        {/* Outer carcass */}
        <rect x="0" y="0" width="320" height="420" rx="2" fill="none" stroke="var(--color-tan)" strokeWidth="1.25" opacity="0.55" />

        {/* Corner joinery notches (mortise-and-tenon reference) */}
        <path d="M0,0 L18,0 L18,7 L7,7 L7,18 L0,18 Z" fill="var(--color-gold)" opacity="0.28" />
        <path d="M320,420 L302,420 L302,413 L313,413 L313,402 L320,402 Z" fill="var(--color-gold)" opacity="0.28" />

        {/* Three drawer fronts with reveal gaps */}
        {[0, 1, 2].map((i) => {
          const gap = 16;
          const h = (420 - gap * 4) / 3;
          const y = gap + i * (h + gap);
          return (
            <g key={i}>
              <rect x={gap} y={y} width={320 - gap * 2} height={h} rx="1.5"
                fill="var(--color-wood)" opacity={0.1 + i * 0.03}
                stroke="var(--border-color)" strokeWidth="1" />
              {/* pull */}
              <circle cx={320 - gap * 2 - 22} cy={y + h / 2} r="4.5" fill="var(--color-gold-soft)" opacity="0.55" />
              {/* faint grain lines for material texture */}
              <path d={`M${gap + 14},${y + h * 0.35} q ${(320 - gap * 2 - 28) / 2} 10 ${320 - gap * 2 - 28} 0`}
                fill="none" stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.18" />
              <path d={`M${gap + 14},${y + h * 0.65} q ${(320 - gap * 2 - 28) / 2} -8 ${320 - gap * 2 - 28} 0`}
                fill="none" stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.14" />
            </g>
          );
        })}

        {/* Finger-joint seam running along the base, connecting the piece
            to the copy below */}
        <g transform="translate(0,442)">
          <path
            d="M0,0 L20,0 L20,10 L40,10 L40,0 L60,0 L60,10 L80,10 L80,0 L100,0 L100,10 L120,10 L120,0 L140,0 L140,10 L160,10 L160,0 L180,0 L180,10 L200,10 L200,0 L220,0 L220,10 L240,10 L240,0 L260,0 L260,10 L280,10 L280,0 L300,0 L300,10 L320,10"
            fill="none" stroke="var(--color-gold-soft)" strokeWidth="1" opacity="0.35" />
        </g>
      </g>

      {/* Fine architectural dimension lines - precision cue */}
      <g stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.16">
        <line x1="0" y1="70" x2="800" y2="20" />
        <line x1="0" y1="640" x2="800" y2="600" />
        <line x1="0" y1="900" x2="800" y2="960" />
      </g>

      {/* Precision tick marks, like a cutting guide, anchoring the bottom copy */}
      <g stroke="var(--color-gold)" strokeWidth="1" opacity="0.28">
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={i} x1={40 + i * 55} y1="960" x2={40 + i * 55} y2={i % 2 === 0 ? 980 : 972} />
        ))}
      </g>
    </svg>
  );
}

export default BrandBackdrop;
