use serde_json::{json, Value};
use reqwest::Client;

const CORE_URL: &str = "http://127.0.0.1:11434";

#[tauri::command]
pub async fn health() -> Result<Value, String> {
    let client = Client::new();
    let response = client.get(format!("{}/health", CORE_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn recommend_model() -> Result<Value, String> {
    let client = Client::new();
    let response = client.get(format!("{}/v1/models/recommend", CORE_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn approve_tool(request_id: String, approved: bool) -> Result<Value, String> {
    let client = Client::new();
    let response = client.post(format!("{}/v1/tools/approve", CORE_URL))
        .json(&json!({ "request_id": request_id, "approved": approved }))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_pending_tools() -> Result<Value, String> {
    let client = Client::new();
    let response = client.get(format!("{}/v1/tools/pending", CORE_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn ingest_file(file_path: String) -> Result<Value, String> {
    let client = Client::new();
    let response = client.post(format!("{}/v1/rag/ingest", CORE_URL))
        .json(&json!({ "file_path": file_path }))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn list_models() -> Result<Value, String> {
    let client = Client::new();
    let response = client.get(format!("{}/v1/models", CORE_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn pull_model(model: String) -> Result<Value, String> {
    let client = Client::new();
    let response = client.post(format!("{}/v1/models/pull", CORE_URL))
        .json(&json!({ "model": model }))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_model(name: String) -> Result<Value, String> {
    let client = Client::new();
    let response = client.delete(format!("{}/v1/models/{}", CORE_URL, name))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_config() -> Result<Value, String> {
    let client = Client::new();
    let response = client.get(format!("{}/v1/config", CORE_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn update_config(updates: Value) -> Result<Value, String> {
    let client = Client::new();
    let response = client.patch(format!("{}/v1/config", CORE_URL))
        .json(&updates)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    
    response.json::<Value>().await.map_err(|e| e.to_string())
}
