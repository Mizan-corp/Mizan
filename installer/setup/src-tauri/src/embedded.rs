//! What's appended to the setup binary.
//!
//! ```text
//! [ the Tauri program ][ payload.zip ][ licence stamp (optional) ][ footer: 32 bytes ]
//! footer = b"MZNSETUP" + payload_offset (u64 LE) + payload_len (u64 LE) + stamp_len (u64 LE)
//! ```
//! `installer/build.py` appends the payload; `installer/stamp.py` (or the owner
//! panel's per-client download) adds the client's licence. Without a footer (a
//! development build) the payload comes from MIZAN_PAYLOAD_DIR instead.

use std::fs::{self, File};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

const MAGIC: &[u8; 8] = b"MZNSETUP";
const FOOTER: u64 = 32;

pub struct Embedded {
    pub exe: PathBuf,
    /// Length of the program itself (everything before the payload).
    pub program_len: u64,
    pub payload: Option<(u64, u64)>,
    pub stamp: Option<String>,
}

pub fn read_self() -> io::Result<Embedded> {
    let exe = std::env::current_exe()?;
    let mut f = File::open(&exe)?;
    let total = f.metadata()?.len();
    let none = |exe: PathBuf| Embedded { exe, program_len: total, payload: None, stamp: None };
    if total < FOOTER {
        return Ok(none(exe));
    }
    f.seek(SeekFrom::End(-(FOOTER as i64)))?;
    let mut footer = [0u8; 32];
    f.read_exact(&mut footer)?;
    if &footer[..8] != MAGIC {
        return Ok(none(exe));
    }
    let n = |i: usize| u64::from_le_bytes(footer[i..i + 8].try_into().unwrap());
    let (offset, len, stamp_len) = (n(8), n(16), n(24));
    let mut stamp = None;
    if stamp_len > 0 && stamp_len < 64 * 1024 {
        f.seek(SeekFrom::Start(offset + len))?;
        let mut buf = vec![0u8; stamp_len as usize];
        f.read_exact(&mut buf)?;
        stamp = String::from_utf8(buf).ok().map(|s| s.trim().to_string());
    }
    Ok(Embedded { exe, program_len: offset, payload: if len > 0 { Some((offset, len)) } else { None }, stamp })
}

/// A window onto part of a file, for reading the embedded zip in place.
struct Section {
    file: File,
    start: u64,
    len: u64,
    pos: u64,
}

impl Read for Section {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        let left = self.len.saturating_sub(self.pos);
        if left == 0 {
            return Ok(0);
        }
        let want = (buf.len() as u64).min(left) as usize;
        self.file.seek(SeekFrom::Start(self.start + self.pos))?;
        let n = self.file.read(&mut buf[..want])?;
        self.pos += n as u64;
        Ok(n)
    }
}

impl Seek for Section {
    fn seek(&mut self, to: SeekFrom) -> io::Result<u64> {
        let next = match to {
            SeekFrom::Start(p) => p as i64,
            SeekFrom::End(d) => self.len as i64 + d,
            SeekFrom::Current(d) => self.pos as i64 + d,
        };
        if next < 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "seek before start"));
        }
        self.pos = next as u64;
        Ok(self.pos)
    }
}

/// Unpack the payload into `dest`, reporting (done, total) files.
pub fn extract(emb: &Embedded, dest: &Path, mut progress: impl FnMut(usize, usize)) -> Result<(), String> {
    fs::create_dir_all(dest).map_err(|e| e.to_string())?;
    if let Some((start, len)) = emb.payload {
        let file = File::open(&emb.exe).map_err(|e| e.to_string())?;
        let mut zip = zip::ZipArchive::new(Section { file, start, len, pos: 0 }).map_err(|e| format!("payload: {e}"))?;
        let total = zip.len();
        for i in 0..total {
            let mut entry = zip.by_index(i).map_err(|e| e.to_string())?;
            let Some(rel) = entry.enclosed_name() else { continue };
            let out = dest.join(rel);
            if entry.is_dir() {
                fs::create_dir_all(&out).map_err(|e| e.to_string())?;
            } else {
                if let Some(parent) = out.parent() {
                    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                let mut w = File::create(&out).map_err(|e| format!("{}: {e}", out.display()))?;
                io::copy(&mut entry, &mut w).map_err(|e| e.to_string())?;
                #[cfg(unix)]
                if let Some(mode) = entry.unix_mode() {
                    use std::os::unix::fs::PermissionsExt;
                    let _ = fs::set_permissions(&out, fs::Permissions::from_mode(mode));
                }
            }
            if i % 50 == 0 || i + 1 == total {
                progress(i + 1, total);
            }
        }
        return Ok(());
    }
    // Development: copy an unpacked payload folder.
    let src = std::env::var("MIZAN_PAYLOAD_DIR").map(PathBuf::from).map_err(|_| {
        "This setup has no payload (development build without MIZAN_PAYLOAD_DIR).".to_string()
    })?;
    let files: Vec<PathBuf> = walk(&src);
    let total = files.len();
    for (i, f) in files.iter().enumerate() {
        let rel = f.strip_prefix(&src).unwrap();
        let out = dest.join(rel);
        if let Some(parent) = out.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        fs::copy(f, &out).map_err(|e| format!("{}: {e}", out.display()))?;
        if i % 50 == 0 || i + 1 == total {
            progress(i + 1, total);
        }
    }
    Ok(())
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() {
                out.extend(walk(&p));
            } else {
                out.push(p);
            }
        }
    }
    out
}

/// Write just the program part of this binary: the installed desktop app.
pub fn write_program(emb: &Embedded, dest: &Path) -> io::Result<()> {
    let mut src = File::open(&emb.exe)?;
    let mut out = File::create(dest)?;
    io::copy(&mut (&mut src).take(emb.program_len), &mut out)?;
    out.flush()?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(dest, fs::Permissions::from_mode(0o755))?;
    }
    Ok(())
}
