(function () {
  var q = new URLSearchParams(location.search);
  var slides = [].slice.call(document.querySelectorAll(".slide"));
  var one = parseInt(q.get("slide") || "", 10);
  if (one) {
    document.body.classList.add("single");
    if (slides[one - 1]) slides[one - 1].classList.add("on");
    return;
  }
  if (q.has("print") || q.has("all")) return;

  var body = document.body,
    cur = -1;
  var cnt = document.querySelector(".cnt"),
    bar = document.querySelector(".prog i");
  body.classList.add("present");
  function fit() {
    body.style.setProperty(
      "--k",
      Math.min(innerWidth / 1920, innerHeight / 1080),
    );
  }
  fit();
  addEventListener("resize", fit);
  function pad(n) {
    return (n < 10 ? "0" : "") + n;
  }
  function show(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (i === cur) return;
    if (cur >= 0) slides[cur].classList.remove("on", "play");
    cur = i;
    var s = slides[cur];
    s.classList.add("on");
    void s.offsetWidth;
    s.classList.add("play");
    cnt.textContent = pad(cur + 1) + " / " + pad(slides.length);
    bar.style.width = ((cur + 1) / slides.length) * 100 + "%";
    if (location.hash !== "#" + (cur + 1))
      history.replaceState(null, "", "#" + (cur + 1));
  }
  function go(d) {
    show(cur + d);
  }
  function fs() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen)
      document.documentElement.requestFullscreen();
  }
  var idle;
  addEventListener("mousemove", function () {
    body.classList.remove("idle");
    clearTimeout(idle);
    idle = setTimeout(function () {
      body.classList.add("idle");
    }, 2600);
  });
  addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var k = e.key;
    if (
      k === "ArrowRight" ||
      k === "PageDown" ||
      k === " " ||
      k === "Enter"
    ) {
      e.preventDefault();
      go(1);
    } else if (k === "ArrowLeft" || k === "PageUp" || k === "Backspace") {
      e.preventDefault();
      go(-1);
    } else if (k === "Home") show(0);
    else if (k === "End") show(slides.length - 1);
    else if (k === "f" || k === "F") fs();
  });
  document.querySelector(".ctl").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    e.stopPropagation();
    if (b.hasAttribute("data-fs")) fs();
    else go(+b.dataset.go);
  });
  addEventListener("click", function (e) {
    if (e.button !== 0 || e.target.closest("a,button,.ctl")) return;
    if (String(getSelection())) return;
    go(e.clientX < innerWidth / 3 ? -1 : 1);
  });
  var tx = null;
  addEventListener(
    "touchstart",
    function (e) {
      tx = e.touches[0].clientX;
    },
    { passive: true },
  );
  addEventListener("touchend", function (e) {
    if (tx === null) return;
    var dx = e.changedTouches[0].clientX - tx;
    tx = null;
    if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
  });
  addEventListener("hashchange", function () {
    show((parseInt(location.hash.slice(1), 10) || 1) - 1);
  });
  show((parseInt(location.hash.slice(1), 10) || 1) - 1);
  idle = setTimeout(function () {
    body.classList.add("idle");
  }, 3500);
})();
