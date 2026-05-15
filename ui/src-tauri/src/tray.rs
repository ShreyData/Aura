use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, Runtime,
};

pub fn setup<R: Runtime>(app: &AppHandle<R>) -> anyhow::Result<()> {
    let open_hub = MenuItem::with_id(app, "open_hub", "Open Hub", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(
        app,
        &[
            &open_hub,
            &tauri::menu::PredefinedMenuItem::separator(app)?,
            &settings,
            &tauri::menu::PredefinedMenuItem::separator(app)?,
            &quit,
        ],
    )?;

    let _tray = TrayIconBuilder::with_id("main")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| {
            match event.id.as_ref() {
                "open_hub" => {
                    if let Some(window) = app.get_webview_window("hub") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "settings" => {
                    // Settings is usually a view in Hub or a separate window.
                    // The prompt doesn't specify a settings window label, 
                    // but docs/UI_Architecture.md says "settings" lives in Hub.
                    // Wait, UI_Architecture.md table shows: orb, hub, permission, onboarding.
                    // So "Settings" probably opens Hub at the settings view.
                    if let Some(window) = app.get_webview_window("hub") {
                        let _ = window.show();
                        let _ = window.set_focus();
                        let _ = app.emit("navigate", "settings");
                    }
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)?;

    Ok(())
}
