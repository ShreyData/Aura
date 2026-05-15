use tauri::{AppHandle, Manager, Runtime};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

pub fn setup<R: Runtime>(app: &AppHandle<R>) -> anyhow::Result<()> {
    let capture_shortcut = "Alt+Space";
    let dismiss_shortcut = "Escape";

    let app_handle = app.clone();
    
    app.global_shortcut().on_shortcut(move |_app, shortcut, event| {
        if event.state() == tauri_plugin_global_shortcut::ShortcutState::Pressed {
            if shortcut.description() == "alt+space" {
                let _ = app_handle.emit("capture", ());
            } else if shortcut.description() == "escape" {
                let _ = app_handle.emit("dismiss", ());
            }
        }
    })?;

    app.global_shortcut().register("Alt+Space".parse::<Shortcut>()?)?;
    app.global_shortcut().register("Escape".parse::<Shortcut>()?)?;

    Ok(())
}
