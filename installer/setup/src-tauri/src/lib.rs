//! Mizan Setup.
//!
//! - No arguments: the guided installer window.
//! - `--app`: the installed Mizan desktop app (a window onto the local server).
//! - `install …` / other mizan-server commands: headless, for scripts and servers.
//! - `--elevated-install <options> <progress>`: Windows, the elevated half of an install.

mod embedded;
mod install;
mod licence;
mod platform;

// A release build must embed its screens (feature custom-protocol): without it Tauri loads the
// dev server (devUrl, http://localhost:5180) and the window shows "Could not connect to localhost".
#[cfg(all(dev, not(debug_assertions)))]
compile_error!("release build without the custom-protocol feature: build with `--features custom-protocol`");

use serde::Serialize;
use serde_json::{json, Value};
use std::path::PathBuf;
use std::time::Duration;
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

#[derive(Serialize)]
struct SetupInfo {
    version: String,
    platform: &'static str,
    is_admin: bool,
    install_dir: String,
    found: Option<licence::Found>,
    licence: Option<Value>,
    installed: Option<Value>,
    has_payload: bool,
}

#[tauri::command]
fn setup_info() -> SetupInfo {
    let emb = embedded::read_self().ok();
    let found = emb.as_ref().and_then(|e| licence::find(e.stamp.as_deref(), &e.exe));
    SetupInfo {
        version: env!("CARGO_PKG_VERSION").into(),
        platform: if cfg!(windows) { "windows" } else { "linux" },
        is_admin: platform::is_admin(),
        install_dir: install::default_install_dir().display().to_string(),
        licence: found.as_ref().and_then(|f| licence::peek(&f.key)),
        found,
        installed: platform::installed_config(),
        has_payload: emb.map(|e| e.payload.is_some()).unwrap_or(false) || std::env::var("MIZAN_PAYLOAD_DIR").is_ok(),
    }
}

#[tauri::command]
fn read_licence(text: Option<String>, path: Option<String>) -> Result<Value, String> {
    let key = match (text, path) {
        (Some(t), _) => licence::extract_key(&t),
        (_, Some(p)) => licence::read_file(&p),
        _ => None,
    }
    .ok_or("هذا ليس مفتاح ترخيص ميزان. انسخه من لوحة المالك (زر «تنزيل»).")?;
    let payload = licence::peek(&key).ok_or("تعذرت قراءة مفتاح الترخيص.")?;
    Ok(json!({"key": key, "licence": payload}))
}

#[tauri::command]
async fn run_install(window: tauri::Window, options: install::Options) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let emit = |v: Value| {
            let _ = window.emit("install-progress", v);
        };
        let dir = PathBuf::from(&options.install_dir);
        #[cfg(windows)]
        if install::needs_elevation(&dir) {
            return install::run_elevated(&options, emit);
        }
        let _ = &dir;
        let emb = embedded::read_self().map_err(|e| e.to_string())?;
        install::run(&emb, &options, emit)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn open_mizan(app: tauri::AppHandle, url: String, desktop: bool) -> Result<(), String> {
    if desktop {
        open_app_window(&app, &url).map_err(|e| e.to_string())
    } else {
        open::that(&url).map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    open::that(path).map_err(|e| e.to_string())
}

fn open_app_window(app: &tauri::AppHandle, url: &str) -> tauri::Result<()> {
    if let Some(w) = app.get_webview_window("app") {
        w.set_focus()?;
        return Ok(());
    }
    WebviewWindowBuilder::new(app, "app", WebviewUrl::External(url.parse().expect("local url")))
        .title("ميزان")
        .inner_size(1360.0, 860.0)
        .min_inner_size(1024.0, 680.0)
        .maximized(true)
        .build()?;
    Ok(())
}

fn wait_for(url: &str, timeout: Duration) -> bool {
    let addr = url.trim_start_matches("http://").trim_start_matches("https://").to_string();
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if let Ok(mut addrs) = std::net::ToSocketAddrs::to_socket_addrs(&addr) {
            if let Some(a) = addrs.next() {
                if std::net::TcpStream::connect_timeout(&a, Duration::from_millis(500)).is_ok() {
                    return true;
                }
            }
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    false
}

/// Headless use: unpack if needed and hand over to mizan-server.
fn headless(args: &[String]) -> i32 {
    platform::attach_console();
    let emb = match embedded::read_self() {
        Ok(e) => e,
        Err(e) => {
            eprintln!("{e}");
            return 2;
        }
    };
    let dir = std::env::var("MIZAN_INSTALL_DIR").map(PathBuf::from).unwrap_or_else(|_| install::default_install_dir());
    if args.first().map(String::as_str) == Some("install") {
        println!("Unpacking Mizan to {} …", dir.display());
        if let Err(e) = embedded::extract(&emb, &dir, |_, _| {}) {
            eprintln!("✘ {e}");
            return 1;
        }
    }
    let program = install::server_program(&dir);
    match std::process::Command::new(&program).args(args).status() {
        Ok(s) => s.code().unwrap_or(1),
        Err(e) => {
            eprintln!("✘ {}: {e}", program.display());
            1
        }
    }
}

const SERVER_COMMANDS: &[&str] = &["install", "status", "start", "stop", "restart", "licence", "backup", "backups", "restore", "update", "uninstall", "version"];

pub fn run() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() == 3 && args[0] == "--elevated-install" {
        std::process::exit(install::elevated_entry(&args[1], &args[2]));
    }
    if args.first().map(|a| SERVER_COMMANDS.contains(&a.as_str())).unwrap_or(false) {
        std::process::exit(headless(&args));
    }
    let app_mode = args.iter().any(|a| a == "--app");

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![setup_info, read_licence, run_install, open_mizan, open_path])
        .setup(move |app| {
            if app_mode {
                let url = platform::installed_config()
                    .and_then(|c| platform::local_url(&c))
                    .unwrap_or_else(|| "http://127.0.0.1:47800".into());
                if !wait_for(&url, Duration::from_secs(45)) {
                    // Not running: show the setup window's "not running" screen.
                    WebviewWindowBuilder::new(app, "setup", WebviewUrl::App("index.html#/not-running".into()))
                        .title("ميزان").inner_size(560.0, 380.0).resizable(false).center().build()?;
                    return Ok(());
                }
                open_app_window(app.handle(), &url)?;
                return Ok(());
            }
            WebviewWindowBuilder::new(app, "setup", WebviewUrl::App("index.html".into()))
                .title("Mizan Setup — تثبيت ميزان")
                .inner_size(920.0, 640.0)
                .resizable(false)
                .center()
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Mizan Setup");
}
