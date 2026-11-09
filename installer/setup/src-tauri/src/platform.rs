//! Platform specifics: administrator rights, elevation, consoles, shortcuts and
//! finding an installed Mizan.

use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

#[cfg(not(windows))]
const ICON_PNG: &[u8] = include_bytes!("../icons/128x128.png");

#[cfg(windows)]
pub fn is_admin() -> bool {
    unsafe { windows_sys::Win32::UI::Shell::IsUserAnAdmin() != 0 }
}

#[cfg(not(windows))]
pub fn is_admin() -> bool {
    // SAFETY: geteuid has no preconditions.
    unsafe { libc_geteuid() == 0 }
}

#[cfg(not(windows))]
extern "C" {
    #[link_name = "geteuid"]
    fn libc_geteuid() -> u32;
}

/// Command-line use on Windows: write to the console we were started from.
pub fn attach_console() {
    #[cfg(windows)]
    unsafe {
        windows_sys::Win32::System::Console::AttachConsole(windows_sys::Win32::System::Console::ATTACH_PARENT_PROCESS);
    }
}

#[cfg(windows)]
fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Start this program elevated (UAC prompt); returns the process handle.
#[cfg(windows)]
pub fn spawn_elevated(exe: &Path, args: &[&str]) -> Result<isize, String> {
    use windows_sys::Win32::UI::Shell::{ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW};
    let quoted: Vec<String> = args.iter().map(|a| format!("\"{a}\"")).collect();
    let (verb, file, params) = (wide("runas"), wide(&exe.display().to_string()), wide(&quoted.join(" ")));
    let mut info: SHELLEXECUTEINFOW = unsafe { std::mem::zeroed() };
    info.cbSize = std::mem::size_of::<SHELLEXECUTEINFOW>() as u32;
    info.fMask = SEE_MASK_NOCLOSEPROCESS;
    info.lpVerb = verb.as_ptr();
    info.lpFile = file.as_ptr();
    info.lpParameters = params.as_ptr();
    info.nShow = 0; // SW_HIDE
    let ok = unsafe { ShellExecuteExW(&mut info) };
    if ok == 0 || info.hProcess.is_null() {
        return Err("Administrator permission is needed to install Mizan here.".into());
    }
    Ok(info.hProcess as isize)
}

/// Wait up to `ms`; Some(exit code) once the process has finished.
#[cfg(windows)]
pub fn wait_process(handle: isize, ms: u32) -> Option<i32> {
    use windows_sys::Win32::System::Threading::{GetExitCodeProcess, WaitForSingleObject};
    let h = handle as windows_sys::Win32::Foundation::HANDLE;
    if unsafe { WaitForSingleObject(h, ms) } != 0 {
        return None;
    }
    let mut code: u32 = 1;
    unsafe { GetExitCodeProcess(h, &mut code) };
    Some(code as i32)
}

pub fn create_shortcuts(app: &Path) {
    #[cfg(windows)]
    {
        // Public desktop and Start menu (we're elevated when installing to Program Files).
        let public = std::env::var("PUBLIC").unwrap_or_else(|_| r"C:\Users\Public".into());
        let programs = std::env::var("ProgramData").map(|p| format!(r"{p}\Microsoft\Windows\Start Menu\Programs")).unwrap_or_default();
        for dir in [format!(r"{public}\Desktop"), programs] {
            if dir.is_empty() {
                continue;
            }
            let lnk = format!(r"{dir}\Mizan.lnk");
            let script = format!(
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{t}';$s.Arguments='--app';$s.IconLocation='{t},0';$s.Description='Mizan';$s.Save()",
                t = app.display()
            );
            use std::os::windows::process::CommandExt;
            let _ = std::process::Command::new("powershell")
                .args(["-NoProfile", "-NonInteractive", "-Command", &script])
                .creation_flags(0x0800_0000)
                .status();
        }
    }
    #[cfg(not(windows))]
    {
        let icon = app.with_file_name("mizan.png");
        let _ = fs::write(&icon, ICON_PNG);
        let entry = format!(
            "[Desktop Entry]\nType=Application\nName=Mizan\nName[ar]=ميزان\nComment=Mizan ERP\nExec=\"{}\" --app\nIcon={}\nTerminal=false\nCategories=Office;Finance;\n",
            app.display(),
            icon.display()
        );
        if let Some(apps) = dirs::data_dir().map(|d| d.join("applications")) {
            let _ = fs::create_dir_all(&apps);
            let _ = fs::write(apps.join("mizan.desktop"), &entry);
        }
        if let Some(desktop) = dirs::desktop_dir() {
            let path = desktop.join("mizan.desktop");
            if fs::write(&path, &entry).is_ok() {
                use std::os::unix::fs::PermissionsExt;
                let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o755));
            }
        }
    }
}

/// An installed Mizan's configuration (config.json), wherever it was installed.
pub fn installed_config() -> Option<Value> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(p) = std::env::var("MIZAN_CONFIG") {
        candidates.push(PathBuf::from(p));
    }
    if let Ok(home) = std::env::var("MIZAN_HOME") {
        candidates.push(PathBuf::from(home).join("config.json"));
    }
    if cfg!(windows) {
        let pd = std::env::var("ProgramData").unwrap_or_else(|_| r"C:\ProgramData".into());
        candidates.push(PathBuf::from(pd).join("Mizan").join("config.json"));
    } else {
        if let Some(d) = dirs::data_dir() {
            candidates.push(d.join("mizan").join("config.json"));
        }
        candidates.push(PathBuf::from("/var/lib/mizan/config.json"));
    }
    candidates.into_iter().find_map(|p| fs::read(&p).ok()).and_then(|raw| serde_json::from_slice(&raw).ok())
}

/// The local address the Mizan app window opens.
pub fn local_url(cfg: &Value) -> Option<String> {
    let port = cfg["http_port"].as_u64()?;
    let scheme = if cfg["tls"].as_bool().unwrap_or(false) { "https" } else { "http" };
    Some(format!("{scheme}://127.0.0.1:{port}"))
}
