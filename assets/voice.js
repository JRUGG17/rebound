/* Speech to text for the journal boxes.
 *
 * The whole premise of this app is that a kid will say something and will not
 * write it, so the microphone is not a nicety.
 *
 * Two things make this fiddly in Dash. The textareas are React-controlled, so
 * assigning .value does nothing Dash can see — it has to go through the
 * native setter and then an input event, or the text appears on screen and
 * vanishes on the next callback. And the buttons are rebuilt on every render,
 * so listeners bound to them die. Both are handled by delegating from
 * document and writing through the React setter.
 */
(function () {
  "use strict";

  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var active = null;

  // Write into a React-controlled textarea so Dash's state actually updates.
  function setValue(el, value) {
    var proto = window.HTMLTextAreaElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
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
    recognition.interimResults = true;   // show words as they are said
    recognition.continuous = true;       // a kid pauses mid-sentence

    // Keep whatever was already typed; speech appends to it.
    var existing = (box.value || "").trim();
    var settled = "";

    recognition.onresult = function (event) {
      var pending = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          settled += chunk;
        } else {
          pending += chunk;
        }
      }
      var parts = [existing, (settled + pending).trim()].filter(Boolean);
      setValue(box, parts.join(" "));
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

  // Flag it so the UI can say so rather than offering a button that cannot work.
  document.addEventListener("DOMContentLoaded", function () {
    document.body.classList.add(Recognition ? "has-speech" : "no-speech");
  });
})();
