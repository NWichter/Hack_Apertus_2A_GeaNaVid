/**
 * GeaNaVid Demo Application Logic
 * Output in the OST format (slide 25 of the OST track session).
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const btnModeBeginner = document.getElementById("btnModeBeginner");
  const btnModeAdvanced = document.getElementById("btnModeAdvanced");
  const beginnerFields = document.getElementById("beginnerFields");
  const advancedFields = document.getElementById("advancedFields");

  const checkForm = document.getElementById("checkForm");
  const presetSelect = document.getElementById("presetSelect");
  const claimText = document.getElementById("claimText");
  const claimCharCount = document.getElementById("claimCharCount");
  const claimLang = document.getElementById("claimLang");
  const caseId = document.getElementById("caseId");
  const referenceText = document.getElementById("referenceText");
  const bookletSelect = document.getElementById("bookletSelect");
  const bookletLang = document.getElementById("bookletLang");
  const voteOptions = document.getElementById("voteOptions");
  const presetNote = document.getElementById("presetNote");
  const voteTitle = document.getElementById("voteTitle");

  const btnSubmit = document.getElementById("btnSubmit");
  const btnReset = document.getElementById("btnReset");
  const spinner = document.getElementById("spinner");
  const btnCopyJson = document.getElementById("btnCopyJson");

  const cliCommandText = document.getElementById("cliCommandText");
  const jsonOutput = document.getElementById("jsonOutput");
  const verdictRibbon = document.getElementById("verdictRibbon");
  const verdictTitle = document.getElementById("verdictTitle");
  const metricTokens = document.getElementById("metricTokens");
  const metricLatency = document.getElementById("metricLatency");
  const specStatus = document.getElementById("specStatus");
  const modelBadge = document.getElementById("modelBadge");
  const modelGroup = document.getElementById("modelGroup");
  const modelSelect = document.getElementById("modelSelect");
  const metricModel = document.getElementById("metricModel");

  const LABELS = ["entailment", "neutral", "contradiction"];
  let currentMode = "beginner";
  let presetsData = [];
  let bookletSources = {};
  let goldLabel = null;

  // Update char count
  claimText.addEventListener("input", () => {
    claimCharCount.textContent = `${claimText.value.length} chars`;
    updateCliPreview();
  });

  referenceText.addEventListener("input", updateCliPreview);
  caseId.addEventListener("input", updateCliPreview);
  claimLang.addEventListener("change", updateCliPreview);
  voteTitle.addEventListener("input", updateCliPreview);
  modelSelect.addEventListener("change", updateCliPreview);

  // Mode Switcher
  function setMode(mode) {
    currentMode = mode;
    if (mode === "beginner") {
      btnModeBeginner.classList.add("active");
      btnModeAdvanced.classList.remove("active");
      beginnerFields.classList.remove("hidden");
      advancedFields.classList.add("hidden");
    } else {
      btnModeAdvanced.classList.add("active");
      btnModeBeginner.classList.remove("active");
      advancedFields.classList.remove("hidden");
      beginnerFields.classList.add("hidden");
    }
    updateCliPreview();
  }

  btnModeBeginner.addEventListener("click", () => setMode("beginner"));
  btnModeAdvanced.addEventListener("click", () => setMode("advanced"));

  function bookletChanged() {
    const src = bookletSources[`${bookletSelect.value}_${bookletLang.value}`];
    voteOptions.innerHTML = "";
    (src ? src.votes : []).forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      voteOptions.appendChild(opt);
    });
    updateCliPreview();
  }

  bookletSelect.addEventListener("change", bookletChanged);
  bookletLang.addEventListener("change", bookletChanged);

  function clearGold() {
    goldLabel = null;
    presetNote.textContent = "";
  }

  claimText.addEventListener("input", clearGold);
  referenceText.addEventListener("input", clearGold);
  bookletSelect.addEventListener("change", clearGold);
  bookletLang.addEventListener("change", clearGold);
  voteTitle.addEventListener("input", clearGold);

  function shellQuote(text) {
    return "'" + String(text).replace(/'/g, "'\\''") + "'";
  }

  // The CLI call that runs the same pipeline with the same model as this page.
  function updateCliPreview() {
    const parts = [];
    if (modelSelect.value) parts.push(`LLM_NAME=${modelSelect.value}`);
    parts.push("booklint", "predict", "--id", shellQuote(caseId.value.trim() || "demo-01"));
    parts.push("--claim", shellQuote(claimText.value.trim() || "<claim>"));
    if (currentMode === "beginner") {
      parts.push("--reference", shellQuote(referenceText.value.trim() || "<reference text>"));
    } else {
      const src = bookletSources[`${bookletSelect.value}_${bookletLang.value}`];
      parts.push("--booklet", src ? src.url : `<${bookletSelect.value}_${bookletLang.value}.pdf>`);
      if (voteTitle.value.trim()) parts.push("--vote", shellQuote(voteTitle.value.trim()));
    }
    if (claimLang.value !== "auto") parts.push("--claim-lang", claimLang.value);
    cliCommandText.textContent = parts.join(" ");
  }

  // Load Presets
  async function loadPresets() {
    try {
      const res = await fetch("/api/presets");
      if (!res.ok) return;
      const data = await res.json();
      const ost = (data.ost || []).map((p) => Object.assign({ kind: "ost" }, p));
      const syn = (data.presets || []).map((p) => Object.assign({ kind: "synthetic" }, p));
      presetsData = ost.concat(syn);
      populatePresetsDropdown(ost, syn);
    } catch (err) {
      console.warn("Could not load the examples:", err);
    }
  }

  function addGroup(label, items, offset) {
    if (!items.length) return;
    const group = document.createElement("optgroup");
    group.label = label;
    items.forEach((p, idx) => {
      const opt = document.createElement("option");
      opt.value = offset + idx;
      const lang = p.kind === "ost" ? `${p.claim_language} → ${p.booklet_lang}` : p.claim_language || "";
      const cut = p.claim.length > 68 ? `${p.claim.substring(0, 68)}…` : p.claim;
      opt.textContent = `(${lang}) ${cut}`;
      group.appendChild(opt);
    });
    presetSelect.appendChild(group);
  }

  function populatePresetsDropdown(ost, syn) {
    presetSelect.innerHTML = '<option value="">-- Choose an example or type your own below --</option>';
    addGroup("OST v1.1 benchmark (real cases, development split), Advanced task", ost, 0);
    addGroup("Synthetic edge cases (LLM-written, not reviewed, never evaluated), Beginner task", syn, ost.length);
  }

  presetSelect.addEventListener("change", () => {
    const idx = presetSelect.value;
    if (idx === "" || !presetsData[idx]) return;

    const p = presetsData[idx];
    claimText.value = p.claim || "";
    claimCharCount.textContent = `${claimText.value.length} chars`;
    caseId.value = p.id || `preset-${idx}`;

    if (p.kind === "ost") {
      claimLang.value = "auto";
      setMode("advanced");
      bookletSelect.value = p.booklet;
      bookletLang.value = p.booklet_lang;
      bookletChanged();
      voteTitle.value = p.vote || "";
      referenceText.value = "";
    } else {
      claimLang.value = p.claim_language || "auto";
      setMode("beginner");
      referenceText.value = p.reference_string || "";
      voteTitle.value = "";
    }
    goldLabel = typeof p.label === "number" ? p.label : null;
    presetNote.textContent =
      p.kind === "ost"
        ? `OST v1.1 ${p.id}, gold label: ${LABELS[p.label]}. The claim language is detected, as in OST's input.`
        : `Synthetic ${p.challenge_type || "edge case"}, unreviewed label: ${LABELS[p.label]}. Demo only.`;

    updateCliPreview();
  });

  // Fetch Server Info
  async function loadInfo() {
    try {
      const res = await fetch("/api/info");
      if (res.ok) {
        const data = await res.json();
        if (data.model) {
          modelBadge.textContent = `Model: ${data.model}`;
        }
        const models = data.models && data.models.length ? data.models : data.model ? [data.model] : [];
        modelSelect.innerHTML = "";
        models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = /70b/i.test(m) ? `${m} (70B, submitted default)` : /8b/i.test(m) ? `${m} (8B)` : m;
          modelSelect.appendChild(opt);
        });
        const big = models.find((m) => /70b/i.test(m));
        if (big) modelSelect.value = big;
        modelGroup.classList.toggle("hidden", models.length < 2);
        bookletSources = data.booklet_sources || {};
        if (data.booklets && data.booklets.length) {
          const keep = bookletSelect.value;
          bookletSelect.innerHTML = "";
          data.booklets
            .slice()
            .reverse()
            .forEach((d) => {
              const opt = document.createElement("option");
              opt.value = d;
              opt.textContent = d;
              bookletSelect.appendChild(opt);
            });
          if (data.booklets.includes(keep)) bookletSelect.value = keep;
        }
        bookletChanged();
      }
    } catch (e) {
      // Ignore
    }
  }

  // Handle Form Submission
  checkForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const claim = claimText.value.trim();
    if (!claim) return;

    btnSubmit.disabled = true;
    spinner.classList.remove("hidden");
    jsonOutput.innerHTML = `<code>// Running booklint pipeline via Apertus...\n// Please wait...</code>`;
    verdictRibbon.classList.add("hidden");

    const payload = {
      id: caseId.value.trim() || `demo-${Date.now()}`,
      claim: claim,
      mode: currentMode,
      claim_lang: claimLang.value !== "auto" ? claimLang.value : null,
      reference: currentMode === "beginner" ? referenceText.value.trim() : "",
      booklet: currentMode === "advanced" ? bookletSelect.value : "",
      booklet_lang: currentMode === "advanced" ? bookletLang.value : "",
      vote: currentMode === "advanced" ? voteTitle.value.trim() : "",
      model: modelSelect.value || null,
    };

    const t0 = performance.now();

    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const clientLatency = Math.round(performance.now() - t0);

      if (res.status === 429) {
        const errData = await res.json();
        jsonOutput.innerHTML = `<code style="color: #ff7b72;">// HTTP 429 Rate Limit Exceeded\n${JSON.stringify(errData, null, 2)}</code>`;
        specStatus.textContent = "Rate limited. Please wait a moment.";
        return;
      }

      if (res.status === 401) {
        jsonOutput.innerHTML = `<code style="color: #ff7b72;">// HTTP 401 Unauthorized\n// Reload the page and sign in.</code>`;
        specStatus.textContent = "Unauthorized access.";
        return;
      }

      const isJson = (res.headers.get("Content-Type") || "").includes("application/json");
      const data = isJson ? await res.json() : null;
      if (!res.ok || !data) {
        const msg = data && data.error ? data.error : "The demo API is not reachable from this page.";
        jsonOutput.innerHTML = `<code style="color: #ff7b72;">// HTTP ${res.status}\n// ${escapeHtml(msg)}</code>`;
        specStatus.textContent = "Request failed.";
        return;
      }
      displayResult(data, clientLatency, res.headers.get("X-Model") || modelSelect.value || "");
    } catch (err) {
      console.error(err);
      jsonOutput.innerHTML = `<code style="color: #ff7b72;">// Network error: ${escapeHtml(err.message)}</code>`;
    } finally {
      btnSubmit.disabled = false;
      spinner.classList.add("hidden");
    }
  });

  // Display Result conforming to Slide 25
  function displayResult(data, clientLatency, usedModel) {
    // Validate Slide 25 Root Keys
    const keys = Object.keys(data);
    const requiredKeys = ["id", "label", "label_name", "evidence", "metrics"];
    const hasAllKeys = requiredKeys.every((k) => keys.includes(k));

    if (hasAllKeys) {
      specStatus.innerHTML = `<span style="color: #4ade80;">✓ OST output format</span> (id, label, label_name, evidence, metrics)`;
    } else {
      specStatus.innerHTML = `<span style="color: #ff7b72;">⚠ Schema Warning</span>`;
    }
    if (goldLabel !== null) {
      const ok = data.label === goldLabel;
      specStatus.innerHTML += ` · gold: ${LABELS[goldLabel]} <span style="color: ${ok ? "#4ade80" : "#ff7b72"};">${ok ? "✓" : "✗"}</span>`;
    }

    // Verdict styling
    verdictRibbon.className = "verdict-ribbon";
    const lbl = data.label;
    const lblName = (data.label_name || "").toLowerCase();

    if (lbl === 0 || lblName === "entailment") {
      verdictRibbon.classList.add("verdict-entailment");
      verdictTitle.textContent = "Gea · Entailment (0)";
    } else if (lbl === 1 || lblName === "neutral") {
      verdictRibbon.classList.add("verdict-neutral");
      verdictTitle.textContent = "Vid · Neutral (1)";
    } else if (lbl === 2 || lblName === "contradiction") {
      verdictRibbon.classList.add("verdict-contradiction");
      verdictTitle.textContent = "Na · Contradiction (2)";
    }

    const m = data.metrics || {};
    const totalTokens = (m.input_tokens || 0) + (m.output_tokens || 0);
    metricTokens.textContent = `${totalTokens} (${m.input_tokens || 0} in / ${m.output_tokens || 0} out)`;
    metricLatency.textContent = `${m.inference_time_ms || clientLatency} ms`;
    metricModel.textContent = usedModel || "-";
    if (usedModel) modelBadge.textContent = `Model: ${usedModel}`;

    verdictRibbon.classList.remove("hidden");

    // Syntax-highlighted JSON rendering
    const formatted = JSON.stringify(data, null, 2);
    jsonOutput.innerHTML = `<code>${syntaxHighlight(formatted)}</code>`;
  }

  function escapeHtml(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function syntaxHighlight(json) {
    json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return json.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = "color: #79c0ff;"; // number
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = "color: #7ee787;"; // key
          } else {
            cls = "color: #a5d6ff;"; // string
          }
        } else if (/true|false/.test(match)) {
          cls = "color: #ff7b72;"; // boolean
        } else if (/null/.test(match)) {
          cls = "color: #8b949e;"; // null
        }
        return `<span style="${cls}">${match}</span>`;
      }
    );
  }

  // Copy JSON
  btnCopyJson.addEventListener("click", () => {
    const raw = jsonOutput.textContent;
    navigator.clipboard.writeText(raw).then(() => {
      const orig = btnCopyJson.textContent;
      btnCopyJson.textContent = "Copied!";
      setTimeout(() => (btnCopyJson.textContent = orig), 1800);
    });
  });

  // Reset form
  btnReset.addEventListener("click", () => {
    checkForm.reset();
    claimCharCount.textContent = "0 chars";
    presetSelect.value = "";
    clearGold();
    updateCliPreview();
    verdictRibbon.classList.add("hidden");
    jsonOutput.innerHTML = `<code>{\n  "status": "ready"\n}</code>`;
    specStatus.textContent = "Strict root keys {\"id\", \"label\", \"label_name\", \"evidence\", \"metrics\"} guaranteed.";
  });

  // Keyboard shortcut: Ctrl + Enter
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      checkForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    }
  });

  // Init
  loadPresets();
  loadInfo();
  updateCliPreview();
});
