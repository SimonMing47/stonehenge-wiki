use std::env;
use std::ffi::OsString;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

const DEFAULT_URL: &str = "http://127.0.0.1:8765";
const TOKEN_HEADER: &str = "X-STONEHENGE-WIKI-TOKEN";
const CLI_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Clone, Copy)]
pub enum CliPlatform {
    Auto,
    Linux,
    Windows,
}

#[derive(Debug)]
struct CliConfig {
    base_url: String,
    token: Option<String>,
    action: Action,
}

#[derive(Debug)]
enum Action {
    Get { path: String },
    Post { path: String, body: String },
    Help,
    Version,
}

#[derive(Debug)]
struct HttpUrl {
    host: String,
    port: u16,
    path_prefix: String,
}

pub fn run(platform: CliPlatform) -> ! {
    let args: Vec<String> = env::args_os().skip(1).map(os_string_to_string).collect();
    match run_client(platform, &args) {
        Ok(code) => std::process::exit(code),
        Err(err) => {
            eprintln!("{err}");
            std::process::exit(2);
        }
    }
}

fn run_client(platform: CliPlatform, args: &[String]) -> Result<i32, String> {
    let config = parse_args(args)?;
    match config.action {
        Action::Help => {
            print_help();
            Ok(0)
        }
        Action::Version => {
            print_version(platform);
            Ok(0)
        }
        Action::Get { path } => request(
            &config.base_url,
            config.token.as_deref(),
            "GET",
            &path,
            None,
        ),
        Action::Post { path, body } => request(
            &config.base_url,
            config.token.as_deref(),
            "POST",
            &path,
            Some(&body),
        ),
    }
}

fn parse_args(args: &[String]) -> Result<CliConfig, String> {
    let mut base_url = env::var("STONEHENGE_WIKI_URL").unwrap_or_else(|_| DEFAULT_URL.to_string());
    let mut token = env::var("STONEHENGE_WIKI_TOKEN")
        .ok()
        .filter(|value| !value.is_empty());
    let mut rest: Vec<String> = Vec::new();
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--url" => {
                index += 1;
                base_url = required_value(args, index, "--url")?.to_string();
            }
            "--token" => {
                index += 1;
                token = Some(required_value(args, index, "--token")?.to_string());
            }
            value => rest.push(value.to_string()),
        }
        index += 1;
    }

    let action = parse_action(&rest)?;
    Ok(CliConfig {
        base_url,
        token,
        action,
    })
}

fn parse_action(args: &[String]) -> Result<Action, String> {
    if args.iter().any(|arg| arg == "-h" || arg == "--help") {
        return Ok(Action::Help);
    }
    if args.iter().any(|arg| arg == "-v" || arg == "--version") {
        return Ok(Action::Version);
    }
    if args.iter().any(|arg| arg == "--serve") {
        return Err("stonehenge-wiki CLI is REST-only. Start the Stonehenge Wiki API service separately, then call this CLI with --url.".to_string());
    }
    if args.is_empty() {
        return Ok(Action::Post {
            path: "/groups/run".to_string(),
            body: "{}".to_string(),
        });
    }

    let mut question_id = "api-1".to_string();
    let mut level = "".to_string();
    let mut groups: Vec<String> = Vec::new();
    let mut limit = "50".to_string();
    let mut include_missing = false;
    let mut title = "".to_string();
    let mut category = "00_inbox".to_string();
    let mut status = "".to_string();
    let mut reason = "".to_string();
    let mut actor = "cli".to_string();
    let mut include_evaluation = false;
    let mut llm_test_agent: Option<String> = None;
    let mut llm_test_live = false;
    let mut ask_question: Option<String> = None;
    let mut explain_question: Option<String> = None;
    let mut import_source: Option<String> = None;
    let mut source_status_path: Option<String> = None;
    let mut deck_topic: Option<String> = None;
    let mut slide_count = "6".to_string();
    let mut selected: Option<Action> = None;

    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--health" => selected = Some(get("/health")),
            "--api-contract" => selected = Some(get("/api/contract")),
            "--dump-index" => selected = Some(get("/index")),
            "--list-sources" => selected = Some(get("/sources")),
            "--include-missing-sources" => include_missing = true,
            "--list-source-versions" => selected = Some(get("/sources/history")),
            "--source-history" => {
                index += 1;
                let value = required_value(args, index, "--source-history")?;
                selected = Some(get(&format!(
                    "/sources/history?path={}",
                    encode_query(value)
                )));
            }
            "--source-detail" => {
                index += 1;
                let value = required_value(args, index, "--source-detail")?;
                selected = Some(get(&format!(
                    "/sources/detail?path={}",
                    encode_query(value)
                )));
            }
            "--source-history-limit" | "--audit-limit" | "--wiki-section-limit" => {
                index += 1;
                limit = required_value(args, index, args[index - 1].as_str())?.to_string();
            }
            "--source-risk-report" => selected = Some(get("/sources/risk")),
            "--list-source-reviews" => selected = Some(get("/sources/reviews")),
            "--source-review-path" => {
                index += 1;
                let value = required_value(args, index, "--source-review-path")?;
                selected = Some(get(&format!(
                    "/sources/reviews?path={}",
                    encode_query(value)
                )));
            }
            "--list-wiki-sections" => selected = Some(get("/wiki/sections")),
            "--wiki-section-source" => {
                index += 1;
                let value = required_value(args, index, "--wiki-section-source")?;
                selected = Some(get(&format!(
                    "/wiki/sections?source_path={}",
                    encode_query(value)
                )));
            }
            "--search-wiki" => {
                index += 1;
                let value = required_value(args, index, "--search-wiki")?;
                selected = Some(get(&format!("/wiki/search?q={}", encode_query(value))));
            }
            "--lint-wiki" => selected = Some(get("/wiki/lint")),
            "--governance-report" => selected = Some(get("/reports/governance")),
            "--readiness-report" => selected = Some(get("/reports/readiness")),
            "--audit-log" => selected = Some(get("/audit")),
            "--test-llm-agent" => {
                index += 1;
                let value = required_value(args, index, "--test-llm-agent")?;
                llm_test_agent = Some(value.to_string());
            }
            "--test-llm-live" => llm_test_live = true,
            "--ask" => {
                index += 1;
                let value = required_value(args, index, "--ask")?;
                ask_question = Some(value.to_string());
            }
            "--explain-ask" => {
                index += 1;
                let value = required_value(args, index, "--explain-ask")?;
                explain_question = Some(value.to_string());
            }
            "--question-id" | "--id" => {
                index += 1;
                question_id = required_value(args, index, args[index - 1].as_str())?.to_string();
            }
            "--level" => {
                index += 1;
                level = required_value(args, index, "--level")?.to_string();
            }
            "--reindex" => selected = Some(post("/reindex", "{}")),
            "--compile-wiki" => selected = Some(post("/wiki/compile", "{}")),
            "--import-source" => {
                index += 1;
                let source = required_value(args, index, "--import-source")?;
                import_source = Some(source.to_string());
            }
            "--import-title" => {
                index += 1;
                title = required_value(args, index, "--import-title")?.to_string();
            }
            "--import-category" => {
                index += 1;
                category = required_value(args, index, "--import-category")?.to_string();
            }
            "--set-source-status" => {
                index += 1;
                let path = required_value(args, index, "--set-source-status")?;
                source_status_path = Some(path.to_string());
            }
            "--source-status" => {
                index += 1;
                status = required_value(args, index, "--source-status")?.to_string();
            }
            "--source-status-reason" => {
                index += 1;
                reason = required_value(args, index, "--source-status-reason")?.to_string();
            }
            "--source-status-actor" => {
                index += 1;
                actor = required_value(args, index, "--source-status-actor")?.to_string();
            }
            "--generate-ppt" | "--generate-brief" => {
                index += 1;
                let topic = required_value(args, index, args[index - 1].as_str())?;
                deck_topic = Some(topic.to_string());
            }
            "--slide-count" => {
                index += 1;
                let value = required_value(args, index, "--slide-count")?;
                slide_count = value.to_string();
            }
            "--group" => {
                index += 1;
                groups.push(required_value(args, index, "--group")?.to_string());
            }
            "--evaluation-report" => selected = Some(post("/reports/evaluation", "{}")),
            "--export-evaluation-report" => {
                selected = Some(post("/reports/evaluation/export", "{}"))
            }
            "--export-governance-report" => {
                selected = Some(post("/reports/governance/export", "{}"))
            }
            "--export-readiness-report" => selected = Some(post("/reports/readiness/export", "{}")),
            "--export-release-bundle" => selected = Some(post("/reports/release/export", "{}")),
            "--release-include-evaluation" => include_evaluation = true,
            unknown => {
                return Err(format!(
                    "unknown argument: {unknown}\n\nRun stonehenge-wiki --help for usage."
                ))
            }
        }
        index += 1;
    }

    let mut action = selected.unwrap_or_else(|| post("/groups/run", "{}"));
    if let Some(question) = ask_question {
        action = post(
            "/ask",
            &json_object(&[
                ("id", &question_id),
                ("title", &question),
                ("level", &level),
            ]),
        );
    }
    if let Some(question) = explain_question {
        action = post(
            "/explain",
            &json_object(&[
                ("id", &question_id),
                ("title", &question),
                ("level", &level),
            ]),
        );
    }
    if let Some(source) = import_source {
        action = post(
            "/sources/import",
            &json_object(&[
                ("source", &source),
                ("title", &title),
                ("category", &category),
            ]),
        );
    }
    if let Some(path) = source_status_path {
        action = post(
            "/sources/status",
            &json_object(&[
                ("path", &path),
                ("status", &status),
                ("reason", &reason),
                ("actor", &actor),
            ]),
        );
    }
    if let Some(topic) = deck_topic {
        action = post(
            "/slides/generate",
            &format!(
                r#"{{"topic":{},"slide_count":{}}}"#,
                json_string(&topic),
                slide_count
            ),
        );
    }
    if let Some(agent) = llm_test_agent {
        action = post(
            "/llm/test",
            &format!(
                r#"{{"agent_name":{},"live":{}}}"#,
                json_string(&agent),
                llm_test_live
            ),
        );
    }
    action = with_common_query(action, &limit, include_missing);
    if !groups.is_empty() {
        action = with_groups(action, &groups, include_evaluation);
    } else if include_evaluation {
        action = with_include_evaluation(action);
    }
    Ok(action)
}

fn with_common_query(action: Action, limit: &str, include_missing: bool) -> Action {
    match action {
        Action::Get { mut path } => {
            if path.starts_with("/audit") {
                path = append_query(&path, "limit", limit);
            }
            if path.starts_with("/wiki/sections") || path.starts_with("/wiki/search") {
                path = append_query(&path, "limit", limit);
            }
            if path.starts_with("/sources/history") || path.starts_with("/sources/reviews") {
                path = append_query(&path, "limit", limit);
            }
            if include_missing && path.starts_with("/sources") && !path.starts_with("/sources/") {
                path = append_query(&path, "include_missing", "1");
            }
            Action::Get { path }
        }
        other => other,
    }
}

fn with_groups(action: Action, groups: &[String], include_evaluation: bool) -> Action {
    match action {
        Action::Get { path } if path == "/reports/readiness" => Action::Get {
            path: append_query(&path, "groups", &groups.join(",")),
        },
        Action::Post { path, .. } if path.starts_with("/reports/") || path == "/groups/run" => {
            let mut entries = vec![format!(r#""groups":{}"#, json_array(groups))];
            if path == "/reports/release/export" {
                entries.push(format!(r#""include_evaluation":{}"#, include_evaluation));
            }
            Action::Post {
                path,
                body: format!("{{{}}}", entries.join(",")),
            }
        }
        other => other,
    }
}

fn with_include_evaluation(action: Action) -> Action {
    match action {
        Action::Post { path, .. } if path == "/reports/release/export" => Action::Post {
            path,
            body: r#"{"include_evaluation":true}"#.to_string(),
        },
        other => other,
    }
}

fn request(
    base_url: &str,
    token: Option<&str>,
    method: &str,
    path: &str,
    body: Option<&str>,
) -> Result<i32, String> {
    let url = parse_http_url(base_url)?;
    let full_path = join_path(&url.path_prefix, path);
    let body_bytes = body.unwrap_or("").as_bytes();
    let mut stream = TcpStream::connect((url.host.as_str(), url.port))
        .map_err(|err| format!("failed to connect to {base_url}: {err}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(120)))
        .map_err(|err| format!("failed to set read timeout: {err}"))?;
    stream
        .set_write_timeout(Some(Duration::from_secs(30)))
        .map_err(|err| format!("failed to set write timeout: {err}"))?;

    let mut headers = format!(
        "{method} {full_path} HTTP/1.1\r\nHost: {}\r\nAccept: application/json\r\nConnection: close\r\n",
        url.host
    );
    if let Some(token) = token {
        headers.push_str(&format!("{TOKEN_HEADER}: {token}\r\n"));
    }
    if body.is_some() {
        headers.push_str("Content-Type: application/json; charset=utf-8\r\n");
        headers.push_str(&format!("Content-Length: {}\r\n", body_bytes.len()));
    }
    headers.push_str("\r\n");

    stream
        .write_all(headers.as_bytes())
        .and_then(|_| stream.write_all(body_bytes))
        .map_err(|err| format!("failed to write request: {err}"))?;

    let mut raw = Vec::new();
    stream
        .read_to_end(&mut raw)
        .map_err(|err| format!("failed to read response: {err}"))?;
    let response = String::from_utf8_lossy(&raw);
    let (head, payload) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "invalid HTTP response".to_string())?;
    let status = parse_status(head)?;
    print!("{}", decode_body(head, payload));
    if !payload.ends_with('\n') {
        println!();
    }
    Ok(if (200..300).contains(&status) { 0 } else { 1 })
}

fn parse_http_url(raw: &str) -> Result<HttpUrl, String> {
    let rest = raw.strip_prefix("http://").ok_or_else(|| {
        "stonehenge-wiki CLI currently supports http:// REST endpoints".to_string()
    })?;
    let (authority, path_prefix) = rest.split_once('/').unwrap_or((rest, ""));
    let (host, port) = if let Some((host, port)) = authority.rsplit_once(':') {
        (
            host.to_string(),
            port.parse::<u16>()
                .map_err(|_| format!("invalid port in URL: {raw}"))?,
        )
    } else {
        (authority.to_string(), 80)
    };
    if host.is_empty() {
        return Err(format!("invalid URL: {raw}"));
    }
    Ok(HttpUrl {
        host,
        port,
        path_prefix: format!("/{}", path_prefix.trim_matches('/')),
    })
}

fn parse_status(head: &str) -> Result<u16, String> {
    let status = head
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .ok_or_else(|| "invalid HTTP status line".to_string())?;
    status
        .parse::<u16>()
        .map_err(|_| format!("invalid HTTP status code: {status}"))
}

fn decode_body(head: &str, body: &str) -> String {
    if !head
        .to_ascii_lowercase()
        .contains("transfer-encoding: chunked")
    {
        return body.to_string();
    }
    let mut output = String::new();
    let mut rest = body;
    while let Some((size_hex, after_size)) = rest.split_once("\r\n") {
        let size = usize::from_str_radix(size_hex.trim(), 16).unwrap_or(0);
        if size == 0 || after_size.len() < size {
            break;
        }
        output.push_str(&after_size[..size]);
        rest = after_size.get(size + 2..).unwrap_or("");
    }
    output
}

fn join_path(prefix: &str, path: &str) -> String {
    let prefix = prefix.trim_end_matches('/');
    if prefix.is_empty() {
        path.to_string()
    } else if path == "/" {
        prefix.to_string()
    } else {
        format!("{prefix}/{path}", path = path.trim_start_matches('/'))
    }
}

fn required_value<'a>(args: &'a [String], index: usize, flag: &str) -> Result<&'a str, String> {
    args.get(index)
        .map(String::as_str)
        .ok_or_else(|| format!("missing value for {flag}"))
}

fn get(path: &str) -> Action {
    Action::Get {
        path: path.to_string(),
    }
}

fn post(path: &str, body: &str) -> Action {
    Action::Post {
        path: path.to_string(),
        body: body.to_string(),
    }
}

fn append_query(path: &str, key: &str, value: &str) -> String {
    let sep = if path.contains('?') { '&' } else { '?' };
    format!("{path}{sep}{key}={}", encode_query(value))
}

fn json_object(entries: &[(&str, &str)]) -> String {
    let pairs = entries
        .iter()
        .map(|(key, value)| format!(r#""{key}":{}"#, json_string(value)))
        .collect::<Vec<_>>();
    format!("{{{}}}", pairs.join(","))
}

fn json_array(values: &[String]) -> String {
    let items = values
        .iter()
        .map(|value| json_string(value))
        .collect::<Vec<_>>();
    format!("[{}]", items.join(","))
}

fn json_string(value: &str) -> String {
    let mut out = String::from("\"");
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn encode_query(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char)
            }
            b' ' => out.push_str("%20"),
            other => out.push_str(&format!("%{other:02X}")),
        }
    }
    out
}

fn os_string_to_string(value: OsString) -> String {
    value.to_string_lossy().to_string()
}

fn print_help() {
    println!(
        r#"stonehenge-wiki REST API CLI

  Usage:
  stonehenge-wiki [--url http://127.0.0.1:8765] [--token TOKEN] <command flags>

Connection:
  --url URL                 Stonehenge Wiki REST API base URL (env: STONEHENGE_WIKI_URL)
  --token TOKEN             API token (env: STONEHENGE_WIKI_TOKEN)
  -v, --version             Show CLI version.

Read commands:
  --health
  --api-contract
  --dump-index
  --list-sources [--include-missing-sources]
  --source-detail PATH
  --list-source-versions [--source-history PATH] [--source-history-limit N]
  --source-risk-report
  --list-source-reviews [--source-review-path PATH]
  --audit-log [--audit-limit N]
  --list-wiki-sections [--wiki-section-source PATH] [--wiki-section-limit N]
  --search-wiki QUERY [--wiki-section-limit N]
  --lint-wiki
  --governance-report
  --readiness-report [--group GROUP]

Write commands:
  --ask QUESTION [--id ID] [--level LEVEL]
  --explain-ask QUESTION [--id ID] [--level LEVEL]
  --test-llm-agent AGENT [--test-llm-live]
  --reindex
  --import-source PATH_OR_URL [--import-title TITLE] [--import-category CATEGORY]
  --set-source-status PATH --source-status active|quarantined [--source-status-reason REASON]
  --compile-wiki
  --group GROUP
  --generate-brief TOPIC [--slide-count N]  (alias: --generate-ppt)
  --evaluation-report [--group GROUP]
  --export-evaluation-report [--group GROUP]
  --export-governance-report
  --export-readiness-report [--group GROUP]
  --export-release-bundle [--group GROUP] [--release-include-evaluation]

The CLI only calls the REST API. It does not start the REST service or execute local project code.
"#
    );
}

fn print_version(platform: CliPlatform) {
    let platform_name = match platform {
        CliPlatform::Auto => "auto",
        CliPlatform::Linux => "linux",
        CliPlatform::Windows => "windows",
    };
    println!("stonehenge-wiki CLI {CLI_VERSION} ({platform_name})");
}
