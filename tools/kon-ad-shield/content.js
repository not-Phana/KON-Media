/**
 * KON Ad-Shield for YouTube Embed Player
 * Intercepts video ads inside YouTube embed iframes and skips them instantaneously.
 */

(function () {
  "use strict";

  // Hide ad banner styling dynamically
  const style = document.createElement("style");
  style.textContent = `
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
