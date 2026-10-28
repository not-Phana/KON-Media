import React from "react";

export default function KonLogo({ size = 40, className = "" }) {
  return (
    <div
      className={`relative shrink-0 flex items-center justify-center rounded-xl bg-gradient-to-br from-[#242831] to-[#16181D] border border-[#383D46] shadow-md ${className}`}
      style={{ width: size, height: size }}
      title="KON Media"
    >
      <svg
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full p-1"
      >
        <defs>
          <linearGradient id="kon-mint-grad" x1="24" y1="16" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#A8DFCB" />
            <stop offset="100%" stopColor="#72B69F" />
          </linearGradient>
          <linearGradient id="kon-spine-grad" x1="16" y1="16" x2="23" y2="48" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#4A5260" />
            <stop offset="100%" stopColor="#2D333D" />
          </linearGradient>
          <filter id="kon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="1.5" stdDeviation="2" floodColor="#8BC5B0" floodOpacity="0.4" />
          </filter>
        </defs>

        {/* Inner Soft Bevel */}
        <rect
          x="3"
          y="3"
          width="58"
          height="58"
          rx="14"
          fill="none"
          stroke="#484F5B"
          strokeWidth="0.8"
          strokeOpacity="0.5"
        />

        {/* K Vertical Spine */}
        <rect
          x="16"
          y="16"
          width="7"
          height="32"
          rx="3.5"
          fill="url(#kon-spine-grad)"
          stroke="#555E6E"
          strokeWidth="0.75"
        />

        {/* Media Chevron (K Arms + Play Momentum) */}
        <path
          d="M25 32 L39.5 19 C41.2 17.5 44 18.7 44 21 L44 23 C44 24 43.5 25 42.6 25.7 L33.2 33.5 L42.6 41.3 C43.5 42 44 43 44 44 L44 46 C44 48.3 41.2 49.5 39.5 48 L25 35 C23.8 34 23.8 32.2 25 32 Z"
          fill="url(#kon-mint-grad)"
          filter="url(#kon-glow)"
        />
      </svg>
    </div>
  );
}
