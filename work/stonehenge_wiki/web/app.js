const state = {
  health: null,
  index: { files: [], comments: [], store: {} },
  sources: [],
  indexError: null,
  sourcesError: null,
  audit: [],
  governance: null,
  readiness: null,
  wikiSections: [],
  wikiPages: [],
  wikiPage: null,
  sourceRisk: null,
  sourceDetail: null,
  sourceDetailPath: "",
  sourceDetailError: null,
  jobs: [],
  explanation: null,
  llm: null,
  llmConfig: null,
  wikiTreeFilter: "",
  wikiPageIndex: null,
};

const pages = new Set(["ask", "wiki", "studio", "sources", "agents", "governance", "audit"]);
const el = (id) => document.getElementById(id);

const LANG_KEY = "stonehengeWikiLanguage";
const lang = localStorage.getItem(LANG_KEY) || "zh";
const I18N = {
  zh: {
    "nav.ask": "问答",
    "nav.wiki": "知识库",
    "nav.studio": "工作台",
    "nav.raw": "原始源",
    "nav.agents": "LLM配置",
    "nav.governance": "治理",
    "nav.audit": "审计",
    "top.subtitle": "知识运营",
    "top.title": "Stonehenge Wiki",
    "title": "Stonehenge Wiki",
    "brand.title": "Stonehenge Wiki",
    "brand.subtitle": "Stonehenge Wiki",
    "ask.title": "问答",
    "ask.placeholder": "输入你的问题",
    "ask.button.ask": "提问",
    "ask.button.explain": "解释",
    "toolbar.lang": "English",
    "toolbar.save": "保存",
    "toolbar.refresh": "刷新",
    "toolbar.reindex": "重建索引",
    "token.placeholder": "API token",
    "token.label": "API token",
    "metric.files": "文件",
    "metric.comments": "评论",
    "metric.audit": "审计",
    "metric.wiki_sections": "Wiki 片段",
    "metric.source_risks": "风险项",
    "metric.database": "数据库",
    "metric.llm": "大模型",
    "metric.knowledge": "知识模式",
    "metric.auth": "鉴权",
    "sources.file_scope": "已激活 · 总数",
    "sources.import_placeholder": "公开 URL 或本地文件路径",
    "sources.import_title": "标题",
    "sources.import_category": "分类",
    "sources.comment_scope": "条",
    "sources.import_btn": "导入",
    "sources.title": "原始源",
    "sources.comments_title": "注释",
    "sources.detail_title": "来源详情",
    "sources.detail_hint": "选择一个来源查看抽取预览。",
    "sources.view_detail": "查看",
    "sources.preview_title": "抽取预览",
    "sources.preview_chars": "预览字符数",
    "sources.meta_title": "元数据",
    "sources.versions_title": "版本",
    "sources.reviews_title": "审核",
    "sources.sections_title": "Wiki 区段",
    "sources.risks_title": "风险",
    "question_groups.title": "问题组",
    "question_groups.subtitle": "question/group-*.md",
    "question_groups.placeholder": "group-1",
    "question_groups.run": "运行组",
    "wiki.articles": "文章",
    "wiki.tree": "知识树",
    "wiki.tree_search": "搜索知识节点",
    "wiki.graph": "知识图谱",
    "wiki.no_relations": "暂无可视化关联",
    "wiki.relation": "关联",
    "wiki.node_kind_index": "总览",
    "wiki.node_kind_source": "来源库",
    "wiki.node_kind_topic": "主题",
    "wiki.node_kind_log": "日志",
    "wiki.node_kind_other": "其他",
    "wiki.graph_source": "共享来源",
    "wiki.graph_kind": "同类型",
    "wiki.graph_folder": "同目录",
    "wiki.graph_link": "内链",
    "wiki.preview": "预览",
    "wiki.preview_hint": "从列表中选择一篇文章。",
    "wiki.explain": "解释",
    "wiki.compiled": "编译库",
    "wiki.search_placeholder": "搜索编译 wiki 段落",
    "wiki.path_description": "wiki/index.md · wiki/sources · wiki/topics · wiki/log.md",
    "wiki.search": "搜索",
    "wiki.compile": "编译",
    "wiki.lint": "检查",
    "wiki.explain_hint": "提问后查看路由、安全与证据。",
    "agents.title": "LLM 代理",
    "agents.enabled": "启用 LLM",
    "agents.default_agent": "默认代理",
    "agents.agent_list": "代理列表",
    "agents.category_map": "分类映射",
    "agents.add": "新增代理",
    "agents.save": "保存配置",
    "agents.test": "测试连接",
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
    "agents.runtime_mode": "运行模式",
    "agents.runtime_command": "运行时命令",
    "agents.runtime_api": "LLM API",
    "agents.runtime_opencode": "opencode",
    "studio.title": "工作台",
    "studio.topic_placeholder": "输入你的演讲主题",
    "studio.slides_4": "4 页",
    "studio.slides_6": "6 页",
    "studio.slides_8": "8 页",
    "studio.generate": "生成演示稿",
    "studio.hint": "暂无输出内容",
    "governance.title": "治理",
    "governance.summary_placeholder": "未加载报告",
    "governance.refresh_report": "刷新报告",
    "governance.export_markdown": "导出 Markdown",
    "governance.refresh_readiness": "刷新准备度",
    "governance.export_readiness": "导出准备度",
    "governance.export_release": "导出发布包",
    "governance.run_evaluation": "运行评估",
    "governance.export_evaluation": "导出评估",
    "governance.jobs_title": "作业历史",
    "governance.readiness_title": "发布前门禁",
    "governance.risk_title": "来源风险审核",
    "audit.title": "审计",
    "audit.subtitle": "最近事件",
    "status.saving": "保存中",
    "status.saved": "已保存",
    "status.testing": "测试中",
    "status.test_ok": "连接正常",
    "status.test_failed": "连接失败",
    "status.not_loaded": "未加载",
    "status.loading": "加载中",
    "status.preview": "预览",
    "status.select_article": "选择文章",
    "status.select_article_hint": "请先从列表选择一篇文章。",
    "status.running": "运行中",
    "status.complete": "完成",
    "status.tracing": "追踪中",
    "status.failed": "失败",
    "status.blocked": "已拦截",
    "status.importing": "导入中",
    "status.imported": "已导入",
    "status.reset": "重置",
    "status.updating": "更新中",
    "status.searching": "搜索中",
    "status.generating": "生成中",
    "status.active": "活跃",
    "status.total": "总数",
    "status.found": "条",
    "status.articles": "篇",
    "status.comments": "条注释",
    "status.questions": "问题",
    "status.unknown": "未知",
    "status.refresh": "刷新",
    "status.score": "得分",
    "status.risks": "风险",
    "status.sources": "来源",
    "status.jobs": "作业",
    "status.todos": "待办",
    "status.readiness": "准备度",
    "status.no_indexed_files": "尚无索引文件",
    "status.no_comments": "暂无注释",
    "status.no_audit_events": "暂无审计事件",
    "status.no_readiness_report": "尚无准备度报告",
    "status.no_readiness_gates": "尚无准备度门禁",
    "status.no_source_risks": "暂无来源风险",
    "status.no_jobs": "暂无作业记录",
    "status.no_evidence": "暂无证据",
    "status.version": "版本",
    "status.versions": "版本",
    "status.section": "区段",
    "status.sections": "区段",
    "status.untagged": "未标记",
    "status.sha_pending": "sha 待补",
    "status.untracked": "未入库",
    "status.disabled": "未启用",
    "status.model": "模型",
    "status.rag": "RAG",
    "status.wiki": "编译库",
    "status.open": "开放",
    "status.answer": "回答",
    "status.token_scopes": "令牌范围",
    "status.route": "路由",
    "status.safety": "安全",
    "status.wiki_mode": "知识库模式",
    "status.line": "行",
    "status.evidence": "证据",
    "status.download_pptx": "下载文件",
    "status.no_answer": "无回答",
    "status.no_configured_agents": "未配置 LLM 代理",
    "status.no_category_mapping": "未设置分类映射",
    "status.no_compiled_sections": "尚无编译 wiki 区段",
    "status.no_compiled_articles": "尚无编译文章",
    "status.download_report": "下载报告",
    "status.download_readiness": "下载准备度报告",
    "status.release_bundle": "发布包",
    "status.download_release": "下载发布包",
    "status.release_export_failed": "发布导出失败",
    "status.export_failed": "导出失败",
    "status.evaluation": "评估",
    "status.evaluation_label": "评估",
    "status.download_evaluation": "下载评估",
    "status.policy_held": "策略持有",
    "status.activate": "激活",
    "status.quarantine": "隔离",
    "status.online": "在线",
    "status.offline": "离线",
    "status.ready": "就绪",
  },
  en: {
    "nav.ask": "Ask",
    "nav.wiki": "Wiki",
    "nav.studio": "Workbench",
    "nav.raw": "Raw",
    "nav.agents": "Agents",
    "nav.governance": "Governance",
    "nav.audit": "Audit",
    "top.subtitle": "Knowledge Operations",
    "top.title": "Stonehenge Wiki",
    "title": "Stonehenge Wiki",
    "brand.title": "Stonehenge Wiki",
    "brand.subtitle": "Stonehenge Wiki",
    "ask.title": "Ask",
    "ask.placeholder": "Ask your question",
    "ask.button.ask": "Ask",
    "ask.button.explain": "Explain",
    "toolbar.lang": "中文",
    "toolbar.save": "Save",
    "toolbar.refresh": "Refresh",
    "toolbar.reindex": "Reindex",
    "token.placeholder": "API token",
    "token.label": "API token",
    "metric.files": "Files",
    "metric.comments": "Comments",
    "metric.audit": "Audit Events",
    "metric.wiki_sections": "Wiki Sections",
    "metric.source_risks": "Source Risks",
    "metric.database": "Database",
    "metric.llm": "LLM",
    "metric.knowledge": "Knowledge",
    "metric.auth": "Auth",
    "sources.file_scope": "active · total",
    "sources.import_placeholder": "Public URL or local file path",
    "sources.import_title": "Title",
    "sources.import_category": "Category",
    "sources.comment_scope": "found",
    "sources.import_btn": "Import",
    "sources.title": "Raw",
    "sources.comments_title": "Comments",
    "sources.detail_title": "Source Detail",
    "sources.detail_hint": "Select a source to inspect extracted preview.",
    "sources.view_detail": "View",
    "sources.preview_title": "Extracted preview",
    "sources.preview_chars": "Preview chars",
    "sources.meta_title": "Metadata",
    "sources.versions_title": "Versions",
    "sources.reviews_title": "Reviews",
    "sources.sections_title": "Wiki sections",
    "sources.risks_title": "Risks",
    "question_groups.title": "Question Groups",
    "question_groups.subtitle": "question/group-*.md",
    "question_groups.placeholder": "group-1",
    "question_groups.run": "Run Group",
    "wiki.articles": "Articles",
    "wiki.tree": "Knowledge Tree",
    "wiki.tree_search": "Search knowledge node",
    "wiki.graph": "Knowledge Graph",
    "wiki.no_relations": "No linked knowledge yet",
    "wiki.relation": "Related",
    "wiki.node_kind_index": "Index",
    "wiki.node_kind_source": "Sources",
    "wiki.node_kind_topic": "Topics",
    "wiki.node_kind_log": "Log",
    "wiki.node_kind_other": "Other",
    "wiki.graph_source": "Same source",
    "wiki.graph_kind": "Same kind",
    "wiki.graph_folder": "Same folder",
    "wiki.graph_link": "Wikilink",
    "wiki.preview": "Preview",
    "wiki.preview_hint": "Select an article from the list.",
    "wiki.explain": "Explain",
    "wiki.compiled": "Compiled Wiki",
    "wiki.search_placeholder": "Search compiled wiki sections",
    "wiki.path_description": "wiki/index.md · wiki/sources · wiki/topics · wiki/log.md",
    "wiki.search": "Search",
    "wiki.compile": "Compile",
    "wiki.lint": "Lint",
    "wiki.explain_hint": "Ask a question, then inspect route, safety, and evidence.",
    "agents.title": "LLM Agents",
    "agents.enabled": "LLM enabled",
    "agents.default_agent": "Default agent",
    "agents.agent_list": "Agents",
    "agents.category_map": "Category mapping",
    "agents.add": "Add Agent",
    "agents.save": "Save",
    "agents.test": "Test",
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
    "agents.runtime_mode": "Runtime mode",
    "agents.runtime_command": "Runtime command",
    "agents.runtime_api": "LLM API",
    "agents.runtime_opencode": "opencode",
    "studio.title": "Workbench",
    "studio.topic_placeholder": "Enter your speaking topic",
    "studio.slides_4": "4 slides",
    "studio.slides_6": "6 slides",
    "studio.slides_8": "8 slides",
    "studio.generate": "Generate Brief",
    "studio.hint": "No artifact yet",
    "governance.title": "Governance",
    "governance.summary_placeholder": "report not loaded",
    "governance.refresh_report": "Refresh Report",
    "governance.export_markdown": "Export Markdown",
    "governance.refresh_readiness": "Refresh Readiness",
    "governance.export_readiness": "Export Readiness",
    "governance.export_release": "Export Release",
    "governance.run_evaluation": "Run Evaluation",
    "governance.export_evaluation": "Export Evaluation",
    "governance.jobs_title": "Job History",
    "governance.readiness_title": "Readiness Gates",
    "governance.risk_title": "Source Risk Review",
    "audit.title": "Audit",
    "audit.subtitle": "latest events",
    "status.saving": "Saving",
    "status.saved": "Saved",
    "status.testing": "Testing",
    "status.test_ok": "Connected",
    "status.test_failed": "Connection failed",
    "status.not_loaded": "Not loaded",
    "status.loading": "Loading",
    "status.refresh": "Refresh",
    "status.preview": "Preview",
    "status.select_article": "Select an article",
    "status.select_article_hint": "Select an article from the list.",
    "status.running": "Running",
    "status.complete": "Complete",
    "status.tracing": "Tracing",
    "status.failed": "Failed",
    "status.blocked": "Blocked",
    "status.importing": "Importing",
    "status.imported": "Imported",
    "status.reset": "Reset",
    "status.updating": "Updating",
    "status.searching": "Searching",
    "status.generating": "Generating",
    "status.active": "active",
    "status.total": "total",
    "status.found": "found",
    "status.articles": "articles",
    "status.comments": "comments",
    "status.questions": "questions",
    "status.unknown": "unknown",
    "status.score": "score",
    "status.risks": "risks",
    "status.sources": "sources",
    "status.jobs": "jobs",
    "status.todos": "todos",
    "status.readiness": "readiness",
    "status.no_indexed_files": "No indexed files",
    "status.no_comments": "No comments",
    "status.no_audit_events": "No audit events",
    "status.no_readiness_report": "No readiness report",
    "status.no_readiness_gates": "No readiness gates",
    "status.no_source_risks": "No source risks",
    "status.no_jobs": "No jobs yet",
    "status.no_evidence": "No evidence",
    "status.version": "version",
    "status.versions": "versions",
    "status.section": "section",
    "status.sections": "sections",
    "status.untagged": "untagged",
    "status.sha_pending": "sha pending",
    "status.untracked": "untracked",
    "status.disabled": "disabled",
    "status.model": "model",
    "status.rag": "rag",
    "status.wiki": "wiki",
    "status.open": "open",
    "status.answer": "answer",
    "status.token_scopes": "token scopes",
    "status.route": "Route",
    "status.safety": "Safety",
    "status.wiki_mode": "Wiki mode",
    "status.line": "line",
    "status.evidence": "Evidence",
    "status.download_pptx": "Download file",
    "status.no_answer": "No answer",
    "status.no_configured_agents": "No configured LLM agents",
    "status.no_category_mapping": "No category mapping",
    "status.no_compiled_sections": "No compiled wiki sections",
    "status.no_compiled_articles": "No compiled wiki articles",
    "status.download_report": "Download report",
    "status.download_readiness": "Download readiness",
    "status.release_bundle": "release bundle",
    "status.download_release": "Download release",
    "status.release_export_failed": "Release export failed",
    "status.export_failed": "Export failed",
    "status.evaluation": "Evaluation",
    "status.evaluation_label": "Evaluation",
    "status.download_evaluation": "Download evaluation",
    "status.policy_held": "Policy held",
    "status.activate": "Activate",
    "status.quarantine": "Quarantine",
    "status.online": "Online",
    "status.offline": "Offline",
    "status.ready": "Ready",
  },
};

let currentLanguage = lang;
const URL_TOKEN_KEY = "stonehengeWikiApiToken";

{
  const tokenFromQuery = new URLSearchParams(window.location.search).get("token");
  if (tokenFromQuery) {
    localStorage.setItem(URL_TOKEN_KEY, tokenFromQuery);
    const cleanUrl = `${window.location.pathname}${window.location.hash || ""}`;
    window.history.replaceState({}, "", cleanUrl);
  }
}

async function api(path, options = {}) {
  const token = localStorage.getItem(URL_TOKEN_KEY) || "";
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "X-STONEHENGE-WIKI-TOKEN": token } : {}),
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

async function safeApiCall(path) {
  try {
    return { ok: true, data: await api(path), error: null };
  } catch (error) {
    return { ok: false, data: null, error: error.message };
  }
}

function buildSourcesFallback(sources) {
  return {
    files: (sources || [])
      .map((source) => ({
        path: source.rel_path || "",
        suffix: source.suffix || "file",
        tags: source.tags || [],
        comment_count: Number(source.comment_count || 0),
        risk: {
          risk_count: source.risk_count || 0,
          max_severity: source.max_severity || "none",
          reasons: [],
        },
        size: source.size,
      }))
      .sort((a, b) => String(a.path).localeCompare(String(b.path))),
    comments: [],
    presentations: [],
    store: {
      files: sources.length,
      comments: 0,
      audit_events: 0,
      wiki_sections: 0,
    },
    source_registry: sources.map((source) => ({
      ...source,
      rel_path: source.rel_path,
    })),
  };
}

async function refreshAll() {
  setBusy("refreshBtn", true);
  try {
    const [health, index, audit, governance, readiness, wikiSections, wikiPages, sourceRisk, jobs, sources, llmConfig] = await Promise.all([
      safeApiCall("/health"),
      safeApiCall("/index"),
      safeApiCall("/audit?limit=25"),
      safeApiCall("/reports/governance"),
      safeApiCall("/reports/readiness"),
      safeApiCall("/wiki/sections?limit=14"),
      safeApiCall("/wiki/pages?limit=200"),
      safeApiCall("/sources/risk"),
      safeApiCall("/jobs?limit=50"),
      safeApiCall("/sources?include_missing=1"),
      safeApiCall("/llm/config"),
    ]);

    const sourceItems = sources.ok ? (sources.data?.sources || []) : [];
    const fallbackIndex = sourceItems.length ? buildSourcesFallback(sourceItems) : null;
    const indexPayload = index.ok ? index.data : fallbackIndex || state.index;
    const healthPayload = health.ok ? health.data : state.health || { files: 0, comments: 0, store: {} };
    const readinessPayload = readiness.ok ? readiness.data : null;

    state.health = healthPayload;
    state.sources = sourceItems;
    state.index = indexPayload || { files: [], comments: [], store: {} };
    state.indexError = index.ok ? null : index.error;
    state.sourcesError = sources.ok ? null : sources.error;
    state.audit = audit.ok ? (audit.data.events || []) : [];
    state.governance = governance.ok ? (governance.data.report || null) : null;
    state.readiness = readinessPayload ? (readinessPayload.report || null) : null;
    state.wikiSections = wikiSections.ok ? (wikiSections.data.sections || []) : [];
    state.wikiPages = wikiPages.ok ? (wikiPages.data.pages || []) : [];
    state.sourceRisk = sourceRisk.ok ? sourceRisk.data : state.sourceRisk;
    state.jobs = jobs.ok ? (jobs.data.jobs || []) : [];
    state.wikiPageIndex = buildWikiPageIndex(state.wikiPages);
    if (llmConfig.ok) {
      state.llmConfig = llmConfig.data;
    }

    renderHealth();
    renderIndex();
    renderSourceDetail();
    renderAudit();
    renderGovernance();
    renderJobs();
    renderReadiness();
    renderWikiPageList();
    renderWikiSections(state.wikiSections);
    renderLLMConfig();
    renderSourceRisk();
    await ensureWikiPagePreview();
    setApiState(health.ok, health.error || "");
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
    ? `${llm.ready ? translate("status.online") : translate("status.offline")} · ${llm.model || llm.provider || translate("status.model")}`
    : translate("status.disabled");
  el("knowledgeMode").textContent = health.rag?.enabled ? translate("status.rag") : translate("status.wiki");
  const auth = health.auth || {};
  el("authName").textContent = auth.enabled ? translate("status.token_scopes") : translate("status.open");
}

function renderLLMConfig() {
  const config = state.llmConfig && state.llmConfig.llm ? state.llmConfig.llm : {};
  const agentMap = config.agents || {};
  const categoryMap = config.category_agents || {};
  const sourceCategories = (state.llmConfig && state.llmConfig.source_categories) || [];
  const agentNames = Object.keys(agentMap).sort();

  el("llmEnabled").checked = Boolean(config.enabled);
  el("llmDefaultAgent").value = String(config.default_agent || "default");
  el("llmRuntimeMode").value = String(config.runtime_mode || "api");
  el("llmRuntimeCommand").value = String(config.runtime_command || "");

  el("llmAgentsList").innerHTML = agentNames.length
    ? agentNames.map((name) => llmAgentRow(name, agentMap[name] || {})).join("")
    : "";
  if (!agentNames.length) {
    el("llmAgentsList").innerHTML = emptyRow(translate("status.no_configured_agents"));
  }

  renderLLMCategoryMappings(categoryMap, sourceCategories, agentNames);
}

function renderLLMCategoryMappings(categoryMap, sourceCategories, agentNames) {
  const rows = [...new Set([...Object.keys(categoryMap), ...sourceCategories.filter(Boolean)])].sort();
  if (!rows.length) {
    el("llmCategoryAgentMap").innerHTML = emptyRow(translate("status.no_category_mapping"));
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
    runtime_mode: "api",
    runtime_command: "",
  };
  const cfg = { ...defaults, ...data };
  const rowId = `agent-${name}`;
  return `
    <div class="agent-row" data-agent-row="${escapeHtml(name)}">
      <div class="agent-row-head">
        <div class="agent-heading">
          <strong>${escapeHtml(name)}</strong>
          <span class="agent-test-status" data-agent-test-status></span>
        </div>
        <div class="row-actions compact">
          <button type="button" data-test-agent="${escapeHtml(name)}">${translate("agents.test")}</button>
          <button type="button" data-remove-agent="${escapeHtml(name)}" class="agent-remove-btn">${translate("agents.remove")}</button>
        </div>
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
          <span>${translate("agents.runtime_mode")}</span>
          <select data-agent-runtime-mode="${escapeHtml(rowId)}">
            <option value="api" ${cfg.runtime_mode === "api" ? "selected" : ""}>${translate("agents.runtime_api")}</option>
            <option value="opencode" ${cfg.runtime_mode === "opencode" ? "selected" : ""}>${translate("agents.runtime_opencode")}</option>
          </select>
        </label>
        <label>
          <span>${translate("agents.runtime_command")}</span>
          <input type="text" value="${escapeHtml(cfg.runtime_command)}" data-agent-runtime-command="${escapeHtml(rowId)}" />
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
  el("llmConfigStatus").textContent = translate("status.saving");
  try {
    const payload = collectLLMConfigPayload();
    const result = await api("/llm/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (result.error) {
      el("llmConfigStatus").textContent = `${translate("status.failed")} · ${result.error}`;
      return;
    }
    state.llmConfig = result;
    renderLLMConfig();
    el("llmConfigStatus").textContent = translate("status.saved");
    await refreshAll();
  } catch (error) {
    el("llmConfigStatus").textContent = `${translate("status.failed")} · ${error.message}`;
  } finally {
    setBusy("saveAgentsBtn", false);
  }
}

async function testLlmAgent(target) {
  const row = target.closest(".agent-row");
  if (!row) return;
  const agentName = row.dataset.agentRow || "";
  const status = row.querySelector("[data-agent-test-status]");
  target.disabled = true;
  if (status) {
    status.className = "agent-test-status";
    status.textContent = translate("status.testing");
  }
  try {
    const result = await api("/llm/test", {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName, live: true }),
    });
    if (status) {
      const missing = Array.isArray(result.missing) && result.missing.length ? ` · ${result.missing.join(", ")}` : "";
      status.className = `agent-test-status ${result.status === "ok" ? "ok" : "fail"}`;
      status.textContent =
        result.status === "ok"
          ? `${translate("status.test_ok")} · ${result.model || agentName}`
          : `${translate("status.test_failed")} · ${result.error || translate("status.unknown")}${missing}`;
    }
    el("llmConfigStatus").textContent =
      result.status === "ok"
        ? `${translate("status.test_ok")} · ${agentName}`
        : `${translate("status.test_failed")} · ${agentName}`;
  } catch (error) {
    if (status) {
      status.className = "agent-test-status fail";
      status.textContent = `${translate("status.test_failed")} · ${error.message}`;
    }
    el("llmConfigStatus").textContent = `${translate("status.test_failed")} · ${error.message}`;
  } finally {
    target.disabled = false;
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
      const runtimeMode = row.querySelector(`[data-agent-runtime-mode="${CSS.escape(rowId)}"]`);
      const runtimeCommand = row.querySelector(`[data-agent-runtime-command="${CSS.escape(rowId)}"]`);
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
        runtime_mode: String(runtimeMode?.value || "api").trim(),
        runtime_command: String(runtimeCommand?.value || "").trim(),
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
    runtime_mode: String(el("llmRuntimeMode")?.value || "api").trim(),
    runtime_command: String(el("llmRuntimeCommand")?.value || "").trim(),
    agents: rawAgents,
    category_agents: categoryAgents,
  };
}

function renderIndex() {
  const files = state.index.files || [];
  const comments = state.index.comments || [];
  const presentations = state.index.presentations || [];
  const registry = state.index.source_registry || state.sources || [];
  const sourceByPath = Object.fromEntries(
    registry.map((source) => [source.rel_path || source.path || source.source_path, source])
  );
  const activeCount = registry.filter((source) => source.status === "active").length || files.length;
  el("fileScope").textContent = `${activeCount} ${translate("status.active")} · ${registry.length || files.length} ${translate("status.total")}`;
  el("commentScope").textContent = `${comments.length} ${translate("status.found")}`;
  el("fileList").innerHTML = files.length
    ? files.map((file) => fileRow(file, sourceByPath[file.path])).join("")
    : emptySourceRow(state.sourcesError || state.indexError || translate("status.no_indexed_files"));
  el("commentList").innerHTML = comments.length
    ? comments.slice(0, 80).map(commentRow).join("")
    : emptyRow(translate("status.no_comments"));
  renderPresentations(presentations);
}

function fileRow(file, source) {
  const tags = (file.tags || []).join(", ") || translate("status.untagged");
  const size = source ? `${Math.round(Number(source.size || 0) / 1024)} KB` : translate("status.untracked");
  const hash = source?.sha256 ? `sha ${String(source.sha256).slice(0, 10)}` : translate("status.sha_pending");
  const versionCount = Number(source?.version_count || 0);
  const versions = `${versionCount} ${versionCount === 1 ? translate("status.version") : translate("status.versions")}`;
  const sectionCount = Number(source?.wiki_section_count || 0);
  const sections = `${sectionCount} ${sectionCount === 1 ? translate("status.section") : translate("status.sections")}`;
  const origin = source?.origin_type || "local";
  const status = source?.status || "active";
  return `
    <div class="source-row">
      <div class="source-row-title">
        <strong>${escapeHtml(file.path)}</strong>
        <button type="button" data-source-detail="${escapeHtml(file.path)}">${translate("sources.view_detail")}</button>
      </div>
      <div class="meta">
        <span class="${status === "active" ? "ok" : "blocked"}">${escapeHtml(status)}</span>
        <span>${escapeHtml(origin)}</span>
        <span>${escapeHtml(size)}</span>
        <span>${escapeHtml(hash)}</span>
        <span>${escapeHtml(versions)}</span>
        <span>${escapeHtml(sections)}</span>
        <span>${escapeHtml(file.suffix || "file")}</span>
        <span>${escapeHtml(tags)}</span>
        <span>${Number(file.comment_count || 0)} ${translate("status.comments")}</span>
      </div>
    </div>
  `;
}

function getSourcePreviewChars() {
  const value = Number.parseInt(el("sourcePreviewChars")?.value || "8000", 10);
  if (!Number.isFinite(value) || value <= 0) {
    return 8000;
  }
  return Math.min(value, 20000);
}

function setSourceDetailPath(path) {
  state.sourceDetailPath = String(path || "").trim();
}

async function loadSourceDetail(path) {
  const sourcePath = String(path || "").trim();
  if (!sourcePath) return;
  setSourceDetailPath(sourcePath);
  el("sourceDetailStatus").textContent = translate("status.loading");
  try {
    const previewChars = getSourcePreviewChars();
    const result = await api(
      `/sources/detail?path=${encodeURIComponent(sourcePath)}&preview_chars=${encodeURIComponent(String(previewChars))}`
    );
    if (result.error) {
      state.sourceDetail = null;
      state.sourceDetailError = result.error;
      el("sourceDetailStatus").textContent = `${translate("status.failed")} · ${result.error}`;
    } else {
      state.sourceDetail = result;
      state.sourceDetailError = null;
      el("sourceDetailStatus").textContent = result.path || translate("status.complete");
    }
  } catch (error) {
    state.sourceDetail = null;
    state.sourceDetailError = error.message;
    el("sourceDetailStatus").textContent = `${translate("status.failed")} · ${error.message}`;
  }
  renderSourceDetail();
}

function renderSourceDetail() {
  const detail = state.sourceDetail;
  if (!detail) {
    el("sourceDetail").innerHTML = `<span class="muted">${escapeHtml(state.sourceDetailError || translate("sources.detail_hint"))}</span>`;
    if (!state.sourceDetailError) {
      el("sourceDetailStatus").textContent = translate("sources.detail_hint");
    }
    return;
  }
  const source = detail.source || {};
  const preview = detail.preview || {};
  const metaItems = [
    ["path", detail.path],
    ["status", source.status],
    ["origin", source.origin_type],
    ["category", source.category],
    ["suffix", source.suffix],
    ["size", source.size],
    ["sha", source.sha256 ? String(source.sha256).slice(0, 16) : ""],
    ["active", detail.active ? "true" : "false"],
    ["versions", source.version_count],
    ["wiki sections", source.wiki_section_count],
  ];
  const versionRows = (detail.versions || []).map((item) => `
    <div class="detail-row">
      <strong>${escapeHtml(String(item.sha256 || "").slice(0, 16))}</strong>
      <span>${escapeHtml(item.last_seen_at || item.first_seen_at || "")}</span>
      <span>${escapeHtml(String(item.observation_count || 0))}</span>
    </div>
  `).join("");
  const reviewRows = (detail.reviews || []).map((item) => `
    <div class="detail-row">
      <strong>${escapeHtml(item.status || "")}</strong>
      <span>${escapeHtml(item.actor || "")}</span>
      <span>${escapeHtml(item.reason || item.created_at || "")}</span>
    </div>
  `).join("");
  const riskRows = (detail.risks || []).map((item) => `
    <div class="detail-row">
      <strong>${escapeHtml(item.code || "")}</strong>
      <span>${escapeHtml(item.severity || "")}</span>
      <span>${escapeHtml(item.message || "")}</span>
    </div>
  `).join("");
  const sectionRows = (detail.wiki_sections || []).map(wikiSectionRow).join("");
  const commentRows = (detail.comments || []).map((comment) => `<div class="detail-row"><span>${escapeHtml(comment)}</span></div>`).join("");
  el("sourceDetail").innerHTML = `
    <div class="source-detail-grid">
      <section>
        <h3>${translate("sources.meta_title")}</h3>
        <div class="detail-kv">
          ${metaItems.filter(([, value]) => value !== undefined && value !== null && value !== "").map(([key, value]) => `
            <div><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
          `).join("")}
        </div>
      </section>
      <section>
        <h3>${translate("sources.preview_title")}</h3>
        <pre class="source-preview">${escapeHtml(preview.text || "") || escapeHtml(translate("status.no_evidence"))}</pre>
      </section>
      <section>
        <h3>${translate("sources.versions_title")}</h3>
        ${versionRows || emptyRow(translate("status.no_evidence"))}
      </section>
      <section>
        <h3>${translate("sources.reviews_title")}</h3>
        ${reviewRows || emptyRow(translate("status.no_evidence"))}
      </section>
      <section>
        <h3>${translate("sources.risks_title")}</h3>
        ${riskRows || emptyRow(translate("status.no_source_risks"))}
      </section>
      <section>
        <h3>${translate("status.comments")}</h3>
        ${commentRows || emptyRow(translate("status.no_comments"))}
      </section>
      <section>
        <h3>${translate("sources.sections_title")}</h3>
        ${sectionRows || emptyRow(translate("status.no_compiled_sections"))}
      </section>
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
    : emptyRow(translate("status.no_audit_events"));
}

function renderGovernance() {
  const report = state.governance;
  if (!report) {
    el("governanceSummary").textContent = translate("governance.summary_placeholder");
    return;
  }
  const summary = report.summary || {};
  const riskCount = (report.risks || []).length;
  const readiness = state.readiness?.summary || {};
  const readinessText = readiness.status ? ` · ${translate("status.readiness")} ${readiness.status}` : "";
  const summaryStatusText = summary.status || translate("status.unknown");
  el("governanceSummary").textContent = `${summaryStatusText} · ${riskCount} ${translate("status.risks")} · ${summary.sources || 0} ${translate("status.sources")} · ${report.todo?.total || 0} ${translate("status.todos")}${readinessText}`;
}

function renderJobs() {
  const rows = state.jobs || [];
  el("jobsStatus").textContent = `${rows.length} ${translate("status.jobs")}`;
  el("jobsList").innerHTML = rows.length
    ? rows.map((job) => jobRow(job)).join("")
    : emptyRow(translate("status.no_jobs"));
}

function jobRow(job) {
  const createdAt = job.created_at || "";
  const input = job.input ? JSON.stringify(job.input) : "";
  const output = job.output ? JSON.stringify(job.output) : "";
  return `
    <div class="job-row">
      <div class="job-title-row">
        <strong>${escapeHtml(job.job_type || "")}</strong>
        <span class="${job.status === "ok" ? "ok" : "blocked"}">${escapeHtml(job.status || "")}</span>
      </div>
      <div class="meta">
        <span>${escapeHtml(createdAt)}</span>
        <span>${escapeHtml(job.id ? String(job.id) : "")}</span>
      </div>
      ${input ? `<pre class="job-preview">${escapeHtml(input.slice(0, 240))}${String(input).length > 240 ? "…" : ""}</pre>` : ""}
      ${output ? `<pre class="job-preview">${escapeHtml(output.slice(0, 240))}${String(output).length > 240 ? "…" : ""}</pre>` : ""}
    </div>
  `;
}

function renderReadiness() {
  const report = state.readiness;
  if (!report) {
    el("readinessStatus").textContent = translate("status.not_loaded");
    el("readinessList").innerHTML = emptyRow(translate("status.no_readiness_report"));
    return;
  }
  const summary = report.summary || {};
  const gates = report.gates || [];
  el("readinessStatus").textContent = `${summary.status || translate("status.unknown")} · ${translate("status.score")} ${summary.score ?? 0} · ${summary.fail || 0} ${translate("status.failed")}`;
  el("readinessList").innerHTML = gates.length
    ? gates.map(readinessRow).join("")
    : emptyRow(translate("status.no_readiness_gates"));
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
  el("riskStatus").textContent = `${summary.status || translate("status.unknown")} · ${summary.sources_with_risks || 0} ${translate("status.sources")}`;
  el("riskList").innerHTML = findings.length
    ? findings.slice(0, 80).map((finding) => riskRow(finding)).join("")
    : emptyRow(translate("status.no_source_risks"));
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
  const actionLabel = policyHeld
    ? translate("status.policy_held")
    : status === "quarantined"
      ? translate("status.activate")
      : translate("status.quarantine");
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
  el("wikiStatus").textContent = `${list.length} ${translate("status.sections")}`;
  el("wikiSectionList").innerHTML = list.length
    ? list.map(wikiSectionRow).join("")
    : emptyRow(translate("status.no_compiled_sections"));
}

function renderWikiPageList() {
  const pages = state.wikiPages || [];
  const filter = (state.wikiTreeFilter || "").trim().toLowerCase();
  const groups = buildWikiTreeGroups(pages, filter);
  const visibleCount = countVisibleTreePages(groups);
  el("wikiPageStatus").textContent = `${visibleCount} / ${pages.length} ${translate("status.articles")}`;
  el("wikiTreeList").innerHTML = pages.length
    ? renderWikiTreeGroups(groups, filter)
    : emptyRow(translate("status.no_compiled_articles"));
}

function buildWikiTreeGroups(pages, filter) {
  const matchTerm = (filter || "").trim().toLowerCase();
  const groupOrder = ["index", "source", "topic", "log", "other"];
  const groups = {
    index: { key: "index", title: translate("wiki.node_kind_index"), folders: new Map(), pages: [] },
    source: { key: "source", title: translate("wiki.node_kind_source"), folders: new Map(), pages: [] },
    topic: { key: "topic", title: translate("wiki.node_kind_topic"), folders: new Map(), pages: [] },
    log: { key: "log", title: translate("wiki.node_kind_log"), folders: new Map(), pages: [] },
    other: { key: "other", title: translate("wiki.node_kind_other"), folders: new Map(), pages: [] },
  };
  const getKind = (kind) => {
    const normalized = String(kind || "").trim().toLowerCase();
    return normalized === "index" || normalized === "source" || normalized === "topic" || normalized === "log"
      ? normalized
      : "other";
  };
  const matchesFilter = (page) => {
    if (!matchTerm) {
      return true;
    }
    return [page.title, page.path, page.excerpt, page.kind, page.file_type, page.source_path]
      .some((value) => String(value || "").toLowerCase().includes(matchTerm));
  };
  const normalizeSegments = (path) => String(path || "").replace(/\.md$/i, "").split("/").filter(Boolean);
  const insertFolder = (node, segments, pageNode) => {
    if (!segments.length) {
      node.pages.push(pageNode);
      return;
    }
    const [head, ...rest] = segments;
    const bucketKey = `folder:${head}`;
    if (!node.folders.has(bucketKey)) {
      node.folders.set(bucketKey, {
        label: head,
        folders: new Map(),
        pages: [],
      });
    }
    insertFolder(node.folders.get(bucketKey), rest, pageNode);
  };
  for (const page of pages || []) {
    const pageKind = getKind(page.kind);
    const group = groups[pageKind];
    const matched = matchesFilter(page);
    const pageNode = {
      path: page.path,
      title: page.title || page.path,
      kind: page.kind || pageKind,
      source_path: page.source_path || "",
      file_type: page.file_type || "",
      excerpt: page.excerpt || "",
      match: matched,
    };
    let segments = normalizeSegments(page.path);
    if (pageKind === "source" && segments[0] === "sources") {
      segments = segments.slice(1);
    }
    if (pageKind === "topic" && segments[0] === "topics") {
      segments = segments.slice(1);
    }
    if (segments.length > 1) {
      insertFolder(group, segments.slice(0, -1), pageNode);
    } else {
      group.pages.push(pageNode);
    }
  }
  return groupOrder.map((kind) => groups[kind]);
}

function countVisibleNodePages(node) {
  let count = 0;
  for (const page of node.pages || []) {
    if (page.match) {
      count += 1;
    }
  }
  for (const folder of node.folders.values()) {
    count += countVisibleNodePages(folder);
  }
  return count;
}

function countVisibleTreePages(groups) {
  return groups.reduce((total, group) => total + countVisibleNodePages(group), 0);
}

function renderWikiTreeGroups(groups, filter) {
  const showAllFolders = !filter || (filter || "").trim().length <= 2;
  const renderNode = (node, depth) => {
    const indent = Math.min(8 + depth * 16, 52);
    const pageRows = [];
    for (const page of node.pages || []) {
      if (!page.match) {
        continue;
      }
      const selectedPath = state.wikiPage?.page?.path || "";
      const active = selectedPath === page.path ? " active" : "";
      const meta = [page.kind, page.file_type, page.source_path].filter(Boolean).join(" · ");
      pageRows.push(`
        <button type="button" class="wiki-tree-page${active}" style="padding-left:${indent}px" data-wiki-page-path="${escapeHtml(page.path)}">
          <span class="wiki-tree-page-title">${escapeHtml(page.title || page.path)}</span>
          <span class="wiki-tree-page-meta">${escapeHtml(meta || page.path)}</span>
        </button>
      `);
    }

    const folderRows = [];
    for (const folder of [...node.folders.values()].sort((a, b) => a.label.localeCompare(b.label))) {
      const nested = renderNode(folder, depth + 1);
      const childCount = countVisibleNodePages(folder);
      if (!nested && !childCount) continue;
      const open = showAllFolders || depth <= 1 ? "open" : "";
      folderRows.push(`
        <details class="wiki-tree-folder" ${open}>
          <summary style="padding-left:${indent}px">
            ${escapeHtml(folder.label)} <span>${childCount}</span>
          </summary>
          <div class="wiki-tree-folder-children">
            ${nested}
          </div>
        </details>
      `);
    }

    return pageRows.concat(folderRows).join("");
  };

  const items = groups
    .map((group) => {
      const child = renderNode(group, 0);
      const count = countVisibleNodePages(group);
      if (!count) {
        return "";
      }
      return `
        <details class="wiki-tree-group" open>
          <summary style="padding-left:6px">
            <span>${escapeHtml(group.title)}</span>
            <span>${count}</span>
          </summary>
          <div class="wiki-tree-group-children">
            ${child || emptyRow(translate("wiki.no_relations"))}
          </div>
        </details>
      `;
    })
    .filter(Boolean)
    .join("");

  if (items) {
    return items;
  }

  if (filter) {
    return emptyRow(translate("status.no_compiled_articles"));
  }

  return emptyRow(translate("status.no_compiled_articles"));
}

function buildWikiPageIndex(pages) {
  const byPath = {};
  const byPathStem = {};
  const byTitle = {};
  for (const page of pages || []) {
    if (!page?.path) {
      continue;
    }
    byPath[page.path] = page;
    const stem = normalizeWikiPath(page.path);
    byPathStem[stem] = byPathStem[stem] || [];
    byPathStem[stem].push(page);
    const titleKey = String(page.title || page.path).trim().toLowerCase();
    byTitle[titleKey] = byTitle[titleKey] || [];
    byTitle[titleKey].push(page);
  }
  return {
    byPath,
    byPathStem,
    byTitle,
  };
}

function normalizeWikiPath(value) {
  return String(value || "").replace(/\.md$/i, "").replace(/^\/+/, "").toLowerCase();
}

function resolveWikiPathCandidate(candidate) {
  if (!candidate) return "";
  const raw = String(candidate).trim().replace(/\.md$/i, "");
  if (!raw) return "";
  return raw.includes("/") || raw.includes(".") ? raw : raw.replace(/\s+/g, "-");
}

function parseWikiLinksFromMarkdown(markdown) {
  const found = [];
  const pattern = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
  let match;
  while ((match = pattern.exec(markdown || "")) !== null) {
    const target = String(match[1] || "").trim();
    if (!target || target.startsWith("http")) {
      continue;
    }
    const normalized = target.split("#", 1)[0].trim();
    if (normalized) {
      found.push(normalized);
    }
  }
  return found;
}

function findWikiPageByLink(candidate, currentPage) {
  const lookup = state.wikiPageIndex || {};
  const raw = resolveWikiPathCandidate(candidate);
  if (!raw) return "";
  if (lookup.byPath?.[candidate]) {
    return candidate;
  }
  if (lookup.byPath?.[`${raw}.md`]) {
    return `${raw}.md`;
  }
  if (lookup.byPathStem?.[raw]) {
    return lookup.byPathStem[raw][0]?.path || "";
  }
  const currentSource = String(currentPage?.source_path || "");
  if (currentSource) {
    for (const item of Object.values(lookup.byPath || {})) {
      if (item.source_path === currentSource && item.path.endsWith(`/${raw}.md`)) {
        return item.path;
      }
    }
  }
  const titleMatches = lookup.byTitle?.[raw.toLowerCase()];
  return titleMatches?.[0]?.path || "";
}

function extractGraphRelations(page, markdown) {
  const current = page || {};
  const relations = [];
  const existing = new Set();
  const addRelation = (targetPath, reason) => {
    if (!targetPath || targetPath === current.path) return;
    if (existing.has(targetPath)) return;
    const target = (state.wikiPageIndex?.byPath || {})[targetPath];
    if (!target) return;
    existing.add(targetPath);
    relations.push({
      path: target.path,
      title: target.title || target.path,
      reason,
    });
  };

  const linkTargets = parseWikiLinksFromMarkdown(markdown || "");
  linkTargets.forEach((target) => {
    const resolved = findWikiPageByLink(target, current);
    addRelation(resolved, translate("wiki.graph_link"));
  });

  for (const candidate of state.wikiPages || []) {
    if (candidate.path === current.path) continue;
    if (current.source_path && candidate.source_path && current.source_path === candidate.source_path) {
      addRelation(candidate.path, translate("wiki.graph_source"));
    }
    if (candidate.kind === current.kind && current.kind) {
      addRelation(candidate.path, translate("wiki.graph_kind"));
    }
    const currentFolder = String(candidate.path).split("/")[0];
    const currentSelfFolder = String(current.path).split("/")[0];
    if (currentFolder && currentFolder === currentSelfFolder) {
      addRelation(candidate.path, translate("wiki.graph_folder"));
    }
  }

  return relations.slice(0, 12);
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
    el("wikiPageMeta").textContent = translate("status.loading");
  }
  try {
    const result = await api(`/wiki/page?path=${encodeURIComponent(path)}`);
    state.wikiPage = result;
    renderWikiPagePreview();
    renderWikiPageList();
  } catch (error) {
    el("wikiPageTitle").textContent = translate("wiki.preview");
    el("wikiPageMeta").textContent = translate("status.failed");
    el("wikiPagePreview").innerHTML = `<div class="answer-status blocked">${escapeHtml(error.message)}</div>`;
  }
}

function renderWikiPagePreview() {
  const detail = state.wikiPage || {};
  const page = detail.page || {};
  if (!page.path) {
    el("wikiPageTitle").textContent = translate("wiki.preview");
    el("wikiPageMeta").textContent = translate("status.select_article");
    el("wikiPagePreview").innerHTML = `<span class="muted">${translate("wiki.preview_hint")}</span>`;
    el("wikiGraph").innerHTML = emptyRow(translate("wiki.no_relations"));
    el("wikiGraphStatus").textContent = translate("status.select_article");
    return;
  }
  const meta = [page.kind, page.file_type, page.source_path || page.path].filter(Boolean).join(" · ");
  el("wikiPageTitle").textContent = page.title || page.path;
  el("wikiPageMeta").textContent = meta;
  el("wikiPagePreview").innerHTML = markdownToHtml(detail.markdown || "");
  renderWikiRelations(detail);
}

function renderWikiRelations(detail) {
  const page = detail.page || {};
  const relations = extractGraphRelations(page, detail.markdown || "");
  el("wikiGraphStatus").textContent = `${relations.length} ${translate("wiki.relation")}`;
  el("wikiGraph").innerHTML = relations.length
    ? relations
        .map((relation) => {
          return `
            <div class="wiki-graph-row">
              <button type="button" class="wiki-graph-node" data-wiki-page-path="${escapeHtml(relation.path)}">
                ${escapeHtml(relation.title || relation.path)}
              </button>
              <span class="wiki-graph-arrow">↔</span>
              <span class="wiki-graph-reason muted">${escapeHtml(relation.reason || "")}</span>
            </div>
          `;
        })
        .join("")
    : `<div class="wiki-graph-empty muted">${translate("wiki.no_relations")}</div>`;
}

function wikiSectionRow(section) {
  const snippet = section.snippet || section.body || "";
  return `
    <div class="wiki-section-row">
      <div class="wiki-section-title">
        <strong>${escapeHtml(section.heading || section.page_title || translate("status.section"))}</strong>
        <span>${escapeHtml(section.kind || "wiki")}</span>
      </div>
      <p>${escapeHtml(snippet.slice(0, 360))}</p>
      <div class="meta">
        <span>${escapeHtml(section.page_path || "")}</span>
        <span>${escapeHtml(section.source_path || translate("status.untagged"))}</span>
        <span>${translate("status.line")} ${Number(section.line_start || 0)}</span>
        ${section.score ? `<span>${translate("status.score")} ${Number(section.score)}</span>` : ""}
      </div>
    </div>
  `;
}

function renderPresentations(presentations) {
  if (!presentations.length) {
    el("artifactOutput").innerHTML = `<span class="muted">${translate("studio.hint")}</span>`;
    return;
  }
  el("artifactOutput").innerHTML = presentations
    .slice(0, 4)
    .map((item) => `
      <div class="artifact-card">
        <strong>${escapeHtml(item.name || item.deck)}</strong>
        <span>${Math.round(Number(item.size || 0) / 1024)} KB</span>
        <a href="${escapeHtml(item.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_pptx")}</a>
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
  el("queryStatus").textContent = translate("status.running");
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
    el("queryStatus").textContent = answer.answer?.error_msg ? translate("status.blocked") : translate("status.complete");
    await refreshAll();
  } catch (error) {
    el("answerOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("queryStatus").textContent = translate("status.failed");
  } finally {
    setBusy("askBtn", false);
  }
}

async function explainQuestion() {
  const title = el("questionInput").value.trim();
  if (!title) return;
  setBusy("explainBtn", true);
  el("explainStatus").textContent = translate("status.tracing");
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
    el("explainStatus").textContent = explanation.status || translate("status.complete");
    setPage("wiki");
  } catch (error) {
    el("explainOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("explainStatus").textContent = translate("status.failed");
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
        <span>${translate("status.route")}</span>
        <strong>${escapeHtml(explanation.route || "knowledge")}</strong>
      </div>
      <div>
        <span>${translate("status.safety")}</span>
        <strong class="${safetyClass}">${escapeHtml(safety.blocked ? "blocked" : "ok")}</strong>
      </div>
      <div>
        <span>${translate("status.wiki_mode")}</span>
        <strong>${escapeHtml(wiki.mode || "compiled_wiki")}</strong>
      </div>
      <div>
        <span>${translate("status.sections")}</span>
        <strong>${Number(wiki.section_count || 0)}</strong>
      </div>
    </div>
    ${safety.reason ? `<div class="answer-status blocked">${escapeHtml(safety.reason)}</div>` : ""}
    <h3>${translate("status.evidence")}</h3>
    <div class="trace-list">
      ${(evidence.length ? evidence : records.slice(0, 6)).map(traceRow).join("") || emptyRow(translate("status.no_evidence"))}
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
        ${item.line ? `<span>${translate("status.line")} ${Number(item.line)}</span>` : ""}
        ${item.score ? `<span>${translate("status.score")} ${Number(item.score)}</span>` : ""}
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
    <div class="answer-status ok">${escapeHtml(answer.id || translate("status.answer"))}</div>
    ${body || `<p class="muted">${translate("status.no_answer")}</p>`}
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
  el("importStatus").textContent = translate("status.importing");
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
      el("importStatus").textContent = `${translate("status.blocked")} · ${result.reason || result.error_msg}`;
      return;
    }
    el("importStatus").textContent = `${translate("status.imported")} · ${result.path}`;
    await refreshAll();
  } catch (error) {
    el("importStatus").textContent = `${translate("status.failed")} · ${error.message}`;
  } finally {
    setBusy("importBtn", false);
  }
}

async function setSourceStatus(path, status, button) {
  if (!path || !status) return;
  if (button) button.disabled = true;
  el("riskStatus").textContent = translate("status.updating");
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
      el("riskStatus").textContent = `${translate("status.failed")} · ${result.error}`;
      return;
    }
    await refreshAll();
  } catch (error) {
    el("riskStatus").textContent = `${translate("status.failed")} · ${error.message}`;
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
  el("wikiStatus").textContent = translate("status.searching");
  try {
    const result = await api(path);
    state.wikiSections = result.sections || [];
    renderWikiSections(state.wikiSections);
  } catch (error) {
    el("wikiSectionList").innerHTML = `<pre>${escapeHtml(JSON.stringify({ error: error.message }, null, 2))}</pre>`;
    el("wikiStatus").textContent = translate("status.failed");
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
    el("governanceSummary").textContent = `${translate("status.failed")} · ${error.message}`;
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
    el("governanceSummary").innerHTML = `${escapeHtml(result.report?.summary?.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_report")}</a>`;
  } catch (error) {
    el("governanceSummary").textContent = `${translate("status.failed")} · ${error.message}`;
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
    el("readinessStatus").textContent = `${translate("status.failed")} · ${error.message}`;
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
    el("readinessStatus").innerHTML = `${escapeHtml(result.report?.summary?.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_readiness")}</a>`;
  } catch (error) {
    el("readinessStatus").textContent = `${translate("status.export_failed")} · ${error.message}`;
  } finally {
    setBusy("exportReadinessBtn", false);
  }
}

async function exportRelease() {
  setBusy("exportReleaseBtn", true);
  try {
    const result = await api("/reports/release/export", { method: "POST", body: selectedGroupsBody() });
    const readiness = result.manifest?.reports?.readiness || "readiness";
    el("governanceSummary").innerHTML = `${translate("status.release_bundle")} · ${escapeHtml(readiness)} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_release")}</a>`;
    await refreshAll();
  } catch (error) {
    el("governanceSummary").textContent = `${translate("status.release_export_failed")} · ${error.message}`;
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
    el("governanceSummary").textContent = `${translate("status.evaluation")} ${summary.status || translate("status.unknown")} · ${summary.total_questions || 0} ${translate("status.questions")} · ${translate("status.score")} ${summary.score ?? 0}`;
    await refreshAll();
  } catch (error) {
    el("governanceSummary").textContent = `${translate("status.evaluation")} ${translate("status.failed")} · ${error.message}`;
  } finally {
    setBusy("runEvaluationBtn", false);
  }
}

async function exportEvaluation() {
  setBusy("exportEvaluationBtn", true);
  try {
    const result = await api("/reports/evaluation/export", { method: "POST", body: selectedGroupsBody() });
    const summary = result.report?.summary || {};
    el("governanceSummary").innerHTML = `${translate("status.evaluation")} ${escapeHtml(summary.status || "ok")} · <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_evaluation")}</a>`;
  } catch (error) {
    el("governanceSummary").textContent = `${translate("status.evaluation")} ${translate("status.failed")} · ${error.message}`;
  } finally {
    setBusy("exportEvaluationBtn", false);
  }
}

async function generateSlides() {
  const topic = el("slidesTopic").value.trim() || el("questionInput").value.trim();
  if (!topic) return;
  setBusy("generateSlidesBtn", true);
  el("slidesStatus").textContent = translate("status.generating");
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
      el("slidesStatus").textContent = translate("status.blocked");
      return;
    }
    el("artifactOutput").innerHTML = `
      <div class="artifact-card">
        <strong>${escapeHtml(result.topic || "Presentation")}</strong>
        <span>${Number(result.slide_count || 0)} slides</span>
        <a href="${escapeHtml(result.download_url)}" target="_blank" rel="noreferrer">${translate("status.download_pptx")}</a>
      </div>
    `;
    el("slidesStatus").textContent = translate("status.complete");
    await refreshAll();
  } catch (error) {
    el("artifactOutput").innerHTML = `<div class="answer-status blocked">${escapeHtml(error.message)}</div>`;
    el("slidesStatus").textContent = translate("status.failed");
  } finally {
    setBusy("generateSlidesBtn", false);
  }
}

function setApiState(online, detail = "") {
  const node = el("apiState");
  node.classList.toggle("online", online);
  node.textContent = online ? translate("status.online") : (detail || translate("status.offline"));
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
  el("llmRuntimeMode")?.setAttribute("aria-label", translate("agents.runtime_mode"));
  el("llmRuntimeCommand")?.setAttribute("aria-label", translate("agents.runtime_command"));
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
el("wikiTreeSearch").addEventListener("input", () => {
  state.wikiTreeFilter = el("wikiTreeSearch").value || "";
  renderWikiPageList();
});
el("wikiTreeSearchClear").addEventListener("click", () => {
  state.wikiTreeFilter = "";
  el("wikiTreeSearch").value = "";
  renderWikiPageList();
});
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
el("refreshSourceDetailBtn").addEventListener("click", () => {
  loadSourceDetail(state.sourceDetailPath);
});
el("sourcePreviewChars").addEventListener("change", () => {
  if (state.sourceDetailPath) {
    loadSourceDetail(state.sourceDetailPath);
  }
});
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
  const testAgentBtn = event.target.closest("[data-test-agent]");
  if (testAgentBtn) {
    testLlmAgent(testAgentBtn);
    return;
  }
  const removeCategoryBtn = event.target.closest("[data-remove-category]");
  if (removeCategoryBtn) {
    removeCategoryMapping(removeCategoryBtn);
    return;
  }
  const sourceDetailBtn = event.target.closest("[data-source-detail]");
  if (sourceDetailBtn) {
    loadSourceDetail(sourceDetailBtn.dataset.sourceDetail || "");
    return;
  }
  const button = event.target.closest("[data-source-status]");
  if (!button) return;
  setSourceStatus(button.dataset.sourcePath, button.dataset.sourceStatus, button);
});
el("saveTokenBtn").addEventListener("click", () => {
  localStorage.setItem(URL_TOKEN_KEY, el("tokenInput").value.trim());
  refreshAll();
});
el("questionInput").addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    askQuestion();
  }
});

el("tokenInput").value = localStorage.getItem(URL_TOKEN_KEY) || "";
setLanguage(currentLanguage);
renderPage();
refreshAll();
