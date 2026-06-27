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
}

function renderIndex() {
  const files = state.index.files || [];
  const comments = state.index.comments || [];
  el("fileScope").textContent = `${files.length} indexed`;
  el("commentScope").textContent = `${comments.length} found`;
  el("fileList").innerHTML = files.length
    ? files.map(fileRow).join("")
    : emptyRow("No indexed files");
  el("commentList").innerHTML = comments.length
    ? comments.slice(0, 80).map(commentRow).join("")
    : emptyRow("No comments");
}

function fileRow(file) {
  const tags = (file.tags || []).join(", ") || "untagged";
  return `
    <div class="row">
      <strong>${escapeHtml(file.path)}</strong>
      <div class="meta">
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
    el("answerOutput").textContent = JSON.stringify(answer, null, 2);
    el("queryStatus").textContent = answer.answer?.error_msg ? "Blocked" : "Complete";
    await refreshAll();
  } catch (error) {
    el("answerOutput").textContent = JSON.stringify({ error: error.message }, null, 2);
    el("queryStatus").textContent = "Failed";
  } finally {
    setBusy("askBtn", false);
  }
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
    el("answerOutput").textContent = JSON.stringify(result, null, 2);
    await refreshAll();
  } catch (error) {
    el("answerOutput").textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    setBusy("runGroupBtn", false);
  }
}

async function reindex() {
  setBusy("reindexBtn", true);
  try {
    const result = await api("/reindex", { method: "POST", body: "{}" });
    el("answerOutput").textContent = JSON.stringify(result, null, 2);
    await refreshAll();
  } catch (error) {
    el("answerOutput").textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    setBusy("reindexBtn", false);
  }
}

async function compileWiki() {
  setBusy("compileWikiBtn", true);
  try {
    const result = await api("/wiki/compile", { method: "POST", body: "{}" });
    el("answerOutput").textContent = JSON.stringify(result, null, 2);
    await refreshAll();
  } catch (error) {
    el("answerOutput").textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    setBusy("compileWikiBtn", false);
  }
}

async function lintWiki() {
  setBusy("lintWikiBtn", true);
  try {
    const result = await api("/wiki/lint");
    el("answerOutput").textContent = JSON.stringify(result, null, 2);
    await refreshAll();
  } catch (error) {
    el("answerOutput").textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    setBusy("lintWikiBtn", false);
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
el("runGroupBtn").addEventListener("click", runGroup);
el("reindexBtn").addEventListener("click", reindex);
el("compileWikiBtn").addEventListener("click", compileWiki);
el("lintWikiBtn").addEventListener("click", lintWiki);
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
