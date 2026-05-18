use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

pub fn setup<R: Runtime>(app: &AppHandle<R>) -> anyhow::Result<()> {
    let app_handle = app.clone();
    
    // In Tauri v2 Stable, we register shortcuts and then handle them in a central handler
    app.global_shortcut().on_shortcut(move |_app, shortcut, event| {
        if event.state() == ShortcutState::Pressed {
            // Match the shortcut by its description or ID
            let desc = shortcut.description();
            if desc == "alt+space" {
                let _ = app_handle.emit("capture", ());
            } else if desc == "escape" {
                let _ = app_handle.emit("dismiss", ());
            }
        }
    })?;

    // Register the actual keys
    app.global_shortcut().register("Alt+Space".parse::<Shortcut>()?)?;
    app.global_shortcut().register("Escape".parse::<Shortcut>()?)?;

    Ok(())
}
