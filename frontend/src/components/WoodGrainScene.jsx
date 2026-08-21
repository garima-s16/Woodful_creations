import React from 'react';

/**
 * A tasteful, lightweight motion scene for the login/auth left panel:
 * layered wood-grain rings, drifting light "sawdust" motes, and a
 * slow-turning growth-ring mark. Deliberately CSS-only (transform/
 * opacity keyframes, no JS animation loop, no external library) - the
 * person flagged the page as slow to load, so this adds atmosphere
 * without adding weight: everything here is inline SVG plus CSS,
 * animated on the compositor thread rather than JS.
 */
function WoodGrainScene() {
  const motes = Array.from({ length: 14 }, (_, i) => i);

  return (
    <div className="wood-grain-scene" aria-hidden="true">
      <svg className="wood-grain-rings" viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="ringFade" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--color-gold-soft)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--color-gold-soft)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <g className="wood-grain-rings-inner">
          {[70, 110, 150, 190, 230, 270].map((r, i) => (
            <circle
              key={r} cx="300" cy="300" r={r}
              fill="none" stroke="var(--color-gold-soft)" strokeWidth="1"
              opacity={0.16 - i * 0.018}
            />
          ))}
        </g>
        <circle cx="300" cy="300" r="70" fill="url(#ringFade)" />
      </svg>

      <svg className="wood-plank-lines" viewBox="0 0 400 900" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
        <path className="grain-line grain-line-1" d="M0,120 C90,100 160,150 260,120 S380,80 400,110" fill="none" stroke="var(--color-gold)" strokeWidth="1" opacity="0.22" />
        <path className="grain-line grain-line-2" d="M0,420 C110,390 190,450 280,410 S380,380 400,420" fill="none" stroke="var(--color-gold)" strokeWidth="1" opacity="0.16" />
        <path className="grain-line grain-line-3" d="M0,700 C100,670 200,730 300,690 S390,660 400,700" fill="none" stroke="var(--color-gold-soft)" strokeWidth="1" opacity="0.14" />
      </svg>

      <div className="wood-motes">
        {motes.map((i) => (
          <span
            key={i}
            className="wood-mote"
            style={{
              left: `${(i * 137) % 100}%`,
              animationDelay: `${(i * 1.7) % 12}s`,
              animationDuration: `${14 + (i % 5) * 2}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default WoodGrainScene;
