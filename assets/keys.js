/* Enter sends, shift-enter makes a new line.
 *
 * What everyone expects from a message box, and it matters more here than in
 * most apps: the whole premise is that logging has to cost less effort than
 * remembering. Reaching for a mouse to save one sentence is the sort of
 * friction that stops a thirteen-year-old bothering.
 *
 * Delegated from document because Dash rebuilds these boxes constantly.
 */
(function () {
  "use strict";

  function submitFor(box) {
    // The button that belongs to this box: the primary action in the same
    // composer, not whatever primary button happens to be first on the page.
    var composer = box.closest(".composer");
    if (!composer) return null;
    return composer.querySelector(".composer-row button.primary");
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.shiftKey) return;
    if (event.isComposing) return;              // mid IME composition
    var box = event.target;
    if (!box || box.tagName !== "TEXTAREA") return;

    var button = submitFor(box);
    if (!button || button.disabled) return;

    event.preventDefault();
    button.click();
  });
})();
