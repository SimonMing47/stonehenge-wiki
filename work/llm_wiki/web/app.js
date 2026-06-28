const state = {
  health: null,
  index: { files: [], comments: [], store: {} },
  audit: [],
  governance: null,
  wikiSections: [],
  sourceRisk: null,
  explanation: null
};

const pages = new Set(["ask", "wiki", "studio", "sources", "governance", "audit"]);
const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const token = localStorage.getItem("llmWikiApiToken") || "";
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "X-LLM-WIKI-TOKEN": token } : {}),
    ...(options.headers || {})
  };
  const { headers: _headers, ...rest } = options;
  const response = await fetch(path, {
    headers,
    ...rest
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || response.statusText);
  }
  return data;
}

async function refreshAll() {
  setBusy("refreshBtn", true);
  try {
    const [health, index, audit, governance, wikiSections, sourceRisk] = await Promise.all([
      api("/health"),
      api("/index"),
      api("/audit?limit=25"),
      api("/reports/governance"),
      api("/wiki/sections?limit=14"),
      api("/sources/risk")
    ]);
    state.health = health;
    state.index = index;
    state.audit = audit.events || [];
    state.governance = governance.report || null;
    state.wikiSections = wikiSections.sections || [];
    state.sourceRisk = sourceRisk;
    renderHealth();
    renderIndex();
    renderAudit();
    renderGovernance();
    renderWikiSections(state.wikiSections);
    renderSourceRisk();
    setApiState(true);
  } catch (error) {
    setApiState(false, error.message);
  } finally {
    setBusy("refreshBtn", false);
  }
}

function renderHealth() {
  const health = state.health || {};
  const store = health.store || {};
  el("fileCount").textContent = String(health.files ?? store.files ?? 0);
  el("commentCount").textContent = String(health.comments ?? store.comments ?? 0);
  el("auditCount").textContent = String(store.audit_events ?? 0);
  el("wikiSectionCount").textContent = String(store.wiki_sections ?? 0);
  el("sourceRiskCount").textContent = String(state.sourceRisk?.summary?.risk_count ?? 0);
  el("dbName").textContent = (health.database_path || "wiki.sqlite").split("/").slice(-1)[0];
  const llm = health.llm || {};
  el("llmName").textContent = llm.enabled
    ? `${llm.ready ? "ready" : "offline"} · ${llm.model || llm.provider || "model"}`
    : "disabled";
  el("knowledgeMode").textContent = health.rag?.enabled ? "rag" : health.knowledge_mode || "wiki";
  const auth = health.auth || {};
  el("authName").textContent = auth.enabled ? "token scopes" : "open";
}

function renderIndex() {
  const files = state.index.files || [];
  const comments = state.index.comments || [];
  const presentations = state.index.presentations || [];
  const registry = state.index.source_registry || [];
  const sourceByPath = Object.fromEntries(registry.map((source) => [source.rel_path, source]));
  const activeCount = registry.filter((source) => source.status === "active").length || files.length;
  el("fileScope").textContent = `${activeCount} active · ${registry.length || files.length} total`;
  el("commentScope").textContent = `${comments.length} found`;
  el("fileList").innerHTML = files.length
    ? files.map((file) => fileRow(file, sourceByPath[file.path])).join("")
    : emptySourceRow("No indexed files");
  el("commentList").innerHTML = comments.length
    ? comments.slice(0, 80).map(commentRow).join("")
    : emptyRow("No comments");
  renderPresentations(presentations);
}

function fileRow(file, source) {
  const tags = (file.tags || []).join(", ") || "untagged";
  const size = source ? `${Math.round(Number(source.size || 0) / 1024)} KB` : "untracked";
  const hash = source?.sha256 ? `sha ${String(source.sha256).slice(0, 10)}` : "sha pending";
  const versionCount = Number(source?.version_count || 0);
  const versions = `${versionCount} ${versionCount === 1 ? "version" : "versions"}`;
  const sectionCount = Number(source?.wiki_section_count || 0);
  const sections = `${sectionCount} ${sectionCount === 1 ? "section" : "sections"}`;
  const origin = source?.origin_type || "local";
  const status = source?.status || "active";
  return `
    <div class="source-row">
      <strong>${escapeHtml(file.path)}</strong>
      <div class="meta">
        <span class="${status === "active" ? "ok" : "blocked"}">${escapeHtml(status)}</span>
        <span>${escapeHtml(origin)}</span>
        <span>${escapeHtml(size)}</span>
        <span>${escapeHtml(hash)}</span>
        <span>${escapeHtml(versions)}</span>
        <span>${escapeHtml(sections)}</span>
        <span>${escapeHtml(file.suffix || "file")}</span>
        <span>${escapeHtml(tags)}</span>
        <span>${Number(file.comment_count || 0)} comments</span>
      </div>
    </div>
  `;
}

function commentRow(comment) {
  return `
    <div class="row">
      <strong>${escapeHtml(comment)}</strong>
    </div>
  `;
}

function renderAudit() {
  const events = state.audit || [];
  el("auditList").innerHTML = events.length
    ? events.map(auditRow).join("")
    : emptyRow("No audit events");
}

function renderGovernance() {
  const report = state.governance;
  if (!report) {
    el("governanceSummary").textContent = "report not loaded";
    return;
  }
  const summary = report.summary || {};
  const riskCount = (report.risks || []).length;
  el("governanceSummary").textContent = `${summary.status || "unknown"} · ${riskCount} risks · ${summary.sources || 0} sources · ${report.todo?.total || 0} todos`;
}

function renderSourceRisk() {
  const report = state.sourceRisk || {};
  const summary = report.summary || {};
  const findings = report.findings || [];
  el("sourceRiskCount").textContent = String(summary.risk_count ?? 0);
  el("riskStatus").textContent = `${summary.status || "unknown"} · ${summary.sources_with_risks || 0} sources`;
  el("riskList").innerHTML = findings.length
    ? findings.slice(0, 80).map((finding) => riskRow(finding)).join("")
    : emptyRow("No source risks");
}

function riskRow(finding) {
  const location = finding.line ? `${finding.source_path}:${finding.line}` : finding.source_path;
  const registry = state.index.source_registry || [];
  const source = registry.find((item) => item.rel_path === finding.source_path) || {};
  const status = source.status || "active";
  const nextStatus = status === "quarantined" ? "active" : "quarantined";
  const actionLabel = status === "quarantined" ? "Activate" : "Quarantine";
  return `
    <div class="risk-row severity-${escapeHtml(finding.severity || "low")}">
      <div class="risk-title">
        <strong>${escapeHtml(finding.code || "risk")}</strong>
        <span>${escapeHtml(finding.severity || "")} · ${escapeHtml(status)}</span>
      </div>
      <p>${escapeHtml(finding.message || "")}</p>
      <div class="meta">
        <span>${escapeHtml(location || "")}</span>
        ${finding.evidence ? `<span>${escapeHtml(finding.evidence)}</span>` : ""}
      </div>
      <div class="risk-actions">
        <button type="button" data-source-path="${escapeHtml(finding.source_path)}" data-source-status="${escapeHtml(nextStatus)}">${actionLabel}</button>
      </div>
    </div>
  `;
}

function renderWikiSections(sections) {
  const list = sections || [];
  el("wikiStatus").textContent = `${list.length} sections`;
  el("wikiSectionList").innerHTML = list.length
    ? list.map(wikiSectionRow).join("")
    : emptyRow("No compiled wiki sections");
}

function wikiSectionRow(section) {
  const snippet = section.snippet || section.body || "";
  return `
    <div class="wiki-section-row">
      <div class="wiki-section-title">
        <strong>${escapeHtml(section.heading || section.page_title || "Section")}</strong>
        <span>${escapeHtml(section.kind || "wiki")}</span>
      </div>
      <p>${escapeHtml(snippet.slice(0, 360))}</p>
      <div class="meta">
        <span>${escapeHtml(section.page_path || "")}</span>
        <span>${escapeHtml(section.source_path || "topic")}</span>
        <span>line ${Number(section.line_start || 0)}</span>
        ${section.score ? `<span>score ${Number(section.score)}</span>` : ""}
      </div>
    </div>
  `;
}

function renderPresentations(presentations) {
  if (!presentations.length) {
    el("artifactOutput").innerHTML = '<span class="muted">No deck yet</span>';
    return;
  }
  el("artifactOutput").innerHTML = presentations
    .slice(0, 4)
    .map((item) => `
      <div class="artifact-card">
        <strong>${escapeHtml(item.name || item.deck)}</strong>
        <span>${Math.round(Number(item.size || 0) / 1024)} KB</span>
        <a href="${escapeHtml(item.download_url)}" target="_blank" rel="noreferrer">Download PPTX</a>
      </div>
    `)
    .join("");
}

function auditRow(event) {
  const statusClass = event.blocked ? "blocked" : "ok";
  const title = event.payload?.title || event.subject || event.event_type;
  return `
    <div class="audit-row">
      <strong>${escapeHtml(title)}</strong>
      <div class="meta">
        <span>${escapeHtml(event.created_at || "")}</span>
        <span>${escapeHtml(event.event_type || "")}</span>
        <span class="${statusClass}">${escapeHtml(event.status || "")}</span>
      </div>
    </div>
  `;
}

function emptyRow(text) {
  return `<div class="row"><span class="muted">${escapeHtml(text)}</span></div>`;
}

function emptySourceRow(text) {
  return `<div class="source-row"><span class="muted">${escapeHtml(text)}</span></div>`;
}

async function askQuestion() {
  const title = el("questionInput").value.trim();
  if (!title) return;
  setBusy("askBtn", true);
  el("queryStatus").textContent = "Running";
  try {
    const answer = await api("/ask", {
      method: "POST",
      body: JSON.stringify({
        id: el("questionId").value.trim() || "console-1",
        title,
        level: el("questionLevel").value
      })
    });
    renderAnswer(answer);
    el("queryStatus").textContent = answer.answer?.error_msg ? "Blocked" : "Complete";
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("queryStatus").textContent = "Failed";
  } finally {
    setBusy("askBtn", false);
  }
}

async function explainQuestion() {
  const title = el("questionInput").value.trim();
  if (!title) return;
  setBusy("explainBtn", true);
  el("explainStatus").textContent = "Tracing";
  try {
    const explanation = await api("/explain", {
      method: "POST",
      body: JSON.stringify({
        id: el("questionId").value.trim() || "console-1",
        title,
        level: el("questionLevel").value
      })
    });
    state.explanation = explanation;
    renderExplanation(explanation);
    renderWikiSections(explanation.wiki?.sections || []);
    el("explainStatus").textContent = explanation.status || "Complete";
    setPage("wiki");
  } catch (error) {
    el("explainOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("explainStatus").textContent = "Failed";
  } finally {
    setBusy("explainBtn", false);
  }
}

function renderExplanation(explanation) {
  const safety = explanation.safety || {};
  const records = explanation.records || [];
  const evidence = explanation.evidence || [];
  const wiki = explanation.wiki || {};
  const safetyClass = safety.blocked ? "blocked" : "ok";
  el("explainOutput").innerHTML = `
    <div class="trace-summary">
      <div>
        <span>Route</span>
        <strong>${escapeHtml(explanation.route || "knowledge")}</strong>
      </div>
      <div>
        <span>Safety</span>
        <strong class="${safetyClass}">${escapeHtml(safety.blocked ? "blocked" : "ok")}</strong>
      </div>
      <div>
        <span>Wiki Mode</span>
        <strong>${escapeHtml(wiki.mode || "compiled_wiki")}</strong>
      </div>
      <div>
        <span>Sections</span>
        <strong>${Number(wiki.section_count || 0)}</strong>
      </div>
    </div>
    ${safety.reason ? `<div class="answer-status blocked">${escapeHtml(safety.reason)}</div>` : ""}
    <h3>Evidence</h3>
    <div class="trace-list">
      ${(evidence.length ? evidence : records.slice(0, 6)).map(traceRow).join("") || emptyRow("No evidence")}
    </div>
  `;
}

function traceRow(item) {
  const path = item.source_path || item.path || "";
  const text = item.text || item.heading || item.name || JSON.stringify(item);
  return `
    <div class="trace-row">
      <strong>${escapeHtml(path)}</strong>
      <p>${escapeHtml(text)}</p>
      <div class="meta">
        ${item.line ? `<span>line ${Number(item.line)}</span>` : ""}
        ${item.score ? `<span>score ${Number(item.score)}</span>` : ""}
      </div>
    </div>
  `;
}

function renderAnswer(answer) {
  const payload = answer.answer || {};
  if (payload.error_msg) {
    el("answerOutput").innerHTML = `<div class="answer-status blocked">${escapeHtml(payload.error_msg)}</div>`;
    return;
  }
  const datas = payload.datas || [];
  const body = datas
    .map((item) => `<p>${escapeHtml(item)}</p>`)
    .join("");
  el("answerOutput").innerHTML = `
    <div class="answer-status ok">${escapeHtml(answer.id || "answer")}</div>
    ${body || '<p class="muted">No answer</p>'}
  `;
}

async function runGroup() {
  const group = el("groupInput").value.trim();
  if (!group) return;
  setBusy("runGroupBtn", true);
  try {
    const result = await api("/groups/run", {
      method: "POST",
      body: JSON.stringify({ groups: [group] })
    });
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
  } finally {
    setBusy("runGroupBtn", false);
  }
}

async function reindex() {
  setBusy("reindexBtn", true);
  try {
    const result = await api("/reindex", { method: "POST", body: "{}" });
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
  } finally {
    setBusy("reindexBtn", false);
  }
}

async function importSource() {
  const source = el("importSource").value.trim();
  if (!source) return;
  setBusy("importBtn", true);
  el("importStatus").textContent = "Importing";
  try {
    const result = await api("/sources/import", {
      method: "POST",
      body: JSON.stringify({
        source,
        title: el("importTitle").value.trim(),
        category: el("importCategory").value.trim() || "00_inbox"
      })
    });
    if (result.error_msg) {
      el("importStatus").textContent = `Blocked · ${result.reason || result.error_msg}`;
      return;
    }
    el("importStatus").textContent = `Imported · ${result.path}`;
    await refreshAll();
  } catch (error) {
    el("importStatus").textContent = `Failed · ${error.message}`;
  } finally {
    setBusy("importBtn", false);
  }
}

async function setSourceStatus(path, status, button) {
  if (!path || !status) return;
  if (button) button.disabled = true;
  el("riskStatus").textContent = "Updating";
  try {
    const result = await api("/sources/status", {
      method: "POST",
      body: JSON.stringify({
        path,
        status,
        reason: "console review action",
        actor: "console"
      })
    });
    if (result.error) {
      el("riskStatus").textContent = `failed · ${result.error}`;
      return;
    }
    await refreshAll();
  } catch (error) {
    el("riskStatus").textContent = `failed · ${error.message}`;
  } finally {
    if (button) button.disabled = false;
  }
}

async function compileWiki() {
  setBusy("compileWikiBtn", true);
  try {
    const result = await api("/wiki/compile", { method: "POST", body: "{}" });
    writeWikiOutput(result);
    await refreshAll();
  } catch (error) {
    writeWikiOutput({ error: error.message });
  } finally {
    setBusy("compileWikiBtn", false);
  }
}

async function lintWiki() {
  setBusy("lintWikiBtn", true);
  try {
    const result = await api("/wiki/lint");
    writeWikiOutput(result);
    await refreshAll();
  } catch (error) {
    writeWikiOutput({ error: error.message });
  } finally {
    setBusy("lintWikiBtn", false);
  }
}

async function searchWikiSections() {
  const query = el("wikiSearchInput").value.trim() || el("questionInput").value.trim();
  const path = query ? `/wiki/search?q=${encodeURIComponent(query)}&limit=14` : "/wiki/sections?limit=14";
  setBusy("wikiSearchBtn", true);
  el("wikiStatus").textContent = "Searching";
  try {
    const result = await api(path);
    state.wikiSections = result.sections || [];
    renderWikiSections(state.wikiSections);
  } catch (error) {
    el("wikiSectionList").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("wikiStatus").textContent = "Failed";
  } finally {
    setBusy("wikiSearchBtn", false);
  }
}

async function refreshReport() {
  setBusy("refreshReportBtn", true);
  try {
    const result = await api("/reports/governance");
    state.governance = result.report || null;
    renderGovernance();
  } catch (error) {
    el("governanceSummary").textContent = `failed · ${error.message}`;
  } finally {
    setBusy("refreshReportBtn", false);
  }
}

async function exportReport() {
  setBusy("exportReportBtn", true);
  try {
    const result = await api("/reports/governance/export", { method: "POST", body: "{}" });
    state.governance = result.report || null;
    renderGovernance();
    el("governanceSummary").innerHTML = `${escapeHtml(result.report?.summary?.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">Download report</a>`;
  } catch (error) {
    el("governanceSummary").textContent = `failed · ${error.message}`;
  } finally {
    setBusy("exportReportBtn", false);
  }
}

function selectedGroupsBody() {
  const group = el("groupInput").value.trim();
  return group ? JSON.stringify({ groups: [group] }) : "{}";
}

async function runEvaluation() {
  setBusy("runEvaluationBtn", true);
  try {
    const result = await api("/reports/evaluation", { method: "POST", body: selectedGroupsBody() });
    const summary = result.report?.summary || {};
    el("governanceSummary").textContent = `evaluation ${summary.status || "unknown"} · ${summary.total_questions || 0} questions · score ${summary.score ?? 0}`;
    await refreshAll();
  } catch (error) {
    el("governanceSummary").textContent = `evaluation failed · ${error.message}`;
  } finally {
    setBusy("runEvaluationBtn", false);
  }
}

async function exportEvaluation() {
  setBusy("exportEvaluationBtn", true);
  try {
    const result = await api("/reports/evaluation/export", { method: "POST", body: selectedGroupsBody() });
    const summary = result.report?.summary || {};
    el("governanceSummary").innerHTML = `evaluation ${escapeHtml(summary.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">Download evaluation</a>`;
  } catch (error) {
    el("governanceSummary").textContent = `evaluation failed · ${error.message}`;
  } finally {
    setBusy("exportEvaluationBtn", false);
  }
}

async function generateSlides() {
  const topic = el("slidesTopic").value.trim() || el("questionInput").value.trim();
  if (!topic) return;
  setBusy("generateSlidesBtn", true);
  el("slidesStatus").textContent = "Generating";
  try {
    const result = await api("/slides/generate", {
      method: "POST",
      body: JSON.stringify({
        topic,
        slide_count: Number(el("slideCount").value || 6)
      })
    });
    if (result.error_msg) {
      el("artifactOutput").innerHTML = `<div class="answer-status blocked">${escapeHtml(result.error_msg)}</div>`;
      el("slidesStatus").textContent = "Blocked";
      return;
    }
    el("artifactOutput").innerHTML = `
      <div class="artifact-card">
        <strong>${escapeHtml(result.topic || "Presentation")}</strong>
        <span>${Number(result.slide_count || 0)} slides</span>
        <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">Download PPTX</a>
      </div>
    `;
    el("slidesStatus").textContent = "Complete";
    await refreshAll();
  } catch (error) {
    el("artifactOutput").innerHTML = `<div class="answer-status blocked">${escapeHtml(error.message)}</div>`;
    el("slidesStatus").textContent = "Failed";
  } finally {
    setBusy("generateSlidesBtn", false);
  }
}

function setApiState(online, detail = "") {
  const node = el("apiState");
  node.classList.toggle("online", online);
  node.textContent = online ? "Online" : detail || "Offline";
}

function currentPage() {
  const id = window.location.hash.replace("#", "") || "ask";
  return pages.has(id) ? id : "ask";
}

function setPage(page) {
  const target = pages.has(page) ? page : "ask";
  if (window.location.hash !== `#${target}`) {
    window.location.hash = target;
  } else {
    renderPage();
  }
}

function renderPage() {
  const active = currentPage();
  document.querySelectorAll("[data-page]").forEach((node) => {
    node.classList.toggle("active", node.dataset.page === active);
  });
  document.querySelectorAll(".nav a").forEach((link) => {
    const page = link.getAttribute("href")?.replace("#", "") || "";
    link.classList.toggle("active", page === active);
  });
}

function setBusy(id, busy) {
  const node = el(id);
  node.disabled = busy;
}

function writeWikiOutput(result) {
  el("wikiOperationOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

el("refreshBtn").addEventListener("click", refreshAll);
el("askBtn").addEventListener("click", askQuestion);
el("explainBtn").addEventListener("click", explainQuestion);
el("importBtn").addEventListener("click", importSource);
el("generateSlidesBtn").addEventListener("click", generateSlides);
el("runGroupBtn").addEventListener("click", runGroup);
el("reindexBtn").addEventListener("click", reindex);
el("compileWikiBtn").addEventListener("click", compileWiki);
el("lintWikiBtn").addEventListener("click", lintWiki);
el("wikiSearchBtn").addEventListener("click", searchWikiSections);
el("refreshReportBtn").addEventListener("click", refreshReport);
el("exportReportBtn").addEventListener("click", exportReport);
el("runEvaluationBtn").addEventListener("click", runEvaluation);
el("exportEvaluationBtn").addEventListener("click", exportEvaluation);
el("tokenForm").addEventListener("submit", (event) => event.preventDefault());
window.addEventListener("hashchange", renderPage);
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-source-status]");
  if (!button) return;
  setSourceStatus(button.dataset.sourcePath, button.dataset.sourceStatus, button);
});
el("saveTokenBtn").addEventListener("click", () => {
  localStorage.setItem("llmWikiApiToken", el("tokenInput").value.trim());
  refreshAll();
});
el("questionInput").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    askQuestion();
  }
});

el("tokenInput").value = localStorage.getItem("llmWikiApiToken") || "";
renderPage();
refreshAll();
