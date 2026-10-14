(function () {
  var form = document.getElementById("contact-form");
  if (!form) return;

  var endpoint = form.getAttribute("data-endpoint");
  var project = form.getAttribute("data-project");
  var status = document.getElementById("contact-status");
  var button = form.querySelector("button[type=submit]");
  var mail = "hello@apertool.ch";
  var openedAt = Date.now();

  var fields = {
    name: form.elements["name"],
    email: form.elements["email"],
    message: form.elements["message"],
  };

  var problems = {
    name: "Please enter your name.",
    email: "Please enter a valid e-mail address.",
    message: "Please write a message of at least 10 characters.",
  };

  function say(state, text, withMail) {
    status.setAttribute("data-state", state);
    status.textContent = text;
    if (withMail) {
      var link = document.createElement("a");
      link.href = "mailto:" + mail;
      link.textContent = mail;
      status.appendChild(link);
      status.appendChild(document.createTextNode("."));
    }
  }

  function clearInvalid() {
    Object.keys(fields).forEach(function (key) {
      fields[key].removeAttribute("aria-invalid");
    });
  }

  function firstProblem() {
    var name = fields.name.value.trim();
    var email = fields.email.value.trim();
    var message = fields.message.value.trim();
    if (!name || name.length > 100) return "name";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email) || email.length > 254)
      return "email";
    if (message.length < 10 || message.length > 5000) return "message";
    return null;
  }

  function failureText(code) {
    if (code === "too_fast")
      return "That was very quick. Please check your message and send it again.";
    if (code === "rate_limited")
      return "Too many messages from your network just now. Please try again later or write to ";
    return "Sorry, the message could not be sent. Please try again later or write to ";
  }

  function finish() {
    button.disabled = false;
    form.removeAttribute("aria-busy");
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (button.disabled) return;
    clearInvalid();

    var bad = firstProblem();
    if (bad) {
      fields[bad].setAttribute("aria-invalid", "true");
      say("error", problems[bad]);
      fields[bad].focus();
      return;
    }

    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    say("pending", "Sending…");

    var body = JSON.stringify({
      name: fields.name.value.trim(),
      email: fields.email.value.trim(),
      message: fields.message.value.trim(),
      project: project,
      website: form.elements["website"].value,
      opened_at: openedAt,
      sent_at: Date.now(),
    });

    var controller = "AbortController" in window ? new AbortController() : null;
    var timer = setTimeout(function () {
      if (controller) controller.abort();
    }, 20000);

    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body,
      credentials: "omit",
      referrerPolicy: "no-referrer",
      signal: controller ? controller.signal : undefined,
    })
      .then(function (response) {
        return response.json().then(
          function (data) {
            return { ok: response.ok && data && data.ok === true, code: data && data.error };
          },
          function () {
            return { ok: false, code: "unavailable" };
          },
        );
      })
      .catch(function () {
        return { ok: false, code: "unavailable" };
      })
      .then(function (result) {
        clearTimeout(timer);
        finish();
        if (result.ok) {
          form.reset();
          openedAt = Date.now();
          say("success", "Thank you. Your message is on its way to Team Apertool.");
        } else {
          say("error", failureText(result.code), result.code !== "too_fast");
        }
      });
  });

  form.hidden = false;
})();
