/**
 * FEAL product variant picker for Figma Sites.
 * Reads page slug, loads embed/data/variants.json, mirrors Style Guide UI.
 */
(function () {
  "use strict";

  var MOUNT_ID = "feal-variant-picker";
  var MAILTO = "order@feal.se";
  var DATA_URL_ATTR = "data-variants-url";
  // Bump when CSS/JS change so Sites/jsDelivr clients don't keep a stale stylesheet
  var ASSET_VERSION = "20260918c";

  var I18N = {
    sv: {
      sizeLabel: "Storlek (Längd x Bredd)",
      length: "Längd utfälld:",
      width: "Bredd:",
      foldedHeight: "Höjd hopvikt:",
      weight: "Vikt:",
      maxLoad: "Maxlast*:",
      quote: "Offertförfrågan",
      placeholder: "Välj storlek",
      missingProduct: "Ingen produkt hittades för den här sidan.",
      missingVariants: "Inga varianter tillgängliga.",
      mailSubject: "Offertförfrågan: ",
      mailBody: "Hej,\n\nJag vill gärna ha en offert på följande produkt:\n\n",
      unitMm: " mm",
      unitKg: " kg",
    },
    en: {
      sizeLabel: "Size (Length x Width)",
      length: "Length unfolded:",
      width: "Width:",
      foldedHeight: "Folded height:",
      weight: "Weight:",
      maxLoad: "Max load*:",
      quote: "Request a quote",
      placeholder: "Select size",
      missingProduct: "No product found for this page.",
      missingVariants: "No variants available.",
      mailSubject: "Quote request: ",
      mailBody: "Hello,\n\nI would like a quote for the following product:\n\n",
      unitMm: " mm",
      unitKg: " kg",
    },
  };

  function scriptBaseUrl() {
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].src || "";
      if (src.indexOf("variant-picker.js") !== -1) {
        return src.replace(/\/variant-picker\.js(\?.*)?$/, "/");
      }
    }
    return "./";
  }

  function loadCss(href) {
    if (document.querySelector('link[data-feal-vp-css="1"]')) return;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.setAttribute("data-feal-vp-css", "1");
    document.head.appendChild(link);
  }

  function qs(name) {
    try {
      return new URLSearchParams(window.location.search).get(name);
    } catch (e) {
      return null;
    }
  }

  function normalizeSlug(raw) {
    if (!raw) return "";
    return String(raw)
      .trim()
      .replace(/^\/+|\/+$/g, "")
      .split("/")
      .filter(Boolean)
      .pop()
      .toLowerCase();
  }

  function detectLang(mount) {
    var attr = (mount.getAttribute("data-lang") || "").toLowerCase();
    if (attr === "en" || attr === "sv") return attr;
    var fromQuery = (qs("lang") || "").toLowerCase();
    if (fromQuery === "en" || fromQuery === "sv") return fromQuery;

    // Path: /en/… or any segment starting with en- (e.g. /en-portabla-ramper-produkt/…)
    var path = (window.location.pathname || "").toLowerCase();
    if (/(^|\/)en(\/|$)/.test(path)) return "en";
    var segments = path.split("/").filter(Boolean);
    for (var i = 0; i < segments.length; i++) {
      if (segments[i] === "en" || segments[i].indexOf("en-") === 0) return "en";
    }

    // Figma Sites page Language → usually <html lang="en">
    try {
      var htmlLang = (
        document.documentElement.getAttribute("lang") ||
        ""
      ).toLowerCase();
      if (htmlLang === "en" || htmlLang.indexOf("en-") === 0) return "en";
    } catch (e) {}

    return "sv";
  }

  function resolveProductSlug(mount) {
    var fromAttr = mount.getAttribute("data-product");
    if (fromAttr) return normalizeSlug(fromAttr);
    var fromQuery = qs("product");
    if (fromQuery) return normalizeSlug(fromQuery);
    return normalizeSlug(window.location.pathname);
  }

  function sizeLabel(variant) {
    var L = variant.length_mm;
    var W = variant.width_mm;
    if (L && W) return L + " × " + W + " mm";
    if (L) return L + " mm";
    if (W) return W + " mm";
    return variant.article_number || variant.slug || "";
  }

  function displayName(variant, lang) {
    return (lang === "en" ? variant.name_en : variant.name_sv) || sizeLabel(variant);
  }

  function formatMm(value, t) {
    if (!value) return "";
    return value + t.unitMm;
  }

  function formatKg(value, t) {
    if (!value) return "";
    return String(value) + t.unitKg;
  }

  function chevronSvg() {
    return (
      '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M3.2 5.6 8 10.4l4.8-4.8 1.1 1.1L8 12.6 2.1 6.7z"/>' +
      "</svg>"
    );
  }

  function buildMailto(variant, lang, t) {
    var name = displayName(variant, lang);
    var subject = t.mailSubject + name;
    var body = t.mailBody + name + "\n";
    if (variant.article_number) body += "Art.nr: " + variant.article_number + "\n";
    return (
      "mailto:" +
      MAILTO +
      "?subject=" +
      encodeURIComponent(subject) +
      "&body=" +
      encodeURIComponent(body)
    );
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "omit" }).then(function (res) {
      if (!res.ok) throw new Error("Failed to load " + url + " (" + res.status + ")");
      return res.json();
    });
  }

  function render(mount, catalog) {
    var lang = detectLang(mount);
    var t = I18N[lang] || I18N.sv;
    var productSlug = resolveProductSlug(mount);
    var entry = catalog[productSlug];
    var variants = entry && entry.variants ? entry.variants.slice() : [];

    mount.className = "feal-vp";
    mount.setAttribute("data-product-slug", productSlug || "");
    mount.innerHTML = "";

    if (!productSlug || !entry) {
      mount.innerHTML =
        '<p class="feal-vp__status">' + escapeHtml(t.missingProduct) + "</p>";
      return;
    }
    if (!variants.length) {
      mount.innerHTML =
        '<p class="feal-vp__status">' + escapeHtml(t.missingVariants) + "</p>";
      return;
    }

    var selectedIndex = -1;
    var root = document.createElement("div");
    root.className = "feal-vp__stack";

    var dropdown = document.createElement("div");
    dropdown.className = "feal-vp__dropdown";

    var label = document.createElement("p");
    label.className = "feal-vp__label";
    label.id = mount.id + "-label";
    label.textContent = t.sizeLabel;

    var selectBtn = document.createElement("button");
    selectBtn.type = "button";
    selectBtn.className = "feal-vp__select";
    selectBtn.setAttribute("aria-haspopup", "listbox");
    selectBtn.setAttribute("aria-expanded", "false");
    selectBtn.setAttribute("aria-labelledby", label.id);

    var valueEl = document.createElement("p");
    valueEl.className = "feal-vp__select-value";
    valueEl.textContent = t.placeholder;

    var list = document.createElement("ul");
    list.className = "feal-vp__select-list";
    list.setAttribute("role", "listbox");

    variants.forEach(function (variant, index) {
      var li = document.createElement("li");
      var opt = document.createElement("button");
      opt.type = "button";
      opt.setAttribute("role", "option");
      opt.setAttribute("aria-selected", "false");
      opt.dataset.index = String(index);
      opt.textContent = sizeLabel(variant);
      opt.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        selectVariant(index);
        closeDropdown();
      });
      li.appendChild(opt);
      list.appendChild(li);
    });

    var chevron = document.createElement("span");
    chevron.className = "feal-vp__chevron";
    chevron.innerHTML = chevronSvg();

    selectBtn.appendChild(valueEl);
    selectBtn.appendChild(list);
    selectBtn.appendChild(chevron);

    selectBtn.addEventListener("click", function (e) {
      // Option clicks stopPropagation; toggle open/close otherwise
      if (e.target.closest(".feal-vp__select-list button")) return;
      if (mount.classList.contains("is-open")) closeDropdown();
      else openDropdown();
    });

    dropdown.appendChild(label);
    dropdown.appendChild(selectBtn);

    var variantBlock = document.createElement("div");
    variantBlock.className = "feal-vp__variant";
    variantBlock.setAttribute("aria-live", "polite");

    var actions = document.createElement("div");
    actions.className = "feal-vp__actions";
    var quoteBtn = document.createElement("a");
    quoteBtn.className = "feal-vp__button";
    quoteBtn.textContent = t.quote;
    quoteBtn.setAttribute("href", "#");
    actions.appendChild(quoteBtn);

    root.appendChild(dropdown);
    root.appendChild(variantBlock);
    root.appendChild(actions);
    mount.appendChild(root);

    function openDropdown() {
      mount.classList.add("is-open");
      selectBtn.setAttribute("aria-expanded", "true");
    }

    function closeDropdown() {
      mount.classList.remove("is-open");
      selectBtn.setAttribute("aria-expanded", "false");
    }

    function selectVariant(index) {
      selectedIndex = index;
      var variant = variants[index];
      mount.classList.add("has-selection");
      valueEl.textContent = sizeLabel(variant);

      list.querySelectorAll("button").forEach(function (btn, i) {
        btn.setAttribute("aria-selected", i === index ? "true" : "false");
      });

      renderVariantDetails(variantBlock, variant, lang, t);
      quoteBtn.href = buildMailto(variant, lang, t);
    }

    document.addEventListener("click", function (e) {
      if (!mount.contains(e.target)) closeDropdown();
    });

    // Auto-select first variant so Step-3 layout is visible by default on product pages
    // Keep closed until user opens — but show details after first selection only.
    // Design Step 1 = closed empty-ish; we use placeholder until pick.
  }

  function renderVariantDetails(container, variant, lang, t) {
    container.innerHTML = "";

    var title = document.createElement("p");
    title.className = "feal-vp__variant-title";
    title.textContent = displayName(variant, lang);
    container.appendChild(title);

    var rows = [
      { label: t.length, value: formatMm(variant.length_mm, t) },
      { label: t.width, value: formatMm(variant.width_mm, t) },
      { label: t.foldedHeight, value: formatMm(variant.folded_height_mm, t) },
      { label: t.weight, value: formatKg(variant.weight_kg, t) },
      { label: t.maxLoad, value: formatKg(variant.max_load_kg, t) },
    ];

    rows.forEach(function (row) {
      if (!row.value) return;
      var lab = document.createElement("p");
      lab.className = "feal-vp__spec-label";
      lab.textContent = row.label;
      var val = document.createElement("p");
      val.className = "feal-vp__spec-value";
      val.textContent = row.value;
      container.appendChild(lab);
      container.appendChild(val);
    });

    var footnote = (lang === "en" ? variant.footnote_en : variant.footnote_sv) || "";
    if (footnote) {
      var note = document.createElement("p");
      note.className = "feal-vp__footnote";
      note.textContent = footnote;
      container.appendChild(note);
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function boot() {
    var mount = document.getElementById(MOUNT_ID);
    if (!mount) return;

    var base = scriptBaseUrl();
    loadCss(base + "variant-picker.css?v=" + ASSET_VERSION);

    var dataUrl =
      mount.getAttribute(DATA_URL_ATTR) ||
      qs("variantsUrl") ||
      base + "data/variants.json?v=" + ASSET_VERSION;

    fetchJson(dataUrl)
      .then(function (catalog) {
        render(mount, catalog);
      })
      .catch(function (err) {
        mount.className = "feal-vp";
        mount.innerHTML =
          '<p class="feal-vp__status">' +
          escapeHtml(err && err.message ? err.message : String(err)) +
          "</p>";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
