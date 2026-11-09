// No console window on Windows; command-line use attaches to the parent console.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    mizan_setup_lib::run()
}
