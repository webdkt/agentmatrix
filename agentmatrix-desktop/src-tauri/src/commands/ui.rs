use tauri::Manager;
use tauri::WebviewWindow;

/// 显示系统通知
#[tauri::command]
pub async fn show_notification(title: String, body: String) -> Result<(), String> {
    println!("Notification: {} - {}", title, body);
    Ok(())
}

/// 检查窗口是否聚焦
#[tauri::command]
pub async fn is_window_focused(app: tauri::AppHandle) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("main") {
        return window.is_focused().map_err(|e| e.to_string());
    }
    Ok(false)
}

/// 显示并聚焦窗口
#[tauri::command]
pub async fn show_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 创建浮动窗口（胶囊 + 信息流）
/// Session 数据已通过 set_current_session 写入全局状态，窗口自行读取
#[tauri::command]
pub async fn create_floating_window(
    app: tauri::AppHandle,
) -> Result<(), String> {
    let capsule = app.get_webview_window("floating-capsule")
        .ok_or("Capsule window not found")?;
    let stream = app.get_webview_window("floating-stream")
        .ok_or("Stream window not found")?;

    // Show capsule, then position stream below it
    capsule.show().map_err(|e| e.to_string())?;
    capsule.set_focus().map_err(|e| e.to_string())?;

    // Position stream below capsule
    sync_stream_position_internal(&app)?;

    stream.show().map_err(|e| e.to_string())?;

    // Clip both windows to rounded rectangles
    clip_window_internal(&app, "floating-capsule", 20.0);
    clip_window_internal(&app, "floating-stream", 16.0);

    Ok(())
}

/// 隐藏浮动窗口（胶囊 + 信息流）
#[tauri::command]
pub async fn destroy_floating_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("floating-stream") {
        window.hide().map_err(|e| e.to_string())?;
    }
    if let Some(window) = app.get_webview_window("floating-capsule") {
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 设置胶囊窗口高度（菜单展开/收起时）
#[tauri::command]
pub async fn set_capsule_height(
    app: tauri::AppHandle,
    height: f64,
) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("floating-capsule") {
        let current_size = window.inner_size().map_err(|e| e.to_string())?;
        let scale = window.scale_factor().map_err(|e| e.to_string())?;
        let logical_width = current_size.width as f64 / scale;
        use tauri::LogicalSize;
        window.set_size(LogicalSize::new(logical_width, height))
            .map_err(|e| e.to_string())?;
        clip_window_internal(&app, "floating-capsule", 20.0);
    }
    Ok(())
}

/// 裁剪窗口为圆角矩形（内部 helper）
#[cfg(target_os = "macos")]
fn clip_window_internal(app: &tauri::AppHandle, label: &str, radius: f64) {
    use std::ffi::c_void;
    extern "C" {
        fn objc_msgSend() -> c_void;
        fn sel_registerName(name: *const i8) -> *const c_void;
    }

    let Some(window) = app.get_webview_window(label) else { return };
    let Ok(ns) = window.ns_window() else { return };
    let ns = ns as *mut c_void;

    unsafe {
        let id_ret: unsafe extern "C" fn(*mut c_void, *const c_void) -> *mut c_void =
            std::mem::transmute(objc_msgSend as *const ());
        let id_bool: unsafe extern "C" fn(*mut c_void, *const c_void, i8) =
            std::mem::transmute(objc_msgSend as *const ());
        let f64_msg: unsafe extern "C" fn(*mut c_void, *const c_void, f64) =
            std::mem::transmute(objc_msgSend as *const ());
        let usize_msg: unsafe extern "C" fn(*mut c_void, *const c_void) -> usize =
            std::mem::transmute(objc_msgSend as *const ());
        let id_usize: unsafe extern "C" fn(*mut c_void, *const c_void, usize) -> *mut c_void =
            std::mem::transmute(objc_msgSend as *const ());
        let sel_wl = sel_registerName(b"setWantsLayer:\0".as_ptr().cast());
        let sel_layer = sel_registerName(b"layer\0".as_ptr().cast());
        let sel_cr = sel_registerName(b"setCornerRadius:\0".as_ptr().cast());
        let sel_mb = sel_registerName(b"setMasksToBounds:\0".as_ptr().cast());
        let sel_cv = sel_registerName(b"contentView\0".as_ptr().cast());
        let sel_sub = sel_registerName(b"subviews\0".as_ptr().cast());
        let sel_count = sel_registerName(b"count\0".as_ptr().cast());
        let sel_obj = sel_registerName(b"objectAtIndex:\0".as_ptr().cast());

        let cv = id_ret(ns, sel_cv);
        if cv.is_null() { return; }

        // Clip contentView layer
        id_bool(cv, sel_wl, 1);
        let cv_layer = id_ret(cv, sel_layer);
        if !cv_layer.is_null() {
            f64_msg(cv_layer, sel_cr, radius);
            id_bool(cv_layer, sel_mb, 1);
        }

        // Force layer flush
        let sel_flush = sel_registerName(b"setNeedsDisplay:\0".as_ptr().cast());
        id_bool(cv, sel_flush, 1);

        // Clip every subview (vibrancy + webview)
        let subviews = id_ret(cv, sel_sub);
        if !subviews.is_null() {
            let count = usize_msg(subviews, sel_count);
            for i in 0..count {
                let sub = id_usize(subviews, sel_obj, i);
                if sub.is_null() { continue; }
                id_bool(sub, sel_wl, 1);
                let sub_layer = id_ret(sub, sel_layer);
                if !sub_layer.is_null() {
                    f64_msg(sub_layer, sel_cr, radius);
                    id_bool(sub_layer, sel_mb, 1);
                }
            }
        }

        // Force re-composite
        let sel_invalidate = sel_registerName(b"invalidateShadow\0".as_ptr().cast());
        let void_msg: unsafe extern "C" fn(*mut c_void, *const c_void) =
            std::mem::transmute(objc_msgSend as *const ());
        void_msg(ns, sel_invalidate);
    }

}

#[cfg(not(target_os = "macos"))]
fn clip_window_internal(_app: &tauri::AppHandle, _label: &str, _radius: f64) {}

/// 将信息流窗口定位到胶囊窗口下方
#[tauri::command]
pub fn sync_stream_position(app: tauri::AppHandle) -> Result<(), String> {
    sync_stream_position_internal(&app)
}

fn sync_stream_position_internal(app: &tauri::AppHandle) -> Result<(), String> {
    use tauri::PhysicalPosition;

    let capsule = match app.get_webview_window("floating-capsule") {
        Some(w) => w,
        None => return Ok(()),
    };
    let stream = match app.get_webview_window("floating-stream") {
        Some(w) => w,
        None => return Ok(()),
    };

    let capsule_pos = capsule.outer_position().map_err(|e| e.to_string())?;
    let scale = capsule.scale_factor().map_err(|e| e.to_string())?;

    // Use logical coordinates then convert to physical for the current screen's DPI.
    // Capsule min height (72 logical) + gap (24 logical) = fixed offset from capsule top,
    // regardless of menu expand/collapse or screen DPI.
    let offset_physical = ((72.0_f64 + 24.0_f64) * scale) as i32;

    let stream_x = capsule_pos.x;
    let stream_y = capsule_pos.y + offset_physical;

    let _ = stream.set_position(PhysicalPosition::new(stream_x, stream_y));

    Ok(())
}

/// 创建输入窗口（屏幕居中）
/// Session 数据已通过 set_current_session 写入全局状态，InputPanel 自行读取
#[tauri::command]
pub async fn create_input_window(
    app: tauri::AppHandle,
) -> Result<(), String> {
    let window = app.get_webview_window("input")
        .ok_or("Input window not found")?;

    // Center on screen
    center_window(&window, 480.0, 320.0)?;

    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;

    Ok(())
}

/// 关闭输入窗口
#[tauri::command]
pub async fn destroy_input_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("input") {
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 创建详情窗口（屏幕居中，显示完整 session 消息流）
#[tauri::command]
pub async fn create_detail_window(
    app: tauri::AppHandle,
) -> Result<(), String> {
    let window = app.get_webview_window("detail")
        .ok_or("Detail window not found")?;

    let base = if cfg!(dev) {
        "http://localhost:5173/detail.html"
    } else {
        "https://tauri.localhost/detail.html"
    };

    // Show first so eval works on the visible webview
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;

    center_window(&window, 480.0, 600.0)?;

    // Reload the page to reset state
    window.eval(&format!("window.location.href = '{}'", base))
        .map_err(|e| format!("Failed to navigate: {}", e))?;

    Ok(())
}

/// 关闭详情窗口
#[tauri::command]
pub async fn destroy_detail_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("detail") {
        let _ = window.eval("window.location.href = 'about:blank'");
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 将窗口居中到屏幕
fn center_window(window: &WebviewWindow, width: f64, height: f64) -> Result<(), String> {
    use tauri::LogicalSize;
    window.set_size(LogicalSize::new(width, height))
        .map_err(|e| e.to_string())?;
    window.center().map_err(|e| e.to_string())?;
    Ok(())
}

/// 最小化主窗口
#[tauri::command]
pub async fn minimize_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.minimize().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 恢复主窗口
#[tauri::command]
pub async fn restore_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.unminimize().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 使用指定配置文件打开浏览器
#[tauri::command]
pub async fn open_browser_with_profile(profile_path: String) -> Result<(), String> {
    // Chrome paths by platform
    #[cfg(target_os = "macos")]
    let chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

    #[cfg(target_os = "windows")]
    let chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe";

    #[cfg(target_os = "linux")]
    let chrome_path = "google-chrome";

    let chrome = std::path::Path::new(chrome_path);

    #[cfg(target_os = "macos")]
    {
        if !chrome.exists() {
            // Fallback: try to open with `open -a`
            std::process::Command::new("open")
                .args(["-a", "Google Chrome", "--args", &format!("--user-data-dir={}", profile_path)])
                .spawn()
                .map_err(|e| format!("Failed to open Chrome: {}", e))?;
        } else {
            std::process::Command::new(chrome)
                .arg(&format!("--user-data-dir={}", profile_path))
                .spawn()
                .map_err(|e| format!("Failed to open Chrome: {}", e))?;
        }
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new(chrome)
            .arg(&format!("--user-data-dir={}", profile_path))
            .spawn()
            .map_err(|e| format!("Failed to open Chrome: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new(chrome)
            .arg(&format!("--user-data-dir={}", profile_path))
            .spawn()
            .map_err(|e| format!("Failed to open Chrome: {}", e))?;
    }

    println!("✅ Opened Chrome with profile: {}", profile_path);
    Ok(())
}

/// 裁剪窗口为圆角矩形（macOS only）
#[tauri::command]
pub async fn clip_window_rounded(
    app: tauri::AppHandle,
    label: String,
    radius: f64,
) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        use std::ffi::c_void;
        extern "C" {
            fn objc_msgSend() -> c_void;
            fn sel_registerName(name: *const i8) -> *const c_void;
        }

        let window = app.get_webview_window(&label)
            .ok_or_else(|| format!("Window '{}' not found", label))?;
        let ns = window.ns_window().unwrap() as *mut c_void;

        unsafe {
            let id_ret: unsafe extern "C" fn(*mut c_void, *const c_void) -> *mut c_void =
                std::mem::transmute(objc_msgSend as *const ());
            let id_bool: unsafe extern "C" fn(*mut c_void, *const c_void, i8) =
                std::mem::transmute(objc_msgSend as *const ());

            // contentView
            let sel_cv = sel_registerName(b"contentView\0".as_ptr().cast());
            let cv = id_ret(ns, sel_cv);

            // setWantsLayer:YES
            let sel_wl = sel_registerName(b"setWantsLayer:\0".as_ptr().cast());
            id_bool(cv, sel_wl, 1);

            // layer
            let sel_layer = sel_registerName(b"layer\0".as_ptr().cast());
            let layer = id_ret(cv, sel_layer);

            // layer.cornerRadius = radius
            let sel_cr = sel_registerName(b"setCornerRadius:\0".as_ptr().cast());
            let f64_msg: unsafe extern "C" fn(*mut c_void, *const c_void, f64) =
                std::mem::transmute(objc_msgSend as *const ());
            f64_msg(layer, sel_cr, radius);

            let sel_mb = sel_registerName(b"setMasksToBounds:\0".as_ptr().cast());
            id_bool(layer, sel_mb, 1);
        }

        }
    Ok(())
}
