/* Making browser speech recognition hear squash.
 *
 * The Web Speech API takes no custom vocabulary, so a general language model
 * decides between "boast" and "post" with no idea which court it is on. It
 * picks wrong constantly: boast as post or boost, tin as ten, the T as tea,
 * nick as the name Nick.
 *
 * Two things can be done about that from the browser.
 *
 * First, ask for several alternatives rather than one and choose between
 * them ourselves, scoring each by how much squash is in it. The recogniser
 * often has the right words in its second guess, and it costs nothing to
 * look.
 *
 * Second, a short list of substitutions for the mistakes that survive. This
 * list is deliberately small and guarded. Over-correcting is worse than
 * under-correcting, because a player reads the box and has to trust it: if
 * "I did ten in a row" becomes "I did tin in a row" they stop using the
 * microphone, and that is the feature gone.
 */
window.ReboundSquash = (function () {
  "use strict";

  // Words that mean the transcript is about squash, used to score alternatives.
  var VOCAB = [
    "boast", "drop", "drive", "lob", "volley", "nick", "tin", "kill", "counter",
    "rail", "length", "width", "tight", "straight", "cross", "crosscourt",
    "court", "front", "back", "corner", "wall", "serve", "return", "backhand",
    "forehand", "racket", "racquet", "swing", "prep", "preparation", "grip",
    "follow", "cut", "slice", "block", "routine", "pattern", "squad", "lesson",
    "solo", "rung", "ladder", "quarter", "service", "rally", "stroke", "let",
    "ghosting", "split", "step", "lunge", "pressure", "reset", "deep", "short",
  ];

  // Unambiguous: none of these left-hand strings are squash words, so the
  // substitution cannot eat a legitimate sentence.
  var ALWAYS = [
    [/\bboost(s|ed|ing)?\b/gi, "boast"],
    [/\bbost\b/gi, "boast"],
    [/\bbowst\b/gi, "boast"],
    [/\bdrop shock\b/gi, "drop shot"],
    [/\bcross caught\b/gi, "cross court"],
    [/\bcross-caught\b/gi, "cross court"],
    [/\bvolley drap\b/gi, "volley drop"],
    [/\bghost in\b/gi, "ghosting"],
    [/\bshort line\b/gi, "short line"],
  ];

  // Guarded: only where the surrounding words make the squash reading certain.
  // "ten in a row" must survive, so "tin" is only restored after a verb or
  // article that implies the front wall.
  var GUARDED = [
    [/\b(hit|hits|hitting|into|in|the|a) ten\b/gi, function (m, w) {
      return w + " tin";
    }],
    [/\bten\b(?= on the (drop|drive|boast|kill))/gi, "tin"],
    [/\b(to|on|at|the) tea\b/gi, function (m, w) { return w + " T"; }],
    [/\bhold the tea\b/gi, "hold the T"],
    [/\b(the|a|in the|into the) Nick\b/g, function (m, w) { return w + " nick"; }],
  ];

  function score(text) {
    var low = " " + text.toLowerCase() + " ";
    var hits = 0;
    for (var i = 0; i < VOCAB.length; i++) {
      if (low.indexOf(" " + VOCAB[i]) !== -1) hits++;
    }
    return hits;
  }

  /* Pick the alternative that sounds most like squash. Ties go to the
   * recogniser's own first choice, which is right more often than not. */
  function best(result) {
    var chosen = result[0].transcript;
    var top = score(chosen);
    for (var i = 1; i < result.length; i++) {
      var candidate = result[i].transcript;
      if (score(candidate) > top) {
        chosen = candidate;
        top = score(candidate);
      }
    }
    return chosen;
  }

  function correct(text) {
    var out = text;
    ALWAYS.forEach(function (pair) { out = out.replace(pair[0], pair[1]); });
    GUARDED.forEach(function (pair) { out = out.replace(pair[0], pair[1]); });
    return out;
  }

  return { best: best, correct: correct, score: score, VOCAB: VOCAB };
})();
