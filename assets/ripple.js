/* A ripple out of the Save button, and the entry that lands glows once.
 *
 * The app asks a thirteen-year-old to write something and then, until now,
 * did nothing visible in return — the text just vanished and a line appeared
 * further down the page. That is a poor trade for the one thing the whole
 * product depends on them doing.
 *
 * So: the button acknowledges the press, and the new entry announces itself
 * when it arrives. Deliberately short and deliberately quiet. This is a
 * record a child keeps about their own training, not a game, and anything
 * that reads as a reward for logging would be the wrong idea — it has to
 * feel like the app received something, not like it is congratulating them.
 *
 * Pure CSS animation, delegated from document because Dash rebuilds these
 * nodes on every render. Honours prefers-reduced-motion.
 */
(function () {
  "use strict";

  var SAVE = ".composer-row button.primary, .composer-row .tab-btn";

  function calm() {
    return window.matchMedia &&
           window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  // The ripple starts where the finger or pointer actually landed, so it
  // reads as a response to the press rather than an animation playing at it.
  document.addEventListener("click", function (event) {
    if (calm()) return;
    var button = event.target.closest(SAVE);
    if (!button) return;

    var box = button.getBoundingClientRect();
    var size = Math.max(box.width, box.height) * 2.2;
    var ink = document.createElement("span");
    ink.className = "ripple-ink";
    ink.style.width = ink.style.height = size + "px";
    ink.style.left = (event.clientX - box.left - size / 2) + "px";
    ink.style.top = (event.clientY - box.top - size / 2) + "px";

    if (getComputedStyle(button).position === "static") {
      button.style.position = "relative";
    }
    button.appendChild(ink);
    setTimeout(function () { ink.remove(); }, 620);
  }, true);

  // When the save lands, Dash rebuilds the list. Glow whichever entry is
  // newest, once, so the thing they just wrote is visibly the thing that
  // arrived.
  var seen = null;
  var observer = new MutationObserver(function () {
    if (calm()) return;
    var composer = document.querySelector(".composer");
    if (!composer) { seen = null; return; }
    var first = composer.querySelector(".entry");
    if (!first) return;
    var text = first.textContent.slice(0, 120);
    if (seen === null) { seen = text; return; }   // first paint is not an arrival
    if (text === seen) return;
    seen = text;
    first.classList.remove("just-landed");
    void first.offsetWidth;                        // restart the animation
    first.classList.add("just-landed");
  });

  function watch() {
    var page = document.getElementById("page");
    if (!page) return setTimeout(watch, 300);
    observer.observe(page, { childList: true, subtree: true });
  }
  watch();
})();
