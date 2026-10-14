// Model switch in the results section: WAI-ARIA tabs (click, arrow keys, Home/End), no reload.
(function () {
  var list = document.querySelector('.model-switch [role="tablist"]');
  if (!list) return;
  var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));

  function select(tab, focus) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      var panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
    if (focus) tab.focus();
    try {
      localStorage.setItem("geanavid-model-tab", tab.id);
    } catch (e) {
      /* storage may be blocked */
    }
  }

  tabs.forEach(function (tab, i) {
    tab.addEventListener("click", function () {
      select(tab, false);
    });
    tab.addEventListener("keydown", function (e) {
      var next = null;
      if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
      else if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === "Home") next = tabs[0];
      else if (e.key === "End") next = tabs[tabs.length - 1];
      if (next) {
        e.preventDefault();
        select(next, true);
      }
    });
  });

  try {
    var saved = document.getElementById(localStorage.getItem("geanavid-model-tab") || "");
    if (saved && tabs.indexOf(saved) >= 0) select(saved, false);
  } catch (e) {
    /* ignore */
  }
})();
