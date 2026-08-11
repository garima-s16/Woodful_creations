import React from 'react';

/**
 * Original vector mascot for the Woodful Assistant - young adult male,
 * curly hair, simple t-shirt, friendly minimal expression. Deliberately
 * geometric/clean rather than cartoonish or photorealistic, built from
 * plain shapes in the app's own palette so it never needs an external
 * image asset.
 */
function AssistantMascot({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
      <circle cx="32" cy="32" r="32" fill="var(--color-gold)" />

      {/* shirt / shoulders */}
      <path d="M10 58c2-10 10-16 22-16s20 6 22 16z" fill="var(--color-ink)" />
      <path d="M24 44c3 3 13 3 16 0v4c-3 2-13 2-16 0z" fill="var(--color-ivory)" />

      {/* neck */}
      <rect x="27" y="34" width="10" height="8" rx="3" fill="#e0a86a" />

      {/* head */}
      <ellipse cx="32" cy="26" rx="13" ry="14" fill="#e8b783" />

      {/* curly hair - cluster of small circles around the crown/sides */}
      <g fill="var(--color-ink)">
        <circle cx="20" cy="18" r="5.5" />
        <circle cx="26" cy="12" r="6" />
        <circle cx="34" cy="10" r="6" />
        <circle cx="42" cy="13" r="5.5" />
        <circle cx="46" cy="20" r="5" />
        <circle cx="18" cy="25" r="4.5" />
        <circle cx="45" cy="27" r="4.5" />
      </g>

      {/* face */}
      <circle cx="27" cy="27" r="1.6" fill="var(--color-ink)" />
      <circle cx="37" cy="27" r="1.6" fill="var(--color-ink)" />
      <path d="M26 33c2.5 2 9.5 2 12 0" stroke="var(--color-ink)" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export default AssistantMascot;
