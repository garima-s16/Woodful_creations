import React from 'react';

/**
 * Layered spatial backdrop for the login brand panel, drawn directly
 * from Woodful's own logo motifs rather than generic decoration:
 *   - an irregular, hand-cut-feeling tree-ring cross-section (the
 *     logo's own "O" is a tree-ring illustration - this echoes it,
 *     deliberately organic/uneven rather than perfect concentric
 *     circles, which is what read as generic "tech template" before)
 *   - a partial saw-blade tooth arc (the logo's other "O")
 *   - a dovetail-joinery zigzag, a real woodworking joint profile
 *   - an abstracted cabinet-panel corner, cropped by the frame edge -
 *     a genuine foreground element with its own scale/weight, not
 *     just background texture
 *   - the ruler/tick-mark row, kept - it was already genuinely on-brand
 *
 * Three real depth layers (background/midground/foreground), each
 * with its own parallax multiplier - background barely moves,
 * foreground moves most, giving actual spatial separation rather than
 * one flat plane of decoration. `offset` is a small {x,y} pointer
 * offset (in px, already clamped/damped by the caller) driving all
 * three; when absent (mobile, or motion-reduced), every layer sits
 * still at its resting position.
 */
function BrandBackdrop({ offset = { x: 0, y: 0 } }) {
  const organicRing = (cx, cy, r, seed) => {
    const points = [];
    const steps = 28;
    for (let i = 0; i <= steps; i++) {
      const angle = (i / steps) * Math.PI * 2;
      const wobble = Math.sin(angle * 3 + seed) * (r * 0.035) + Math.cos(angle * 5 + seed * 2) * (r * 0.02);
      const rr = r + wobble;
      points.push(`${(cx + Math.cos(angle) * rr).toFixed(1)},${(cy + Math.sin(angle) * rr).toFixed(1)}`);
    }
    return `M${points.join(' L')} Z`;
  };

  const layerTransform = (multiplier) => `translate(${(offset.x * multiplier).toFixed(1)}px, ${(offset.y * multiplier).toFixed(1)}px)`;

  return (
    <svg className="brand-backdrop" viewBox="0 0 800 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="ringFade" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stopColor="var(--color-gold)" stopOpacity="0.16" />
          <stop offset="100%" stopColor="var(--color-gold)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* BACKGROUND layer - moves least, reads as furthest away */}
      <g style={{ transform: layerTransform(0.25), transition: 'transform 0.4s cubic-bezier(0.16,1,0.3,1)' }}>
        <g transform="translate(330,300)">
          <circle r="240" fill="url(#ringFade)" />
          {[36, 62, 86, 108, 128, 146, 162, 176, 188].map((r, i) => (
            <path key={r} d={organicRing(0, 0, r, i * 1.7)} fill="none" stroke="var(--color-tan)" strokeWidth="1" opacity={0.5 - i * 0.035} />
          ))}
        </g>
      </g>

      {/* MIDGROUND layer - saw-tooth arc, joinery line, ruler ticks */}
      <g style={{ transform: layerTransform(0.5), transition: 'transform 0.4s cubic-bezier(0.16,1,0.3,1)' }}>
        <g transform="translate(560,560)" opacity="0.4">
          {Array.from({ length: 16 }).map((_, i) => {
            const angle = (i / 16) * Math.PI * 0.9 - Math.PI * 0.1;
            const rInner = 150, rOuter = 172;
            const x1 = Math.cos(angle) * rInner, y1 = Math.sin(angle) * rInner;
            const x2 = Math.cos(angle) * rOuter, y2 = Math.sin(angle) * rOuter;
            return <line key={i} x1={x1.toFixed(1)} y1={y1.toFixed(1)} x2={x2.toFixed(1)} y2={y2.toFixed(1)} stroke="var(--color-gold-soft)" strokeWidth="1.5" />;
          })}
        </g>

        <g stroke="var(--color-tan)" strokeWidth="0.75" opacity="0.25" fill="none">
          <path d="M0,140 L60,140 L85,110 L110,140 L170,140 L195,110 L220,140 L280,140" />
        </g>

        <g stroke="var(--color-gold)" strokeWidth="1" opacity="0.3">
          {Array.from({ length: 14 }).map((_, i) => (
            <line key={i} x1={40 + i * 55} y1="960" x2={40 + i * 55} y2={i % 2 === 0 ? 980 : 972} />
          ))}
        </g>
      </g>

      {/* FOREGROUND layer - an abstracted cabinet-panel corner, cropped
          by the frame edge (Godly-style composition: an element with
          real scale/weight that extends past the boundary, rather than
          everything politely contained inside the viewport). Moves the
          most, reading as the layer closest to the viewer. */}
      <g style={{ transform: layerTransform(0.9), transition: 'transform 0.4s cubic-bezier(0.16,1,0.3,1)' }} opacity="0.5">
        <path
          d="M-40,40 L200,40 L200,340 L120,420 L-40,420 Z"
          fill="none" stroke="var(--color-gold-soft)" strokeWidth="1.25"
        />
        {/* inset panel line, like a cabinet-door detail */}
        <path d="M-10,70 L170,70 L170,300 L100,380 L-10,380 Z" fill="none" stroke="var(--color-gold-soft)" strokeWidth="0.75" opacity="0.6" />
      </g>
    </svg>
  );
}

export default BrandBackdrop;
