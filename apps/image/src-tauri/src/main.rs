#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf, process::{Child, Command, Stdio}, sync::Mutex};
use tauri::Manager;
#[cfg(windows)]
use std::os::windows::{io::AsRawHandle, process::CommandExt};

#[derive(Clone, Serialize, Deserialize)]
struct Bootstrap { python: String, port: u16 }
struct Service { child: Option<Child>, job: Option<usize>, home: PathBuf, root: PathBuf, script: PathBuf, bootstrap: Bootstrap, error: Option<String> }
impl Service {
    fn stop(&mut self) {
        #[cfg(windows)]
        if let Some(handle) = self.job.take() { unsafe { windows_sys::Win32::Foundation::CloseHandle(handle as _); } }
        if let Some(mut child) = self.child.take() { let _ = child.kill(); let _ = child.wait(); }
    }
    fn start(&mut self) -> Result<(), String> {
        self.stop();
        self.error = None;
        let log = fs::File::create(self.home.join("launcher.log")).map_err(|e|e.to_string())?;
        let mut command = Command::new(&self.bootstrap.python);
        command.arg(&self.script).arg("--data-dir").arg(&self.home).arg("--port").arg(self.bootstrap.port.to_string())
            .env("PYTHONUTF8", "1").env("PYTHONUNBUFFERED", "1").env("LOCAL_AI_ROOT", &self.root).env("LOCAL_AI_DESKTOP", "1").stdin(Stdio::null()).stdout(log.try_clone().map_err(|e|e.to_string())?).stderr(log);
        #[cfg(windows)] command.creation_flags(0x08000000);
        let mut child = command.spawn().map_err(|e| format!("API 服务无法启动，请配置 Python 运行环境：{e}"))?;
        #[cfg(windows)] unsafe {
            use windows_sys::Win32::{Foundation::CloseHandle, System::JobObjects::*};
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if handle.is_null() || SetInformationJobObject(handle, JobObjectExtendedLimitInformation, &info as *const _ as _, std::mem::size_of_val(&info) as u32) == 0 || AssignProcessToJobObject(handle, child.as_raw_handle() as _) == 0 {
                let _ = child.kill(); let _ = child.wait();
                if !handle.is_null() { CloseHandle(handle); }
                return Err("无法建立进程树管理，服务未启动".into());
            }
            self.job = Some(handle as usize);
        }
        self.child = Some(child);
        Ok(())
    }
}
impl Drop for Service { fn drop(&mut self) { self.stop(); } }

#[tauri::command]
fn connection(state: tauri::State<Mutex<Service>>) -> Result<serde_json::Value, String> {
    let mut s = state.lock().map_err(|e|e.to_string())?;
    if let Some(error) = &s.error { return Err(error.clone()); }
    if let Some(child) = s.child.as_mut() {
        if let Some(code) = child.try_wait().map_err(|e|e.to_string())? {
            return Err(format!("API 进程已退出 ({code})：{}", fs::read_to_string(s.home.join("launcher.log")).unwrap_or_default()));
        }
    }
    let token = fs::read_to_string(s.home.join("api-token")).map_err(|_| "服务正在初始化".to_string())?;
    Ok(serde_json::json!({"base":format!("http://127.0.0.1:{}",s.bootstrap.port),"token":token.trim(),"data_dir":s.home,"desktop_key":fs::read_to_string(s.home.join("desktop-token")).unwrap_or_default().trim()}))
}
#[tauri::command]
fn bootstrap(state: tauri::State<Mutex<Service>>) -> Result<Bootstrap, String> { Ok(state.lock().map_err(|e|e.to_string())?.bootstrap.clone()) }
#[tauri::command]
fn restart_api(config: Bootstrap, state: tauri::State<Mutex<Service>>) -> Result<(), String> {
    if config.port < 1024 || !PathBuf::from(&config.python).is_file() { return Err("请选择有效的 Python 文件和 1024 以上端口".into()); }
    let mut s = state.lock().map_err(|e|e.to_string())?;
    fs::write(s.home.join("runtime.json"), serde_json::to_vec_pretty(&config).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    s.bootstrap = config;
    if let Err(error) = s.start() { s.error = Some(error.clone()); return Err(error); }
    Ok(())
}
#[tauri::command]
fn save_download(request: tauri::ipc::Request<'_>) -> Result<(), String> {
    let encoded = request.headers().get("x-save-path")
        .ok_or("Missing save path")?.to_str().map_err(|e| e.to_string())?;
    let path: String = serde_json::from_str(encoded).map_err(|e| e.to_string())?;
    let path = PathBuf::from(path);
    if !path.is_absolute() || path.file_name().is_none() {
        return Err("Invalid save path".into());
    }
    match request.body() {
        tauri::ipc::InvokeBody::Raw(bytes) => fs::write(path, bytes).map_err(|e| e.to_string()),
        _ => Err("Expected binary file data".into()),
    }
}

#[tauri::command]
fn reveal_file(path: String) -> Result<(), String> {
    let path = PathBuf::from(path.replace('/', "\\"));
    if !path.is_absolute() || !path.is_file() {
        return Err("文件不存在或已移动".into());
    }
    #[cfg(windows)] {
        // A dedicated COM apartment avoids conflicting with WebView's apartment.
        std::thread::spawn(move || reveal_in_shell(&path)).join()
            .map_err(|_| "无法打开文件所在目录".to_string())?
    }
    #[cfg(not(windows))] { Err("此功能仅支持 Windows".into()) }
}

#[cfg(windows)]
fn reveal_in_shell(path: &std::path::Path) -> Result<(), String> {
    use std::os::windows::ffi::OsStrExt;
    use std::ptr::{null, null_mut};
    use windows_sys::Win32::System::Com::{CoInitializeEx, CoUninitialize, CoTaskMemFree, COINIT_APARTMENTTHREADED};
    use windows_sys::Win32::UI::Shell::{SHParseDisplayName, SHOpenFolderAndSelectItems};
    let wide: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
    unsafe {
        let initialized = CoInitializeEx(null(), COINIT_APARTMENTTHREADED as u32);
        if initialized < 0 { return Err(format!("Windows Shell 初始化失败 (0x{:08X})", initialized as u32)); }
        let mut item = null_mut();
        let parsed = SHParseDisplayName(wide.as_ptr(), null_mut(), &mut item, 0, null_mut());
        let result = if parsed < 0 {
            Err(format!("无法定位文件 (0x{:08X})", parsed as u32))
        } else {
            // cidl=0 means the absolute item itself is selected in its parent folder.
            let opened = SHOpenFolderAndSelectItems(item, 0, null(), 0);
            if opened < 0 { Err(format!("无法打开文件所在目录 (0x{:08X})", opened as u32)) } else { Ok(()) }
        };
        if !item.is_null() { CoTaskMemFree(item.cast()); }
        CoUninitialize();
        result
    }
}

#[tauri::command]
fn system_language() -> String {
    #[cfg(windows)] {
        #[link(name = "kernel32")]
        extern "system" { fn GetUserDefaultUILanguage() -> u16; }
        let lang = unsafe { GetUserDefaultUILanguage() };
        return match lang & 0x03ff { 0x0004 => "zh-CN", 0x0011 => "ja", _ => "en" }.to_string();
    }
    #[cfg(not(windows))] { "en".to_string() }
}
fn main() {
    tauri::Builder::default().plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let exe_dir = std::env::current_exe()?.parent().unwrap().to_path_buf();
            let project = if exe_dir.join("apps/image/server/run.py").is_file() {exe_dir.join("apps/image")} else {PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()};
            let home = app.path().app_data_dir()?;
            fs::create_dir_all(&home)?;
            let bootstrap = fs::read(home.join("runtime.json")).ok().and_then(|s|serde_json::from_slice(&s).ok()).unwrap_or(Bootstrap { python: project.parent().unwrap().parent().unwrap().join("runtimes/image/Scripts/python.exe").to_string_lossy().into(), port:19877 });
            let packaged = app.path().resource_dir()?.join("server/run.py");
            let source_script = project.join("server/run.py");
            let script = if source_script.is_file() { source_script } else { packaged };
            let mut service = Service { child: None, job: None, home, root:project, script, bootstrap, error: None };
            if let Err(error) = service.start() { service.error = Some(error); }
            app.manage(Mutex::new(service));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![connection, bootstrap, restart_api, system_language, save_download, reveal_file])
        .build(tauri::generate_context!()).expect("无法启动桌面应用")
        .run(|app, event| { if let tauri::RunEvent::Exit = event { app.state::<Mutex<Service>>().lock().unwrap().stop(); } });
}

