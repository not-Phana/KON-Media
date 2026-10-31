import React from "react";

/**
 * Custom vector icon for KON Search 1.2 Rei Flash (Speed Mode).
 * Replaces generic emojis with a bespoke, aerodynamic kinetic lightning bolt.
 */
export function KonFlashIcon({ className = "w-3.5 h-3.5", ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 inline-block ${className}`}
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="kon-flash-grad" x1="5" y1="2" x2="19" y2="22" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FBBF24" />
          <stop offset="50%" stopColor="#F59E0B" />
          <stop offset="100%" stopColor="#D97706" />
        </linearGradient>
      </defs>
      {/* Aerodynamic sculpted kinetic flash bolt */}
      <path
        d="M13.8 2.2C13.5 1.6 12.8 1.4 12.2 1.7C11.9 1.9 11.6 2.2 11.5 2.6L6.2 12.2C5.8 12.9 6.3 13.8 7.1 13.8H11.5L9.6 21.6C9.4 22.4 10.3 23 10.9 22.5L18.4 12.8C18.9 12.1 18.4 11.2 17.6 11.2H13.2L14.2 3.2C14.3 2.8 14.1 2.4 13.8 2.2Z"
        fill="url(#kon-flash-grad)"
      />
      {/* Internal kinetic highlight streak */}
      <path
        d="M11.8 4L7.8 12.5H11L9.8 18.5L16.5 12H12.8L13.5 4H11.8Z"
        fill="white"
        fillOpacity="0.32"
      />
    </svg>
  );
}

/**
 * Custom vector icon for KON Search 1.2 Rei (Precision Mode).
 * Replaces generic emojis with a calibrated optical reticle and focal pip.
 */
export function KonPrecisionIcon({ className = "w-3.5 h-3.5", ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 inline-block ${className}`}
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="kon-prec-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#0084FF" />
        </linearGradient>
      </defs>
      {/* Outer calibration dashed ring */}
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="url(#kon-prec-grad)"
        strokeWidth="1.8"
        strokeDasharray="2.5 2"
      />
      {/* Precision inner focus circle */}
      <circle
        cx="12"
        cy="12"
        r="4.5"
        stroke="url(#kon-prec-grad)"
        strokeWidth="1.5"
      />
      {/* Cardinal crosshair tick marks */}
      <line x1="12" y1="1" x2="12" y2="4.5" stroke="#0084FF" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="12" y1="19.5" x2="12" y2="23" stroke="#0084FF" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="1" y1="12" x2="4.5" y2="12" stroke="#0084FF" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="19.5" y1="12" x2="23" y2="12" stroke="#0084FF" strokeWidth="1.8" strokeLinecap="round" />
      {/* Center target pip */}
      <circle cx="12" cy="12" r="1.8" fill="#0084FF" />
    </svg>
  );
}

/**
 * Custom vector icon for Continuous Autonomous Training.
 */
export function KonTrainingIcon({ className = "w-3.5 h-3.5", ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 inline-block ${className}`}
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="kon-train-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#10B981" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
      </defs>
      <path
        d="M21 12C21 16.9706 16.9706 21 12 21C8.2 21 4.9 18.6 3.6 15.2M3 12C3 7.02944 7.02944 3 12 3C15.8 3 19.1 5.4 20.4 8.8"
        stroke="url(#kon-train-grad)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="3" fill="#10B981" />
      <path d="M21 4V9H16" stroke="url(#kon-train-grad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 20V15H8" stroke="url(#kon-train-grad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default {
  KonFlashIcon,
  KonPrecisionIcon,
  KonTrainingIcon,
};
