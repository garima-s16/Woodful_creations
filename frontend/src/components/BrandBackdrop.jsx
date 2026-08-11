import React from 'react';

/**
 * Original abstract backdrop for the login brand panel - concentric
 * wood-ring rounds and fine laser-cut-style line work, evoking the
 * craft without using a photograph. No real photography of Woodful's
 * work exists in this project, so this is generated art rather than a
 * stock/fake image standing in for one.
 */
function BrandBackdrop() {
  return (
    <svg className="brand-backdrop" viewBox="0 0 800 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="ringFade" cx="50%" cy="50%" r="65%">
          <stop offset="0%" stopColor="var(--color-gold)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--color-gold)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Wood-ring rounds, off-center like a cut cross-section */}
      <g opacity="0.5" transform="translate(560,260)">
        {[40, 75, 108, 138, 165, 190, 212].map((r) => (
          <circle key={r} r={r} fill="none" stroke="var(--color-tan)" strokeWidth="1" opacity={0.5 - r / 500} />
        ))}
        <circle r="230" fill="url(#ringFade)" />
      </g>

      {/* Second, smaller ring cluster lower-left */}
      <g opacity="0.35" transform="translate(140,760)">
        {[25, 48, 70, 90, 108].map((r) => (
          <circle key={r} r={r} fill="none" stroke="var(--color-gold-soft)" strokeWidth="1" opacity={0.55 - r / 300} />
        ))}
      </g>

      {/* Fine laser-cut style geometric line lattice */}
      <g stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.22">
        <line x1="0" y1="120" x2="800" y2="20" />
        <line x1="0" y1="420" x2="800" y2="340" />
        <line x1="0" y1="620" x2="800" y2="560" />
        <line x1="0" y1="880" x2="800" y2="940" />
        <line x1="80" y1="0" x2="0" y2="200" />
        <line x1="720" y1="0" x2="800" y2="180" />
      </g>

      {/* Precision tick marks, like a cutting guide */}
      <g stroke="var(--color-gold)" strokeWidth="1" opacity="0.3">
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={i} x1={40 + i * 55} y1="960" x2={40 + i * 55} y2={i % 2 === 0 ? 980 : 972} />
        ))}
      </g>
    </svg>
  );
}

export default BrandBackdrop;
