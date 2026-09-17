/* Quiz page: one question at a time, answer palette, countdown timer, submit confirmation */
(function () {
  "use strict";

  var form = document.getElementById("quiz-form");
  if (!form) return;

  var questions = Array.prototype.slice.call(form.querySelectorAll(".question"));
  var paletteBtns = Array.prototype.slice.call(document.querySelectorAll(".palette-btn"));
  var prevBtn = document.getElementById("prev-btn");
  var nextBtn = document.getElementById("next-btn");
  var clearBtn = document.getElementById("clear-btn");
  var submitBtn = document.getElementById("submit-btn");
  var answeredCount = document.getElementById("answered-count");
  var dialog = document.getElementById("confirm-dialog");
  var confirmText = document.getElementById("confirm-text");
  var current = 0;
  var submitting = false;

  function isAnswered(q) { return !!q.querySelector("input:checked"); }

  function render() {
    var answered = 0;
    questions.forEach(function (q, i) {
      q.classList.toggle("active", i === current);
      var done = isAnswered(q);
      if (done) answered++;
      paletteBtns[i].classList.toggle("answered", done);
      paletteBtns[i].classList.toggle("current", i === current);
      paletteBtns[i].setAttribute("aria-current", i === current ? "step" : "false");
    });
    answeredCount.textContent = answered;
    prevBtn.disabled = current === 0;
    nextBtn.textContent = current === questions.length - 1 ? "Review and submit" : "Next";
    clearBtn.disabled = !isAnswered(questions[current]);
  }

  function go(index, focus) {
    current = Math.max(0, Math.min(questions.length - 1, index));
    render();
    if (focus) {
      var first = questions[current].querySelector("input:checked") || questions[current].querySelector("input");
      if (first) first.focus({ preventScroll: true });
    }
    if (window.innerWidth < 960) {
      questions[current].scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  prevBtn.addEventListener("click", function () { go(current - 1, true); });
  nextBtn.addEventListener("click", function () {
    if (current === questions.length - 1) openConfirm();
    else go(current + 1, true);
  });
  clearBtn.addEventListener("click", function () {
    questions[current].querySelectorAll("input").forEach(function (i) { i.checked = false; });
    render();
  });
  paletteBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { go(parseInt(btn.dataset.goto, 10), true); });
  });
  form.addEventListener("change", render);

  // Keyboard shortcuts: A-D choose, arrow keys move
  document.addEventListener("keydown", function (e) {
    if (dialog.open || e.ctrlKey || e.metaKey || e.altKey) return;
    var key = e.key.toUpperCase();
    if (["A", "B", "C", "D"].indexOf(key) !== -1) {
      var input = questions[current].querySelector('input[value="' + key + '"]');
      if (input) { input.checked = true; render(); }
    } else if (e.key === "ArrowRight" && e.target.type !== "radio") {
      go(current + 1);
    } else if (e.key === "ArrowLeft" && e.target.type !== "radio") {
      go(current - 1);
    }
  });

  // Submit confirmation
  function openConfirm() {
    var unanswered = questions.filter(function (q) { return !isAnswered(q); }).length;
    confirmText.textContent = unanswered
      ? unanswered + " question" + (unanswered === 1 ? " is" : "s are") + " not answered and will score zero. You can't change answers after submitting."
      : "All questions are answered. You can't change answers after submitting.";
    if (typeof dialog.showModal === "function") dialog.showModal();
    else if (window.confirm(confirmText.textContent)) doSubmit();
  }
  function doSubmit() {
    if (submitting) return;
    submitting = true;
    window.removeEventListener("beforeunload", warnLeave);
    form.submit();
  }
  submitBtn.addEventListener("click", openConfirm);
  document.getElementById("confirm-cancel").addEventListener("click", function () { dialog.close(); });
  document.getElementById("confirm-submit").addEventListener("click", doSubmit);

  // Warn before leaving mid-test
  function warnLeave(e) { e.preventDefault(); e.returnValue = ""; }
  window.addEventListener("beforeunload", warnLeave);

  // Countdown timer (server supplies remaining seconds so refresh doesn't reset it)
  var timer = document.getElementById("timer");
  var timerValue = document.getElementById("timer-value");
  var endAt = Date.now() + parseInt(form.dataset.remaining, 10) * 1000;

  function tick() {
    var left = Math.max(0, Math.round((endAt - Date.now()) / 1000));
    var m = Math.floor(left / 60), s = left % 60;
    timerValue.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    timer.classList.toggle("warning", left <= 120 && left > 30);
    timer.classList.toggle("danger", left <= 30);
    if (left === 60) timer.setAttribute("aria-live", "polite");
    if (left <= 0) {
      clearInterval(interval);
      if (dialog.open) dialog.close();
      doSubmit();
    }
  }
  var interval = setInterval(tick, 1000);
  tick();

  render();
})();
