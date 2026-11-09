//! Finding the client's licence without making them type it, and reading what
//! it says (for display only: the engine verifies the signature).

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

#[derive(Serialize, Clone)]
pub struct Found {
    pub key: String,
    /// stamp | file | downloads | clipboard
    pub source: String,
    pub file: Option<String>,
}

/// The first `MZN1.<payload>.<signature>` in some text.
pub fn extract_key(text: &str) -> Option<String> {
    let start = text.find("MZN1.")?;
    let key: String = text[start..]
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
        .collect();
    (key.split('.').count() == 3 && key.len() > 40).then_some(key)
}

pub fn peek(key: &str) -> Option<serde_json::Value> {
    let body = key.trim().split('.').nth(1)?;
    let raw = URL_SAFE_NO_PAD.decode(body.trim_end_matches('=')).ok()?;
    serde_json::from_slice(&raw).ok()
}

fn newest_mzn(dir: &Path, max_age: Option<Duration>) -> Option<PathBuf> {
    let mut best: Option<(SystemTime, PathBuf)> = None;
    for e in fs::read_dir(dir).ok()?.flatten() {
        let p = e.path();
        if p.extension().and_then(|x| x.to_str()).map(|x| x.eq_ignore_ascii_case("mzn")) != Some(true) {
            continue;
        }
        let Ok(modified) = e.metadata().and_then(|m| m.modified()) else { continue };
        if let Some(age) = max_age {
            if SystemTime::now().duration_since(modified).unwrap_or_default() > age {
                continue;
            }
        }
        if best.as_ref().map(|(t, _)| modified > *t).unwrap_or(true) {
            best = Some((modified, p));
        }
    }
    best.map(|(_, p)| p)
}

fn from_file(path: &Path, source: &str) -> Option<Found> {
    let text = fs::read_to_string(path).ok()?;
    extract_key(&text).map(|key| Found { key, source: source.into(), file: Some(path.display().to_string()) })
}

pub fn find(stamp: Option<&str>, exe: &Path) -> Option<Found> {
    if let Some(key) = stamp.and_then(extract_key) {
        return Some(Found { key, source: "stamp".into(), file: None });
    }
    if let Some(found) = exe.parent().and_then(|d| newest_mzn(d, None)).and_then(|p| from_file(&p, "file")) {
        return Some(found);
    }
    let month = Some(Duration::from_secs(30 * 24 * 3600));
    if let Some(found) = dirs::download_dir().and_then(|d| newest_mzn(&d, month)).and_then(|p| from_file(&p, "downloads")) {
        return Some(found);
    }
    arboard::Clipboard::new()
        .ok()
        .and_then(|mut c| c.get_text().ok())
        .and_then(|t| extract_key(&t))
        .map(|key| Found { key, source: "clipboard".into(), file: None })
}

pub fn read_file(path: &str) -> Option<String> {
    fs::read_to_string(path).ok().and_then(|t| extract_key(&t))
}
