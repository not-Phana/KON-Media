import React from "react";

export default function KonLogo({ size = 42, className = "" }) {
  return (
    <div
      className={`relative shrink-0 flex items-center justify-center rounded-2xl neu-raised ${className}`}
      style={{ width: size, height: size }}
      title="KON Media"
    >
      <svg
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full p-1.5"
      >
        <defs>
          <linearGradient id="kon-blue-grad" x1="16" y1="16" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="100%" stopColor="#0084FF" />
          </linearGradient>
          <linearGradient id="kon-spine-grad" x1="16" y1="16" x2="23" y2="48" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#64748B" />
            <stop offset="100%" stopColor="#334155" />
          </linearGradient>
        </defs>

        {/* K Vertical Spine */}
        <rect
          x="16"
          y="16"
          width="7"
          height="32"
          rx="3.5"
          fill="url(#kon-spine-grad)"
        />

        {/* K Upper Diagonal */}
        <path
          d="M21 32L39 17C40.5 15.8 42.5 17 42.5 19V20C42.5 21 41.8 22 40.8 22.8L27 34L21 32Z"
          fill="url(#kon-blue-grad)"
        />

        {/* K Lower Diagonal */}
        <path
          d="M25 32L41 46.5C42 47.4 42.6 48.5 42.6 49.5V50.5C42.6 52.5 40.5 53.7 39 52.5L21 36L25 32Z"
          fill="url(#kon-blue-grad)"
        />

        {/* Media Play Spark */}
        <circle cx="48" cy="32" r="3" fill="#0084FF" />
      </svg>
    </div>
  );
}
