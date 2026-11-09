//! The install job: unpack the payload, run `mizan-server install --json`, then
//! (single device) put the Mizan app and its shortcuts in place.
//!
//! The wizard runs it in-process, or, on Windows when administrator rights are
//! needed, in an elevated copy of this program that writes progress to a file
//! the wizard follows.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::embedded::{self, Embedded};

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Options {
    pub licence: String,
    pub admin_password: String,
    pub admin_username: Option<String>,
    pub install_dir: String,
    pub port: Option<u16>,
    pub demo: bool,
    /// Development/testing only (hidden in the wizard).
    #[serde(default)]
    pub extra_args: Vec<String>,
}

pub fn server_program(install_dir: &Path) -> PathBuf {
    install_dir.join("server").join(if cfg!(windows) { "mizan-server.exe" } else { "mizan-server" })
}

pub fn app_program(install_dir: &Path) -> PathBuf {
    install_dir.join(if cfg!(windows) { "Mizan.exe" } else { "mizan-app" })
}

pub fn default_install_dir() -> PathBuf {
    if cfg!(windows) {
        PathBuf::from(std::env::var("ProgramFiles").unwrap_or_else(|_| r"C:\Program Files".into())).join("Mizan")
    } else {
        dirs::home_dir().unwrap_or_default().join(".local").join("opt").join("mizan")
    }
}

#[cfg_attr(not(windows), allow(dead_code))]
pub fn needs_elevation(install_dir: &Path) -> bool {
    if !cfg!(windows) || crate::platform::is_admin() {
        return false;
    }
    // Writable without administrator rights? (e.g. a folder in the user's profile)
    let probe = install_dir.join(".mizan-write-test");
    let ok = fs::create_dir_all(install_dir).and_then(|_| fs::write(&probe, b"")).is_ok();
    let _ = fs::remove_file(&probe);
    !ok
}

/// Run the whole job, sending each progress event (JSON) to `emit`.
pub fn run(emb: &Embedded, opts: &Options, mut emit: impl FnMut(Value)) -> Result<Value, String> {
    let dir = PathBuf::from(&opts.install_dir);

    // 1. Unpack
    emit(json!({"step": "extract", "status": "running"}));
    embedded::extract(emb, &dir, |done, total| {
        emit(json!({"step": "extract", "status": "progress", "done": done, "total": total}));
    })?;
    emit(json!({"step": "extract", "status": "done"}));

    // 2. The engine
    let mut args: Vec<String> = vec![
        "install".into(), "--json".into(),
        "--licence".into(), opts.licence.clone(),
    ];
    if let Some(u) = &opts.admin_username {
        if !u.trim().is_empty() {
            args.extend(["--admin-username".into(), u.trim().to_string()]);
        }
    }
    if let Some(p) = opts.port {
        args.extend(["--port".into(), p.to_string()]);
    }
    if opts.demo {
        args.push("--demo".into());
    }
    args.extend(opts.extra_args.iter().cloned());
    // Development/testing only: e.g. "--app-env development --cloud-url http://localhost:8003".
    if let Ok(extra) = std::env::var("MIZAN_SETUP_EXTRA_ARGS") {
        args.extend(extra.split_whitespace().map(String::from));
    }

    let mut cmd = Command::new(server_program(&dir));
    cmd.args(&args)
        .env("MIZAN_ADMIN_PASSWORD", &opts.admin_password) // not on the command line
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = cmd.spawn().map_err(|e| format!("Couldn't start the installer engine: {e}"))?;
    let stdout = child.stdout.take().unwrap();
    let mut summary = Value::Null;
    let mut last_error: Option<String> = None;
    for line in BufReader::new(stdout).lines().map_while(Result::ok) {
        let Ok(event) = serde_json::from_str::<Value>(&line) else { continue };
        if event["status"] == "error" {
            last_error = event["message"].as_str().map(String::from);
        }
        if event["step"] == "done" {
            summary = event.clone();
        }
        emit(event);
    }
    let stderr = child.stderr.take().map(|s| BufReader::new(s).lines().map_while(Result::ok).collect::<Vec<_>>().join("\n"));
    let status = child.wait().map_err(|e| e.to_string())?;
    if !status.success() {
        return Err(last_error.or(stderr.filter(|s| !s.is_empty())).unwrap_or_else(|| "The installation failed.".into()));
    }

    // 3. Single device: the Mizan app and its shortcuts
    if summary["mode"] == "desktop" {
        emit(json!({"step": "shortcuts", "status": "running"}));
        let app = app_program(&dir);
        embedded::write_program(emb, &app).map_err(|e| format!("Couldn't install the Mizan app: {e}"))?;
        crate::platform::create_shortcuts(&app);
        emit(json!({"step": "shortcuts", "status": "done"}));
    }
    Ok(summary)
}

/// Windows: run the job in an elevated copy of this program, following its progress file.
#[cfg(windows)]
pub fn run_elevated(opts: &Options, mut emit: impl FnMut(Value)) -> Result<Value, String> {
    use std::io::{Seek, SeekFrom};
    use std::time::Duration;

    let tmp = std::env::temp_dir().join(format!("mizan-setup-{}", std::process::id()));
    fs::create_dir_all(&tmp).map_err(|e| e.to_string())?;
    let opts_file = tmp.join("options.json");
    let progress_file = tmp.join("progress.jsonl");
    fs::write(&opts_file, serde_json::to_vec(opts).unwrap()).map_err(|e| e.to_string())?;
    fs::write(&progress_file, b"").map_err(|e| e.to_string())?;

    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let handle = crate::platform::spawn_elevated(&exe, &["--elevated-install", &opts_file.display().to_string(), &progress_file.display().to_string()])?;

    let mut pos = 0u64;
    let mut summary = Value::Null;
    let mut error: Option<String> = None;
    loop {
        let finished = crate::platform::wait_process(handle, 400);
        if let Ok(mut f) = fs::File::open(&progress_file) {
            let _ = f.seek(SeekFrom::Start(pos));
            let mut reader = BufReader::new(f);
            let mut line = String::new();
            while reader.read_line(&mut line).unwrap_or(0) > 0 {
                if !line.ends_with('\n') {
                    break; // a partial line: read it next time
                }
                pos += line.len() as u64;
                if let Ok(event) = serde_json::from_str::<Value>(line.trim()) {
                    if event["step"] == "done" {
                        summary = event.clone();
                    }
                    if event["status"] == "error" {
                        error = event["message"].as_str().map(String::from);
                    }
                    if event["step"] != "result" {
                        emit(event);
                    }
                }
                line.clear();
            }
        }
        if let Some(code) = finished {
            let _ = fs::remove_file(&opts_file);
            return if code == 0 { Ok(summary) } else { Err(error.unwrap_or_else(|| "The installation failed.".into())) };
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

/// The elevated side: run the job, writing progress lines to a file.
pub fn elevated_entry(opts_file: &str, progress_file: &str) -> i32 {
    use std::io::Write;
    let Ok(raw) = fs::read(opts_file) else { return 2 };
    let Ok(opts) = serde_json::from_slice::<Options>(&raw) else { return 2 };
    let Ok(emb) = embedded::read_self() else { return 2 };
    let mut out = fs::OpenOptions::new().append(true).open(progress_file).ok();
    let mut write = |v: Value| {
        if let Some(f) = out.as_mut() {
            let _ = writeln!(f, "{v}");
            let _ = f.flush();
        }
    };
    match run(&emb, &opts, &mut write) {
        Ok(_) => 0,
        Err(e) => {
            write(json!({"step": "install", "status": "error", "message": e}));
            1
        }
    }
}
