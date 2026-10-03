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

  let currentMode = "beginner";
  let presetsData = [];

  // Update char count
  claimText.addEventListener("input", () => {
    claimCharCount.textContent = `${claimText.value.length} chars`;
    updateCliPreview();
  });

  referenceText.addEventListener("input", updateCliPreview);
  caseId.addEventListener("input", updateCliPreview);
  claimLang.addEventListener("change", updateCliPreview);
  voteTitle.addEventListener("input", updateCliPreview);

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

  bookletSelect.addEventListener("change", updateCliPreview);

  // CLI Command Preview
  function updateCliPreview() {
    const cid = caseId.value.trim() || "demo-01";
    const claim = claimText.value.trim() || "[CLAIM]";
    const lang = claimLang.value !== "auto" ? ` --claim-lang ${claimLang.value}` : "";

    if (currentMode === "beginner") {
      const refSnippet = referenceText.value.trim()
        ? `"${referenceText.value.trim().substring(0, 32)}..."`
        : `"[REFERENCE_TEXT]"`;
      cliCommandText.textContent = `booklint predict --id "${cid}" --claim "${claim.substring(0, 36)}..." --reference ${refSnippet}${lang}`;
    } else {
      const bookletVal = `${bookletSelect.value}_de.pdf`;
      const voteVal = voteTitle.value.trim() ? ` --vote "${voteTitle.value.trim()}"` : "";
      cliCommandText.textContent = `booklint predict --id "${cid}" --claim "${claim.substring(0, 36)}..." --booklet "${bookletVal}"${voteVal}${lang}`;
    }
  }

  // Load Presets
  async function loadPresets() {
    try {
      const res = await fetch("/api/presets");
      if (res.ok) {
        const data = await res.json();
        presetsData = data.presets || [];
        populatePresetsDropdown(presetsData);
      }
    } catch (err) {
      console.warn("Could not load presets from server proxy:", err);
      // Fallback local presets if server endpoint not reachable
      const fallbackPresets = [
        {
          id: "edge-rm-01",
          claim: "La nova lescha davart l'identitad electronica (E-ID) è facultativa per ils burgais.",
          claim_language: "rm",
          reference_string: "Die elektronische Identität E-ID ist freiwillig und für alle Bürgerinnen und Bürger kostenlos.",
          challenge_type: "romansh_crosslingual",
          label: 0,
        },
        {
          id: "edge-rm-02",
          claim: "Il Cussegl federal recumonda d'acceptar l'iniziativa dal pievel «Per ina Svizra da 10 milliuns!».",
          claim_language: "rm",
          reference_string: "Bundesrat und Parlament empfehlen Volk und Ständen, die Volksinitiative abzulehnen.",
          challenge_type: "romansh_crosslingual",
          label: 2,
        },
        {
          id: "edge-modal-01",
          claim: "Die Kantone sind gesetzlich verpflichtet, auf sämtlichen Zweitwohnungen eine Sondersteuer einzuführen.",
          claim_language: "de",
          reference_string: "Die Verfassungsänderung ermächtigt die Kantone, eine Liegenschaftssteuer auf Zweitliegenschaften zu erheben. Die Einführung bleibt im Ermessen der einzelnen Kantone.",
          challenge_type: "modal_negation",
          label: 2,
        },
        {
          id: "edge-attrib-01",
          claim: "Der Bundesrat warnt in seinen Erläuterungen, dass die Infrastruktur und die Sozialwerke ohne Zuwanderungsstopp kollabieren.",
          claim_language: "de",
          reference_string: "Argumente des Initiativkomitees: Die ungebremste Zuwanderung führt dazu, dass unsere Infrastruktur und Sozialwerke unweigerlich kollabieren.",
          challenge_type: "attribution_trap",
          label: 2,
        },
      ];
      populatePresetsDropdown(fallbackPresets);
    }
  }

  function populatePresetsDropdown(presets) {
    presetSelect.innerHTML = '<option value="">-- Choose an edge case or type your own below --</option>';
    presets.forEach((p, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      const typeBadge = `[synthetic${p.challenge_type ? ", " + p.challenge_type : ""}] `;
      const langBadge = p.claim_language ? `(${p.claim_language}) ` : "";
      opt.textContent = `${typeBadge}${langBadge}${p.claim.substring(0, 68)}...`;
      presetSelect.appendChild(opt);
    });
  }

  presetSelect.addEventListener("change", () => {
    const idx = presetSelect.value;
    if (idx === "" || !presetsData[idx]) return;

    const p = presetsData[idx];
    claimText.value = p.claim || "";
    claimCharCount.textContent = `${claimText.value.length} chars`;
    caseId.value = p.id || `preset-${idx}`;

    if (p.claim_language) {
      claimLang.value = p.claim_language;
    } else {
      claimLang.value = "auto";
    }

    if (p.reference_string) {
      setMode("beginner");
      referenceText.value = p.reference_string;
    } else if (p.booklet_url || p.vote) {
      setMode("advanced");
      if (p.vote) voteTitle.value = p.vote;
    }

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
      vote: currentMode === "advanced" ? voteTitle.value.trim() : "",
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
      displayResult(data, clientLatency);
    } catch (err) {
      console.error(err);
      jsonOutput.innerHTML = `<code style="color: #ff7b72;">// Network error: ${escapeHtml(err.message)}</code>`;
    } finally {
      btnSubmit.disabled = false;
      spinner.classList.add("hidden");
    }
  });

  // Display Result conforming to Slide 25
  function displayResult(data, clientLatency) {
    // Validate Slide 25 Root Keys
    const keys = Object.keys(data);
    const requiredKeys = ["id", "label", "label_name", "evidence", "metrics"];
    const hasAllKeys = requiredKeys.every((k) => keys.includes(k));

    if (hasAllKeys) {
      specStatus.innerHTML = `<span style="color: #4ade80;">✓ OST output format</span> (id, label, label_name, evidence, metrics)`;
    } else {
      specStatus.innerHTML = `<span style="color: #ff7b72;">⚠ Schema Warning</span>`;
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
