/* Speech to text for the journal boxes.
 *
 * The whole premise of this app is that a kid will say something and will not
 * write it, so the microphone is not a nicety.
 *
 * Three things make this fiddly.
 *
 * The textareas are React-controlled, so assigning .value does nothing Dash
 * can see — it has to go through the native setter and then an input event,
 * or the text appears on screen and vanishes on the next callback.
 *
 * The buttons are rebuilt on every render, so listeners bound to them die.
 * The handler delegates from document instead.
 *
 * And the box belongs to the person, not to the recogniser. The first
 * version of this held a snapshot of the text taken when recording started
 * and rewrote the whole box from it on every result, which meant a backspace
 * was undone by the next word and deleting a sentence brought it back as
 * soon as you spoke again. Nothing is held now: each update reads what is
 * actually in the box, removes only the interim words this script put there
 * last time, and appends. Edit mid-sentence and the edit stands.
 */
(function () {
  "use strict";

  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var active = null;

  function setValue(el, value) {
    // Keep the caret where the person left it, unless it was at the very end.
    var atEnd = el.selectionStart === el.value.length;
    var caret = el.selectionStart;

    var proto = window.HTMLTextAreaElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));

    if (atEnd) {
      el.selectionStart = el.selectionEnd = el.value.length;
    } else {
      el.selectionStart = el.selectionEnd = Math.min(caret, el.value.length);
    }
  }

  function targetFor(button) {
    var row = button.closest(".composer-row");
    var box = row && row.parentElement
      ? row.parentElement.querySelector("textarea")
      : null;
    return box || document.querySelector("textarea");
  }

  function stop(button) {
    if (active) {
      try { active.stop(); } catch (e) { /* already stopping */ }
    }
    active = null;
    if (button) {
      button.classList.remove("recording");
      button.textContent = "🎤";
    }
  }

  function start(button) {
    var box = targetFor(button);
    if (!box) return;

    var recognition = new Recognition();
    recognition.lang = "en-GB";
    recognition.interimResults = true;
    recognition.continuous = true;
    // Ask for several guesses so the squash-aware chooser has something to
    // choose between. The right word is often the recogniser's second pick.
    recognition.maxAlternatives = 4;

    // The only thing we remember: the provisional words we last wrote, so we
    // can take them back out again. If they are no longer at the end of the
    // box the person has edited, and we leave their text alone.
    var pending = "";

    function write(finalWords, interimWords) {
      var text = box.value;

      if (pending && text.slice(-pending.length) === pending) {
        text = text.slice(0, text.length - pending.length);
      }
      pending = "";
      text = text.replace(/\s+$/, "");

      if (finalWords) {
        text = (text ? text + " " : "") + finalWords.trim();
      }
      var out = text;
      if (interimWords) {
        pending = (text ? " " : "") + interimWords.trim();
        out = text + pending;
      }
      setValue(box, out);
    }

    recognition.onresult = function (event) {
      var squash = window.ReboundSquash;
      var settled = "";
      var provisional = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var result = event.results[i];
        if (result.isFinal) {
          // Only final results get the full treatment: interim guesses change
          // every few hundred milliseconds and correcting them mid-flight
          // makes the text jump about while the player is still talking.
          var text = squash ? squash.best(result) : result[0].transcript;
          settled += squash ? squash.correct(text) : text;
        } else {
          provisional += result[0].transcript;
        }
      }
      write(settled, provisional);
    };

    recognition.onerror = function (event) {
      if (event.error === "not-allowed") {
        window.alert("Microphone access was blocked. Allow it in the address "
          + "bar, or just type instead.");
      }
      stop(button);
    };

    recognition.onend = function () { stop(button); };

    active = recognition;
    button.classList.add("recording");
    button.textContent = "⏹";
    recognition.start();
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".mic");
    if (!button) return;
    event.preventDefault();

    if (!Recognition) {
      window.alert("This browser has no speech recognition. Chrome has it; "
        + "otherwise just type.");
      return;
    }
    if (active) { stop(button); } else { start(button); }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.body.classList.add(Recognition ? "has-speech" : "no-speech");
  });
})();
