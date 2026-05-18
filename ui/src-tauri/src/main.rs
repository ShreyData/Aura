// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod process;
mod ipc;
mod hotkeys;
mod tray;

use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            ipc::health,
            ipc::recommend_model,
            ipc::approve_tool,
            ipc::get_pending_tools,
            ipc::ingest_file,
            ipc::list_models,
            ipc::pull_model,
            ipc::delete_model,
            ipc::get_config,
            ipc::update_config,
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            
            // 1. Setup Hotkeys
            if let Err(e) = hotkeys::setup(&handle) {
                eprintln!("Failed to setup hotkeys: {}", e);
            }

            // 2. Setup Tray
            if let Err(e) = tray::setup(&handle) {
                eprintln!("Failed to setup tray: {}", e);
            }

            tauri::async_runtime::spawn(async move {
                println!("Starting sidecars...");
                
                // 1. Start Ollama on 11435
                if let Err(e) = process::start_ollama(&handle, 11435).await {
                    eprintln!("Failed to start Ollama sidecar: {}", e);
                } else {
                    println!("Ollama sidecar started and healthy.");
                }

                // 2. Start Aura Core on 11434
                if let Err(e) = process::start_aura_core(&handle, 11434).await {
                    eprintln!("Failed to start Aura Core sidecar: {}", e);
                } else {
                    println!("Aura Core sidecar started and healthy.");
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");

    // Ensure all processes are killed on exit
    process::kill_all();
}
