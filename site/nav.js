/* Shared site navigation — one source of truth for all four pages.
 *
 * Before this, every page rolled its own: index.html had three gold cabinet buttons in
 * the header, while arcade/daily/gridiron each had a different line of text links
 * ("← back to the league · daily puzzles · gridiron →"). Nothing told you where you
 * were, the targets were text-sized, and adding a page meant editing four files and
 * getting it slightly wrong in at least one.
 *
 * Two presentations, one component:
 *   Desktop  — a bar under the header, current page marked.
 *   Phone    — a fixed tab bar pinned to the BOTTOM. That's deliberate: on a 6"+ phone
 *              the top of the screen is out of thumb reach one-handed, and these pages
 *              are long enough that a top nav scrolls away exactly when you want it.
 *
 * Injected by script so the markup can't drift between pages. If JS fails the pages are
 * still fully usable and cross-linked by their own in-page links; navigation degrades,
 * it doesn't disappear.
 */
(function () {
  "use strict";

  var PAGES = [
    { href: "index.html",    label: "LEAGUE",   icon: "☰" },
    { href: "arcade.html",   label: "ARCADE",   icon: "▶" },
    { href: "daily.html",    label: "DAILY",    icon: "★" },
    { href: "gridiron.html", label: "GRIDIRON", icon: "◆" }
  ];

  // "" and "/" both mean the league page.
  var here = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  if (here === "") here = "index.html";

  var CSS = [
    ":root { --nav-h: 58px; }",

    /* ---- shared ---- */
    ".sitenav { font-family: var(--font-display, monospace); }",
    ".sitenav a {",
    "  display: flex; align-items: center; justify-content: center; gap: 7px;",
    "  text-decoration: none; color: var(--text-dim, #9fb89f);",
    "  border: 2px solid var(--line-strong, #2f5d33);",
    "  background: var(--panel, #0d1a0f);",
    /* 44px is the Apple HIG minimum comfortable touch target; these clear it. */
    "  min-height: 44px; padding: 0 12px; font-size: 11px; letter-spacing: .5px;",
    "  -webkit-tap-highlight-color: transparent;",
    "}",
    ".sitenav a:hover { color: var(--text, #dff5df); border-color: var(--accent, #FFC53D); }",
    ".sitenav a[aria-current='page'] {",
    "  color: #10210f; background: var(--accent, #FFC53D);",
    "  border-color: var(--accent, #FFC53D); font-weight: bold;",
    "}",
    ".sitenav .ico { font-size: 13px; line-height: 1; }",

    /* ---- desktop: inline bar ---- */
    "@media (min-width: 721px) {",
    "  .sitenav { display: flex; gap: 8px; margin: 0 0 18px; flex-wrap: wrap; }",
    "  .sitenav a { flex: 0 0 auto; }",
    "}",

    /* ---- phone: fixed bottom tab bar ---- */
    "@media (max-width: 720px) {",
    "  .sitenav {",
    /* Fixed to the viewport. Note this is sized by the initial containing block
       (window.innerWidth), which on a real phone equals the layout viewport but in a
       scaled device emulator does not — if the last tab looks clipped in a desktop
       emulator, that is the emulator, not the layout. Sticky is not an alternative here:
       bottom-sticky only pins an element that sits LAST in its container, and this bar
       is mounted near the top so the desktop layout reads correctly. */
    "    position: fixed; left: 0; right: 0; bottom: 0; z-index: 9999;",
    "    display: grid; grid-template-columns: repeat(" + PAGES.length + ", 1fr); gap: 0;",
    "    background: var(--panel, #0d1a0f);",
    "    border-top: 3px solid var(--line-strong, #2f5d33);",
    /* Keep the bar clear of the home indicator on notched iPhones. */
    "    padding-bottom: env(safe-area-inset-bottom, 0px);",
    "  }",
    "  .sitenav a {",
    "    flex-direction: column; gap: 3px; border: none; border-radius: 0;",
    "    min-height: var(--nav-h); font-size: 9px; padding: 8px 2px;",
    "    border-right: 2px solid var(--line, #1d3a20);",
    "  }",
    "  .sitenav a:last-child { border-right: none; }",
    "  .sitenav a[aria-current='page'] { background: var(--accent, #FFC53D); }",
    "  .sitenav .ico { font-size: 15px; }",
    /* Nothing should hide behind the bar at the end of a scroll. */
    "  body { padding-bottom: calc(var(--nav-h) + env(safe-area-inset-bottom, 0px) + 12px) !important; }",
    "}",

    /* The old per-page link rows are redundant once this exists, and on a phone they
       were the only way to move between pages — small, inline and easy to miss. */
    ".legacy-nav { display: none !important; }",

    /* ---- shared touch ergonomics ----
       Every page was built mouse-first: week chips rendered 32px tall and the panel tabs
       41px, well under the 44px Apple calls the minimum comfortable target. An audit at
       390px found 21 such controls on the arcade page alone. This is in the shared file
       on purpose — it should apply everywhere, and stay applied to pages added later. */
    "@media (max-width: 720px) {",
    "  button, .opt, select, input, a.arcade-link { min-height: 44px; }",
    /* iOS zooms the whole page when you focus a field whose text is under 16px. That
       applies to form fields only — forcing it on buttons blew the week and matchup
       chips up to three times their size, because they're set in the display face. */
    "  input, select, textarea { font-size: max(1em, 16px); }",
    "  button, .opt { padding-top: 8px; padding-bottom: 8px; }",
    /* Dense button rows wrap rather than squeeze below a thumb's width. */
    "  .row, .tabs { flex-wrap: wrap; gap: 8px; }",
    "}"
  ].join("\n");

  function mount() {
    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    var nav = document.createElement("nav");
    nav.className = "sitenav";
    nav.setAttribute("aria-label", "Site");
    nav.innerHTML = PAGES.map(function (p) {
      var cur = p.href.toLowerCase() === here;
      return '<a href="' + p.href + '"' + (cur ? ' aria-current="page"' : "") + ">" +
        '<span class="ico" aria-hidden="true">' + p.icon + "</span>" +
        "<span>" + p.label + "</span></a>";
    }).join("");

    // Mounted in ONE place for both layouts, deliberately: on phones the bar is
    // position:fixed, which takes it out of flow and pins it to the bottom wherever it
    // sits in the DOM. Choosing the mount point from a media query at load time instead
    // would leave the bar stranded mid-page for anyone who rotates the phone or resizes.
    var wrap = document.querySelector(".wrap") || document.body;
    var header = wrap.querySelector("header");
    if (header && header.parentNode === wrap) wrap.insertBefore(nav, header.nextSibling);
    else wrap.insertBefore(nav, wrap.firstChild);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
