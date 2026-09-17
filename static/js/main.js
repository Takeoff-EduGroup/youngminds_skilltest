/* Shared behaviour: flash dismiss, password toggle, client-side form checks */
(function () {
  "use strict";

  // Dismiss flash messages
  document.querySelectorAll(".flash-close").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.closest(".flash").remove(); });
  });

  // Show / hide password
  document.querySelectorAll(".pw-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.getElementById(btn.dataset.target);
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
    });
  });

  var messages = {
    name: "Enter your full name using letters only (at least 3 characters).",
    password: "Enter your password.",
    department: "Select your department.",
    year: "Select your year of study."
  };

  function setError(field, text) {
    var wrap = field.closest(".field");
    if (!wrap) return;
    var slot = wrap.querySelector(".error-text");
    wrap.classList.toggle("has-error", !!text);
    if (slot) slot.textContent = text || "";
  }

  function check(field, form) {
    var name = field.name;
    var value = field.type === "radio"
      ? (form.querySelector('input[name="' + name + '"]:checked') || {}).value || ""
      : field.value.trim();
    var msg = "";

    if (field.required && !value) {
      msg = messages[name] || "This field is required.";
    } else if (name === "name" && !/^[A-Za-z][A-Za-z .'-]{2,119}$/.test(value)) {
      msg = messages.name;
    }
    setError(field, msg);
    return !msg;
  }

  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    var fields = form.querySelectorAll("input[name]:not([type=hidden]), select[name]");

    fields.forEach(function (field) {
      field.addEventListener("blur", function () { if (field.type !== "radio") check(field, form); });
      field.addEventListener("change", function () { check(field, form); });
    });

    form.addEventListener("submit", function (e) {
      var ok = true, firstBad = null, seen = {};
      fields.forEach(function (field) {
        if (field.type === "radio") {
          if (seen[field.name]) return;
          seen[field.name] = true;
        }
        if (!check(field, form)) {
          ok = false;
          if (!firstBad) firstBad = field;
        }
      });
      if (!ok) {
        e.preventDefault();
        firstBad.focus();
      }
    });
  });
})();
