const state = {
  health: null,
  index: { files: [], comments: [], store: {} },
  audit: [],
  governance: null,
  readiness: null,
  wikiSections: [],
  wikiPages: [],
  wikiPage: null,
  sourceRisk: null,
  explanation: null,
  llm: null,
  llmConfig: null,
};

const pages = new Set(["ask", "wiki", "studio", "sources", "agents", "governance", "audit"]);
const el = (id) => document.getElementById(id);

const LANG_KEY = "llmWikiLanguage";
const lang = localStorage.getItem(LANG_KEY) || "zh";
const I18N = {
  zh: {
    "nav.ask": "问答",
    "nav.wiki": "知识库",
    "nav.studio": "PPT",
    "nav.raw": "原始源",
    "nav.agents": "LLM配置",
    "nav.governance": "治理",
    "nav.audit": "审计",
    "top.subtitle": "知识运营",
    "top.title": "LLM Wiki 研究工作台",
    "toolbar.lang": "English",
    "toolbar.save": "保存",
    "toolbar.refresh": "刷新",
    "toolbar.reindex": "重建索引",
    "token.placeholder": "API token",
    "metric.files": "文件",
    "metric.comments": "评论",
    "metric.audit": "审计",
    "metric.wiki_sections": "Wiki 片段",
    "metric.source_risks": "风险项",
    "metric.database": "数据库",
    "metric.llm": "大模型",
    "metric.knowledge": "知识模式",
    "metric.auth": "鉴权",
    "sources.title": "原始源",
    "agents.title": "LLM 代理",
    "agents.enabled": "启用 LLM",
    "agents.default_agent": "默认代理",
    "agents.agent_list": "代理列表",
    "agents.category_map": "分类映射",
    "agents.add": "新增代理",
    "agents.save": "保存配置",
    "agents.add_mapping": "新增映射",
    "agents.default_fallback": "fallback",
    "agents.provider": "模型服务",
    "agents.model": "模型",
    "agents.base_url": "Base URL",
    "agents.api_key_env": "API Key 环境变量",
    "agents.env_file": "环境文件",
    "agents.timeout_seconds": "超时（秒）",
    "agents.max_context_chars": "上下文字符数",
    "agents.max_tokens": "Max Tokens",
    "agents.temperature": "Temperature",
    "agents.enabled_flag": "启用",
    "agents.actions": "操作",
    "agents.remove": "删除",
    "agents.name": "名称",
    "agents.category": "分类",
    "agents.agent": "代理",
  },
  en: {
    "nav.ask": "Ask",
    "nav.wiki": "Wiki",
    "nav.studio": "Studio",
    "nav.raw": "Raw",
    "nav.agents": "Agents",
    "nav.governance": "Governance",
    "nav.audit": "Audit",
    "top.subtitle": "Knowledge Operations",
    "top.title": "LLM Wiki Research Studio",
    "toolbar.lang": "中文",
    "toolbar.save": "Save",
    "toolbar.refresh": "Refresh",
    "toolbar.reindex": "Reindex",
    "token.placeholder": "API token",
    "metric.files": "Files",
    "metric.comments": "Comments",
    "metric.audit": "Audit Events",
    "metric.wiki_sections": "Wiki Sections",
    "metric.source_risks": "Source Risks",
    "metric.database": "Database",
    "metric.llm": "LLM",
    "metric.knowledge": "Knowledge",
    "metric.auth": "Auth",
    "sources.title": "Raw",
    "agents.title": "LLM Agents",
    "agents.enabled": "LLM enabled",
    "agents.default_agent": "Default agent",
    "agents.agent_list": "Agents",
    "agents.category_map": "Category mapping",
    "agents.add": "Add Agent",
    "agents.save": "Save",
    "agents.add_mapping": "Add Mapping",
    "agents.default_fallback": "fallback",
    "agents.provider": "Provider",
    "agents.model": "Model",
    "agents.base_url": "Base URL",
    "agents.api_key_env": "API Key env",
    "agents.env_file": "Env file",
    "agents.timeout_seconds": "Timeout (s)",
    "agents.max_context_chars": "Context chars",
    "agents.max_tokens": "Max tokens",
    "agents.temperature": "Temperature",
    "agents.enabled_flag": "Enabled",
    "agents.actions": "Actions",
    "agents.remove": "Remove",
    "agents.name": "Name",
    "agents.category": "Category",
    "agents.agent": "Agent",
  },
};

let currentLanguage = lang;

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
    const [health, index, audit, governance, readiness, wikiSections, wikiPages, sourceRisk] = await Promise.all([
      api("/health"),
      api("/index"),
      api("/audit?limit=25"),
      api("/reports/governance"),
      api("/reports/readiness"),
      api("/wiki/sections?limit=14"),
      api("/wiki/pages?limit=200"),
      api("/sources/risk")
    ]);
    const llmConfig = await api("/llm/config").catch(() => null);
    state.health = health;
    state.index = index;
    state.audit = audit.events || [];
    state.governance = governance.report || null;
    state.readiness = readiness.report || null;
    state.wikiSections = wikiSections.sections || [];
    state.wikiPages = wikiPages.pages || [];
    state.sourceRisk = sourceRisk;
    if (llmConfig) {
      state.llmConfig = llmConfig;
    }
    renderHealth();
    renderIndex();
    renderAudit();
    renderGovernance();
    renderReadiness();
    renderWikiPageList();
    renderWikiSections(state.wikiSections);
    renderLLMConfig();
    renderSourceRisk();
    await ensureWikiPagePreview();
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

function renderLLMConfig() {
  const config = state.llmConfig && state.llmConfig.llm ? state.llmConfig.llm : {};
  const agentMap = config.agents || {};
  const categoryMap = config.category_agents || {};
  const sourceCategories = (state.llmConfig && state.llmConfig.source_categories) || [];
  const agentNames = Object.keys(agentMap).sort();

  el("llmEnabled").checked = Boolean(config.enabled);
  el("llmDefaultAgent").value = String(config.default_agent || "default");

  el("llmAgentsList").innerHTML = agentNames.length
    ? agentNames.map((name) => llmAgentRow(name, agentMap[name] || {})).join("")
    : "";
  if (!agentNames.length) {
    el("llmAgentsList").innerHTML = emptyRow("No configured LLM agents");
  }

  renderLLMCategoryMappings(categoryMap, sourceCategories, agentNames);
}

function renderLLMCategoryMappings(categoryMap, sourceCategories, agentNames) {
  const rows = [...new Set([...Object.keys(categoryMap), ...sourceCategories.filter(Boolean)])].sort();
  if (!rows.length) {
    el("llmCategoryAgentMap").innerHTML = emptyRow("No category mapping");
    return;
  }
  el("llmCategoryAgentMap").innerHTML = rows
    .map((category) => llmCategoryMappingRow(category, categoryMap[category] || "", agentNames))
    .join("");
}

function llmAgentRow(name, data) {
  const defaults = {
    enabled: true,
    provider: "",
    model: "",
    base_url: "",
    api_key_env: "",
    env_file: "",
    timeout_seconds: 60,
    max_context_chars: 12000,
    max_tokens: 800,
    temperature: 0.1,
  };
  const cfg = { ...defaults, ...data };
  const rowId = `agent-${name}`;
  return `
    <div class="agent-row" data-agent-row="${escapeHtml(name)}">
      <div class="agent-row-head">
        <strong>${escapeHtml(name)}</strong>
        <button type="button" data-remove-agent="${escapeHtml(name)}" class="agent-remove-btn">${translate("agents.remove")}</button>
      </div>
      <div class="agent-fields">
        <label>
          <span>${translate("agents.enabled_flag")}</span>
          <input type="checkbox" ${cfg.enabled ? "checked" : ""} data-agent-enabled="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.provider")}</span>
          <input type="text" value="${escapeHtml(cfg.provider)}" data-agent-provider="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.model")}</span>
          <input type="text" value="${escapeHtml(cfg.model)}" data-agent-model="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.base_url")}</span>
          <input type="text" value="${escapeHtml(cfg.base_url)}" data-agent-base-url="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.api_key_env")}</span>
          <input type="text" value="${escapeHtml(cfg.api_key_env)}" data-agent-api-key-env="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.env_file")}</span>
          <input type="text" value="${escapeHtml(cfg.env_file)}" data-agent-env-file="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.timeout_seconds")}</span>
          <input type="number" value="${escapeHtml(cfg.timeout_seconds)}" data-agent-timeout="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.max_context_chars")}</span>
          <input type="number" value="${escapeHtml(cfg.max_context_chars)}" data-agent-context="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.max_tokens")}</span>
          <input type="number" value="${escapeHtml(cfg.max_tokens)}" data-agent-tokens="${escapeHtml(rowId)}" />
        </label>
        <label>
          <span>${translate("agents.temperature")}</span>
          <input type="number" step="0.1" value="${escapeHtml(cfg.temperature)}" data-agent-temperature="${escapeHtml(rowId)}" />
        </label>
      </div>
    </div>
  `;
}

function llmCategoryMappingRow(category, currentAgent, agentNames) {
  const optionElements = ["<option value=\"\">--</option>"]
    .concat(agentNames.map((agent) => `<option value="${escapeHtml(agent)}" ${agent === currentAgent ? "selected" : ""}>${escapeHtml(agent)}</option>`))
    .join("");
  return `
    <div class="category-map-row">
      <label>
        <span>${translate("agents.category")}</span>
        <input type="text" value="${escapeHtml(category)}" data-category-key />
      </label>
      <label>
        <span>${translate("agents.agent")}</span>
        <select data-category-agent>
          ${optionElements}
        </select>
      </label>
      <button type="button" class="category-map-remove" data-remove-category>${translate("agents.remove")}</button>
    </div>
  `;
}

function addAgentRow() {
  const container = el("llmAgentsList");
  const index = container.querySelectorAll(".agent-row").length + 1;
  const name = `agent-${index}`;
  const existing = new Set(Array.from(container.querySelectorAll(".agent-row")).map((row) => row.dataset.agentRow || ""));
  const uniqueName = existing.has(name) ? `${name}-${Date.now()}` : name;
  container.insertAdjacentHTML(
    "beforeend",
    llmAgentRow(uniqueName, {
      enabled: true,
      provider: "deepseek",
      model: "deepseek-chat",
      base_url: "https://api.deepseek.com/v1",
      api_key_env: "DEEPSEEK_API_KEY",
      env_file: "~/.hermes/.env",
    })
  );
}

function addCategoryMappingRow() {
  const container = el("llmCategoryAgentMap");
  const agentNames = Object.keys((state.llmConfig?.llm?.agents || {}));
  container.insertAdjacentHTML("beforeend", llmCategoryMappingRow("", "", agentNames));
}

function removeAgentRow(target) {
  const row = target.closest(".agent-row");
  if (!row) return;
  row.remove();
}

function removeCategoryMapping(target) {
  const row = target.closest(".category-map-row");
  if (!row) return;
  row.remove();
}

async function saveLlmConfig() {
  setBusy("saveAgentsBtn", true);
  el("llmConfigStatus").textContent = "Saving";
  try {
    const payload = collectLLMConfigPayload();
    const result = await api("/llm/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (result.error) {
      el("llmConfigStatus").textContent = `failed · ${result.error}`;
      return;
    }
    state.llmConfig = result;
    renderLLMConfig();
    el("llmConfigStatus").textContent = "Saved";
    await refreshAll();
  } catch (error) {
    el("llmConfigStatus").textContent = `failed · ${error.message}`;
  } finally {
    setBusy("saveAgentsBtn", false);
  }
}

function collectLLMConfigPayload() {
  const rawAgents = {};
  el("llmAgentsList")
    .querySelectorAll(".agent-row")
    .forEach((row) => {
      const name = row.dataset.agentRow || "";
      if (!name) return;
      const rowId = `agent-${name}`;
      const enabled = row.querySelector(`[data-agent-enabled="${CSS.escape(rowId)}"]`);
      const provider = row.querySelector(`[data-agent-provider="${CSS.escape(rowId)}"]`);
      const model = row.querySelector(`[data-agent-model="${CSS.escape(rowId)}"]`);
      const baseUrl = row.querySelector(`[data-agent-base-url="${CSS.escape(rowId)}"]`);
      const apiKeyEnv = row.querySelector(`[data-agent-api-key-env="${CSS.escape(rowId)}"]`);
      const envFile = row.querySelector(`[data-agent-env-file="${CSS.escape(rowId)}"]`);
      const timeout = row.querySelector(`[data-agent-timeout="${CSS.escape(rowId)}"]`);
      const maxContext = row.querySelector(`[data-agent-context="${CSS.escape(rowId)}"]`);
      const maxTokens = row.querySelector(`[data-agent-tokens="${CSS.escape(rowId)}"]`);
      const temperature = row.querySelector(`[data-agent-temperature="${CSS.escape(rowId)}"]`);
      if (!name.trim()) {
        return;
      }
      rawAgents[name] = {
        enabled: Boolean(enabled && enabled.checked),
        provider: String(provider?.value || "").trim(),
        model: String(model?.value || "").trim(),
        base_url: String(baseUrl?.value || "").trim(),
        api_key_env: String(apiKeyEnv?.value || "").trim(),
        env_file: String(envFile?.value || "").trim(),
        timeout_seconds: Number(timeout?.value || 60),
        max_context_chars: Number(maxContext?.value || 12000),
        max_tokens: Number(maxTokens?.value || 800),
        temperature: Number(temperature?.value || 0.1),
      };
    });

  const categoryAgents = {};
  el("llmCategoryAgentMap").querySelectorAll(".category-map-row").forEach((row) => {
    const key = row.querySelector("[data-category-key]");
    const select = row.querySelector("[data-category-agent]");
    const category = String(key?.value || "").trim();
    const target = String(select?.value || "").trim();
    if (category && target && rawAgents[target]) {
      categoryAgents[category] = target;
    }
  });

  return {
    enabled: Boolean(el("llmEnabled").checked),
    default_agent: String(el("llmDefaultAgent").value || "default").trim(),
    agents: rawAgents,
    category_agents: categoryAgents,
  };
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
  const readiness = state.readiness?.summary || {};
  const readinessText = readiness.status ? ` · readiness ${readiness.status}` : "";
  el("governanceSummary").textContent = `${summary.status || "unknown"} · ${riskCount} risks · ${summary.sources || 0} sources · ${report.todo?.total || 0} todos${readinessText}`;
}

function renderReadiness() {
  const report = state.readiness;
  if (!report) {
    el("readinessStatus").textContent = "not loaded";
    el("readinessList").innerHTML = emptyRow("No readiness report");
    return;
  }
  const summary = report.summary || {};
  const gates = report.gates || [];
  el("readinessStatus").textContent = `${summary.status || "unknown"} · score ${summary.score ?? 0} · ${summary.fail || 0} failing`;
  el("readinessList").innerHTML = gates.length
    ? gates.map(readinessRow).join("")
    : emptyRow("No readiness gates");
}

function readinessRow(item) {
  const status = item.status || "unknown";
  return `
    <div class="gate-row gate-${escapeHtml(status)}">
      <div class="gate-title">
        <strong>${escapeHtml(item.title || item.id || "Gate")}</strong>
        <span>${escapeHtml(status)}</span>
      </div>
      <p>${escapeHtml(item.evidence || "")}</p>
      ${status === "pass" ? "" : `<div class="meta"><span>${escapeHtml(item.remediation || "")}</span></div>`}
    </div>
  `;
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
  const sourceFindings = state.sourceRisk?.findings || [];
  const policyHeld = status === "quarantined" && sourceFindings.some((item) => {
    return item.source_path === finding.source_path && item.code === "permission_file_deny";
  });
  const actionLabel = policyHeld ? "Policy held" : status === "quarantined" ? "Activate" : "Quarantine";
  const disabled = policyHeld ? "disabled" : "";
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
        <button type="button" data-source-path="${escapeHtml(finding.source_path)}" data-source-status="${escapeHtml(nextStatus)}" ${disabled}>${actionLabel}</button>
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

function renderWikiPageList() {
  const pages = state.wikiPages || [];
  el("wikiPageStatus").textContent = `${pages.length} articles`;
  el("wikiPageList").innerHTML = pages.length
    ? pages.map(wikiPageRow).join("")
    : emptyRow("No compiled wiki articles");
}

function wikiPageRow(page) {
  const selectedPath = state.wikiPage?.page?.path || "";
  const active = selectedPath === page.path ? " active" : "";
  const meta = [page.kind, page.file_type, page.source_path].filter(Boolean).join(" · ");
  return `
    <button type="button" class="wiki-page-row${active}" data-wiki-page-path="${escapeHtml(page.path)}">
      <strong>${escapeHtml(page.title || page.path)}</strong>
      <span>${escapeHtml(meta || page.path)}</span>
      ${page.excerpt ? `<small>${escapeHtml(page.excerpt)}</small>` : ""}
    </button>
  `;
}

async function ensureWikiPagePreview() {
  const pages = state.wikiPages || [];
  if (!pages.length) {
    renderWikiPagePreview();
    return;
  }
  const selectedPath = state.wikiPage?.page?.path;
  const target = pages.some((page) => page.path === selectedPath) ? selectedPath : pages[0].path;
  if (!target) return;
  await loadWikiPage(target, { quiet: true });
}

async function loadWikiPage(path, options = {}) {
  if (!path) return;
  if (!options.quiet) {
    el("wikiPageMeta").textContent = "Loading";
  }
  try {
    const result = await api(`/wiki/page?path=${encodeURIComponent(path)}`);
    state.wikiPage = result;
    renderWikiPagePreview();
    renderWikiPageList();
  } catch (error) {
    el("wikiPageTitle").textContent = "Preview";
    el("wikiPageMeta").textContent = "Failed";
    el("wikiPagePreview").innerHTML = `<div class="answer-status blocked">${escapeHtml(error.message)}</div>`;
  }
}

function renderWikiPagePreview() {
  const detail = state.wikiPage || {};
  const page = detail.page || {};
  if (!page.path) {
    el("wikiPageTitle").textContent = "Preview";
    el("wikiPageMeta").textContent = "Select an article";
    el("wikiPagePreview").innerHTML = `<span class="muted">Select an article from the list.</span>`;
    return;
  }
  const meta = [page.kind, page.file_type, page.source_path || page.path].filter(Boolean).join(" · ");
  el("wikiPageTitle").textContent = page.title || page.path;
  el("wikiPageMeta").textContent = meta;
  el("wikiPagePreview").innerHTML = markdownToHtml(detail.markdown || "");
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

async function refreshReadiness() {
  setBusy("refreshReadinessBtn", true);
  try {
    const result = await api("/reports/readiness");
    state.readiness = result.report || null;
    renderGovernance();
    renderReadiness();
  } catch (error) {
    el("readinessStatus").textContent = `failed · ${error.message}`;
  } finally {
    setBusy("refreshReadinessBtn", false);
  }
}

async function exportReadiness() {
  setBusy("exportReadinessBtn", true);
  try {
    const result = await api("/reports/readiness/export", { method: "POST", body: selectedGroupsBody() });
    state.readiness = result.report || null;
    renderGovernance();
    renderReadiness();
    el("readinessStatus").innerHTML = `${escapeHtml(result.report?.summary?.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">Download readiness</a>`;
  } catch (error) {
    el("readinessStatus").textContent = `export failed · ${error.message}`;
  } finally {
    setBusy("exportReadinessBtn", false);
  }
}

async function exportRelease() {
  setBusy("exportReleaseBtn", true);
  try {
    const result = await api("/reports/release/export", { method: "POST", body: selectedGroupsBody() });
    const readiness = result.manifest?.reports?.readiness || "readiness";
    el("governanceSummary").innerHTML = `release bundle · ${escapeHtml(readiness)} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">Download release</a>`;
    await refreshAll();
  } catch (error) {
    el("governanceSummary").textContent = `release export failed · ${error.message}`;
  } finally {
    setBusy("exportReleaseBtn", false);
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

function markdownToHtml(markdown) {
  const lines = String(markdown || "").split("\n");
  const html = [];
  let inList = false;
  let inCode = false;
  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        html.push("</code></pre>");
        inCode = false;
      } else {
        if (inList) {
          html.push("</ul>");
          inList = false;
        }
        html.push("<pre><code>");
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      html.push(escapeHtml(line) + "\n");
      continue;
    }
    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      continue;
    }
    if (trimmed.startsWith("## ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h3>${escapeHtml(trimmed.slice(3))}</h3>`);
    } else if (trimmed.startsWith("# ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h2>${escapeHtml(trimmed.slice(2))}</h2>`);
    } else if (trimmed.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${formatInlineMarkdown(trimmed.slice(2))}</li>`);
    } else {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
    }
  }
  if (inList) html.push("</ul>");
  if (inCode) html.push("</code></pre>");
  return html.join("");
}

function formatInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[\[([^]|]+)\|([^]]+)\]\]/g, "$2")
    .replace(/\[\[([^]]+)\]\]/g, "$1");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function translate(key) {
  return I18N[currentLanguage]?.[key] || key;
}

function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (!key) return;
    const translation = translate(key);
    if (node.tagName === "INPUT" || node.tagName === "TEXTAREA") {
      node.placeholder = translation;
    } else {
      node.textContent = translation;
    }
  });

  document.querySelectorAll("[data-placeholder-i18n]").forEach((node) => {
    const key = node.getAttribute("data-placeholder-i18n");
    if (!key) return;
    node.placeholder = translate(key);
  });
  el("llmEnabled")?.setAttribute("aria-label", translate("agents.enabled"));
  renderLLMConfig();
}

function setLanguage(value) {
  currentLanguage = value === "en" ? "en" : "zh";
  localStorage.setItem(LANG_KEY, currentLanguage);
  applyLanguage();
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
el("refreshReadinessBtn").addEventListener("click", refreshReadiness);
el("exportReadinessBtn").addEventListener("click", exportReadiness);
el("exportReleaseBtn").addEventListener("click", exportRelease);
el("runEvaluationBtn").addEventListener("click", runEvaluation);
el("exportEvaluationBtn").addEventListener("click", exportEvaluation);
el("tokenForm").addEventListener("submit", (event) => event.preventDefault());
el("langToggle").addEventListener("click", () => setLanguage(currentLanguage === "zh" ? "en" : "zh"));
el("addAgentBtn").addEventListener("click", () => {
  if (!el("llmEnabled")) {
    return;
  }
  addAgentRow();
});
el("addCategoryMapBtn").addEventListener("click", addCategoryMappingRow);
el("saveAgentsBtn").addEventListener("click", saveLlmConfig);
window.addEventListener("hashchange", renderPage);
document.addEventListener("click", (event) => {
  const wikiPageButton = event.target.closest("[data-wiki-page-path]");
  if (wikiPageButton) {
    loadWikiPage(wikiPageButton.dataset.wikiPagePath || "");
    return;
  }
  const removeAgentBtn = event.target.closest("[data-remove-agent]");
  if (removeAgentBtn) {
    removeAgentRow(removeAgentBtn);
    return;
  }
  const removeCategoryBtn = event.target.closest("[data-remove-category]");
  if (removeCategoryBtn) {
    removeCategoryMapping(removeCategoryBtn);
    return;
  }
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
setLanguage(currentLanguage);
renderPage();
refreshAll();
