/**
 * KON Ad-Shield for YouTube Embed Player
 * 1. Blocks & auto-skips video advertisements instantaneously.
 * 2. Completely suppresses stuck pause/play central bezel icons (.ytp-bezel).
 * 3. Removes promotional overlays and banner ads.
 */

(function () {
  "use strict";

  // Hide ad banner styling & stuck center pause/play bezels
  const style = document.createElement("style");
  style.textContent = `
    /* Kill stuck center pause/play/volume bezel animation */
    .ytp-bezel,
    .ytp-bezel-icon,
    .ytp-bezel-text,
    .ytp-seek-overlay,
    .ytp-pause-overlay,
    .player-control-play-pause-icon {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
      animation: none !important;
      transition: none !important;
    }

    /* Kill video ads, banners, and promotional cards */
    .ytp-ad-overlay-container,
    .ytp-ad-message-container,
    .ytp-ad-action-interstitial,
    .video-ads,
    .ytp-ad-progress-list,
    #masthead-ad,
    ytd-banner-promo-renderer,
    ytd-in-feed-ad-layout-renderer {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
    }
  `;
  (document.head || document.documentElement).appendChild(style);

  let isFastForwarding = false;

  function removeStuckBezel() {
    const bezels = document.querySelectorAll(
      ".ytp-bezel, .ytp-bezel-icon, .ytp-bezel-text, .ytp-seek-overlay, .ytp-pause-overlay"
    );
    for (const b of bezels) {
      try {
        b.remove();
      } catch (_) {}
    }
  }

  function clickSkipButtons() {
    const selectors = [
      ".ytp-ad-skip-button",
      ".ytp-ad-skip-button-modern",
      ".ytp-skip-ad-button",
      ".ytp-ad-skip-button-slot button",
      ".ytp-ad-overlay-close-button",
      "button.ytp-ad-overlay-close-button",
    ];

    for (const sel of selectors) {
      const btn = document.querySelector(sel);
      if (btn && typeof btn.click === "function") {
        try {
          btn.click();
        } catch (_) {}
      }
    }
  }

  function handleVideoAds() {
    removeStuckBezel();

    const player = document.querySelector(".html5-video-player");
    const video = document.querySelector("video");
    if (!video) return;

    const isAdShowing =
      player?.classList.contains("ad-showing") ||
      player?.classList.contains("ad-interrupting") ||
      document.querySelector(".ytp-ad-player-overlay") !== null;

    if (isAdShowing) {
      // Mute audio during ad to prevent burst
      if (!video.muted) {
        video.muted = true;
      }

      // Fast-forward ad at maximum speed (16x) and seek to end
      isFastForwarding = true;
      video.playbackRate = 16.0;

      if (!isNaN(video.duration) && video.duration > 0) {
        video.currentTime = video.duration - 0.05;
      }

      clickSkipButtons();
    } else if (isFastForwarding) {
      // Ad has finished; restore normal audio and playback speed
      isFastForwarding = false;
      video.playbackRate = 1.0;
      video.muted = false;
    }
  }

  // Fast polling loop during initial load (every 50ms)
  const timer = setInterval(handleVideoAds, 50);

  // MutationObserver to capture state transitions instantly
  const observer = new MutationObserver(() => {
    handleVideoAds();
    clickSkipButtons();
    removeStuckBezel();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class"],
  });

  window.addEventListener("unload", () => {
    clearInterval(timer);
    observer.disconnect();
  });
})();
