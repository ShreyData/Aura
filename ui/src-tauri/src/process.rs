use std::process::{Command as StdCommand, Child};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager, Runtime};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;
use tokio::time::sleep;

enum AuraChild {
    Sidecar(CommandChild),
    Std(Child),
}

impl AuraChild {
    fn kill(self) {
        match self {
            AuraChild::Sidecar(child) => {
                let _ = child.kill();
            }
            AuraChild::Std(mut child) => {
                #[cfg(unix)]
                {
                    use nix::sys::signal::{self, Signal};
                    use nix::unistd::Pid;
                    let pid = Pid::from_raw(child.id() as i32);
                    let _ = signal::kill(pid, Signal::SIGTERM);
                    
                    // Wait 5 seconds then SIGKILL if still alive
                    // This is tricky to do synchronously here without blocking everything,
                    // but we can spawn a thread.
                    std::thread::spawn(move || {
                        std::thread::sleep(Duration::from_secs(5));
                        if let Ok(None) = child.try_wait() {
                            let _ = signal::kill(pid, Signal::SIGKILL);
                        }
                    });
                }
                #[cfg(windows)]
                {
                    let _ = child.kill();
                }
            }
        }
    }
}

static OLLAMA_CHILD: Mutex<Option<AuraChild>> = Mutex::new(Option::None);
static CORE_CHILD: Mutex<Option<AuraChild>> = Mutex::new(Option::None);

pub async fn start_ollama<R: Runtime>(app: &AppHandle<R>, port: u16) -> anyhow::Result<()> {
    let home = dirs::home_dir().ok_or_else(|| anyhow::anyhow!("Could not find home directory"))?;
    let models_dir = home.join(".aura").join("ollama_models");
    
    if !models_dir.exists() {
        std::fs::create_dir_all(&models_dir)?;
    }

    let sidecar_command = app.shell().sidecar("ollama")?
        .args(["serve"])
        .env("OLLAMA_HOST", format!("127.0.0.1:{}", port))
        .env("OLLAMA_MODELS", models_dir.to_string_lossy().to_string());

    let (_rx, child) = sidecar_command.spawn()?;
    
    let mut guard = OLLAMA_CHILD.lock().unwrap();
    *guard = Some(AuraChild::Sidecar(child));

    // Poll health
    let health_url = format!("http://127.0.0.1:{}", port);
    poll_health(&health_url).await?;

    Ok(())
}

pub async fn start_aura_core<R: Runtime>(app: &AppHandle<R>, port: u16) -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        // In development, we can try to launch via uv if available
        let child = StdCommand::new("uv")
            .args(["run", "uvicorn", "aura.main:app", "--host", "127.0.0.1", "--port", &port.to_string()])
            .current_dir("../core")
            .spawn()?;
        
        let mut guard = CORE_CHILD.lock().unwrap();
        *guard = Some(AuraChild::Std(child));
    } else {
        let sidecar_command = app.shell().sidecar("aura-core")?
            .args(["serve", "--port", &port.to_string()]);

        let (_rx, child) = sidecar_command.spawn()?;
        
        let mut guard = CORE_CHILD.lock().unwrap();
        *guard = Some(AuraChild::Sidecar(child));
    }

    // Poll health
    let health_url = format!("http://127.0.0.1:{}/health", port);
    poll_health(&health_url).await?;

    Ok(())
}

async fn poll_health(url: &str) -> anyhow::Result<()> {
    let client = reqwest::Client::new();
    let start = std::time::Instant::now();
    let timeout = Duration::from_secs(30);

    while start.elapsed() < timeout {
        match client.get(url).send().await {
            Ok(res) if res.status().is_success() => return Ok(()),
            _ => sleep(Duration::from_millis(500)).await,
        }
    }

    Err(anyhow::anyhow!("Health check timed out for {}", url))
}

pub fn kill_all() {
    let mut ollama_guard = OLLAMA_CHILD.lock().unwrap();
    if let Some(child) = ollama_guard.take() {
        child.kill();
    }

    let mut core_guard = CORE_CHILD.lock().unwrap();
    if let Some(child) = core_guard.take() {
        child.kill();
    }
}
