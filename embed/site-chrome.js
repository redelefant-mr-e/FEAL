/**
 * FEAL site chrome for Figma Sites.
 * - Soft page fade on same-origin navigations
 * - Close mobile menu if left open after a menu link navigation
 * - Vertical margin for headings inside CMS richtext (div.root)
 *
 * Install once: Site settings → Custom code → end of <body>
 *   <script src="…/embed/site-chrome.js?v=2" defer></script>
 *
 * Requires this file on GitHub `main` (jsDelivr). Bump ?v= after push.
 */
(function () {
  "use strict";

  var FADE_MS = 180;
  var MENU_NAV_DELAY_MS = 60;
  var STYLE_ID = "feal-site-chrome-css";
  var CLOSE_FLAG = "feal-close-menu";
  var CLOSE_RE = /^(stäng|close)$/i;
  var RETRY_MS = [0, 50, 150, 400, 900];
  var navigating = false;

  function prefersReducedMotion() {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (e) {
      return false;
    }
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      "html.feal-fade-out{opacity:0;transition:opacity " +
      FADE_MS +
      "ms ease}" +
      "html{transition:opacity " +
      FADE_MS +
      "ms ease}" +
      /* Figma Sites richtext root — breathe around in-flow headings */
      "div.root :is(h1,h2,h3,h4,h5,h6){margin-block:1.25em .75em}" +
      "div.root :is(h1,h2,h3,h4,h5,h6):first-child{margin-block-start:0}";
    document.head.appendChild(style);
  }

  function findCloseButton() {
    var buttons = document.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      var label = (buttons[i].textContent || "").replace(/\s+/g, " ").trim();
      if (CLOSE_RE.test(label)) return buttons[i];
    }
    return null;
  }

  /** Close mobile menu only — clicks existing stäng/close control (sets Figma boolean). */
  function closeMobileMenu() {
    var btn = findCloseButton();
    if (!btn) return false;
    try {
      btn.click();
    } catch (e) {
      btn.dispatchEvent(
        new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          view: window,
        })
      );
    }
    return true;
  }

  function markMenuShouldClose() {
    try {
      sessionStorage.setItem(CLOSE_FLAG, "1");
    } catch (e) {
      /* ignore */
    }
  }

  function consumeCloseFlag() {
    try {
      if (sessionStorage.getItem(CLOSE_FLAG) === "1") {
        sessionStorage.removeItem(CLOSE_FLAG);
        return true;
      }
    } catch (e) {
      /* ignore */
    }
    return false;
  }

  /** Retry close — Figma may hydrate the open menu after first paint. */
  function closeMobileMenuWithRetries() {
    var i = 0;
    function tick() {
      closeMobileMenu();
      i += 1;
      if (i < RETRY_MS.length) {
        window.setTimeout(tick, RETRY_MS[i] - (RETRY_MS[i - 1] || 0));
      }
    }
    tick();

    if (typeof MutationObserver === "undefined") return;
    var obs = new MutationObserver(function () {
      if (closeMobileMenu()) obs.disconnect();
    });
    obs.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    window.setTimeout(function () {
      obs.disconnect();
    }, 2000);
  }

  function sameOriginNavLink(anchor) {
    if (!anchor || !anchor.href) return false;
    if (anchor.target && anchor.target !== "_self") return false;
    if (anchor.hasAttribute("download")) return false;
    try {
      var url = new URL(anchor.href, location.href);
      if (url.origin !== location.origin) return false;
      if (
        url.pathname === location.pathname &&
        url.search === location.search &&
        url.hash
      ) {
        return false;
      }
      return true;
    } catch (e) {
      return false;
    }
  }

  function navigateTo(href) {
    navigating = false;
    location.href = href;
  }

  function softNavigate(href) {
    if (prefersReducedMotion()) {
      navigateTo(href);
      return;
    }
    ensureStyles();
    if (typeof document.startViewTransition === "function") {
      try {
        document.startViewTransition(function () {
          navigateTo(href);
        });
        return;
      } catch (e) {
        /* fall through */
      }
    }
    document.documentElement.classList.add("feal-fade-out");
    window.setTimeout(function () {
      navigateTo(href);
    }, FADE_MS);
  }

  function onDocumentClick(event) {
    if (navigating || event.defaultPrevented) return;
    if (event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    var anchor =
      event.target && event.target.closest
        ? event.target.closest("a[href]")
        : null;
    if (!sameOriginNavLink(anchor)) return;

    var href = anchor.href;
    var menuWasOpen = !!findCloseButton();

    // Take over same-origin nav so we can close the menu before leaving.
    event.preventDefault();
    event.stopPropagation();
    navigating = true;

    if (menuWasOpen) {
      markMenuShouldClose();
      closeMobileMenu();
      // Let Figma finish the boolean/UI update before navigating.
      window.setTimeout(function () {
        softNavigate(href);
      }, MENU_NAV_DELAY_MS);
      return;
    }

    softNavigate(href);
  }

  function boot() {
    ensureStyles();
    navigating = false;
    if (consumeCloseFlag() || findCloseButton()) {
      closeMobileMenuWithRetries();
    } else {
      closeMobileMenu();
    }
  }

  document.addEventListener("click", onDocumentClick, true);
  window.addEventListener("pageshow", boot);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
