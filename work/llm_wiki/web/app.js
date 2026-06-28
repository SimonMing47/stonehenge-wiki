const state = {
  health: null,
  index: { files: [], comments: [], store: {} },
  audit: []
};

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
    const [health, index, audit] = await Promise.all([
      api("/health"),
      api("/index"),
      api("/audit?limit=25")
    ]);
    state.health = health;
    state.index = index;
    state.audit = audit.events || [];
    renderHealth();
    renderIndex();
    renderAudit();
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
  el("dbName").textContent = (health.database_path || "wiki.sqlite").split("/").slice(-1)[0];
  const llm = health.llm || {};
  el("llmName").textContent = llm.enabled
    ? `${llm.ready ? "ready" : "offline"} · ${llm.model || llm.provider || "model"}`
    : "disabled";
  const auth = health.auth || {};
  el("authName").textContent = auth.enabled ? "token scopes" : "open";
}

function renderIndex() {
  const files = state.index.files || [];
  const comments = state.index.comments || [];
  const presentations = state.index.presentations || [];
  const registry = state.index.source_registry || [];
  const sourceByPath = Object.fromEntries(registry.map((source) => [source.rel_path, source]));
  el("fileScope").textContent = `${registry.length || files.length} active`;
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

async function compileWiki() {
  setBusy("compileWikiBtn", true);
  try {
    const result = await api("/wiki/compile", { method: "POST", body: "{}" });
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
  } finally {
    setBusy("compileWikiBtn", false);
  }
}

async function lintWiki() {
  setBusy("lintWikiBtn", true);
  try {
    const result = await api("/wiki/lint");
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
  } finally {
    setBusy("lintWikiBtn", false);
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

function setBusy(id, busy) {
  const node = el(id);
  node.disabled = busy;
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
el("importBtn").addEventListener("click", importSource);
el("generateSlidesBtn").addEventListener("click", generateSlides);
el("runGroupBtn").addEventListener("click", runGroup);
el("reindexBtn").addEventListener("click", reindex);
el("compileWikiBtn").addEventListener("click", compileWiki);
el("lintWikiBtn").addEventListener("click", lintWiki);
el("tokenForm").addEventListener("submit", (event) => event.preventDefault());
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
refreshAll();
