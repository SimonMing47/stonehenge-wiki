use std::env;
use std::ffi::OsString;
use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Copy)]
pub enum CliPlatform {
    Linux,
    Windows,
}

pub fn run(platform: CliPlatform) -> ! {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    match run_with_platform(platform, &args) {
        Ok(code) => std::process::exit(code),
        Err(err) => {
            eprintln!("{}", err);
            std::process::exit(2);
        }
    }
}

fn run_with_platform(platform: CliPlatform, args: &[OsString]) -> Result<i32, String> {
    let main_py = locate_main_py()?;
    let candidates = python_candidates(platform);
    let mut last_error: Option<io::Error> = None;

    for py in &candidates {
        match Command::new(&py)
            .arg(&main_py)
            .args(args)
            .status()
        {
            Ok(status) => return Ok(status.code().unwrap_or(1)),
            Err(err) if err.kind() == io::ErrorKind::NotFound => {
                last_error = Some(err);
                continue;
            }
            Err(err) => {
                return Err(format!(
                    "failed to execute CLI bridge with '{}': {}",
                    py,
                    err
                ));
            }
        }
    }

    Err(format!(
        "python executable not found. Tried: {}. last error: {}",
        candidates
            .iter()
            .map(|p| p.to_string_lossy())
            .collect::<Vec<_>>()
            .join(", "),
        last_error
            .map(|e| e.to_string())
            .unwrap_or_else(|| "NotFound".to_string())
    ))
}

fn python_candidates(platform: CliPlatform) -> Vec<OsString> {
    let mut candidates: Vec<OsString> = Vec::new();
    if let Ok(explicit) = env::var_os("LLM_WIKI_PYTHON") {
        if !explicit.is_empty() {
            candidates.push(explicit);
        }
    }

    match platform {
        CliPlatform::Windows => candidates.extend(["python", "python3"].iter().map(OsString::from)),
        CliPlatform::Linux => candidates.extend(["python3", "python"].iter().map(OsString::from)),
    }
    candidates
}

fn locate_main_py() -> Result<PathBuf, String> {
    if let Ok(explicit) = env::var_os("LLM_WIKI_MAIN_PY") {
        let explicit_path = PathBuf::from(explicit);
        if explicit_path.is_file() {
            return Ok(explicit_path);
        }
    }

    if let Ok(wiki_root) = env::var_os("LLM_WIKI_ROOT") {
        let candidate = Path::new(&wiki_root).join("work").join("main.py");
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    let mut candidates = Vec::new();
    if let Ok(cwd) = env::current_dir() {
        candidates.push(cwd.join("work").join("main.py"));
    }

    if let Ok(exe) = env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            candidates.push(exe_dir.join("work").join("main.py"));
            candidates.push(exe_dir.join("..").join("work").join("main.py"));
            candidates.push(exe_dir.join("..").join("..").join("work").join("main.py"));
        }
    }

    for candidate in candidates {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    Err(
        "无法定位 work/main.py。请设置 LLM_WIKI_MAIN_PY=... 或 LLM_WIKI_ROOT=..."
            .to_string(),
    )
}
