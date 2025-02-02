#![allow(dead_code)]
#![allow(non_snake_case)]

#[link(wasm_import_module = "sys")]
extern {
  #[link_name = "millis"]         fn unsafe_millis() -> u32;
  #[link_name = "delay"]          fn unsafe_delay(ms: u32);
  #[link_name = "pinMode"]        fn unsafe_pinMode(pin:u32, mode:u32);
  #[link_name = "digitalWrite"]   fn unsafe_digitalWrite(pin:u32, value:u32);
  #[link_name = "getPinLED"]      fn unsafe_getPinLED() -> u32;
  #[link_name = "getChipID"] fn unsafe_getChipID(buf : *mut u8);
  #[link_name = "print"] fn unsafe_print(ptr: *const u8, size: usize);
  #[link_name = "printInt"] fn unsafe_print_int(out: u32);
  #[link_name = "printFloat"] fn unsafe_print_float(out: f32);
  #[link_name = "testiFunction"] fn unsafe_testiFunction(value: i32) -> i32;
}

//#[link(wasm_import_module = "serial")]
//extern {
//  #[link_name = "print"] fn unsafe_print(ptr: *const u8, size: usize);
//  #[link_name = "printInt"] fn unsafe_print_int(out: u32);
//  #[link_name = "printFloat"] fn unsafe_print_float(out: f32);
//}

#[link(wasm_import_module = "wifi")]
extern {
  #[link_name = "wifiConnect"] fn unsafe_wifi_connect(ssid: *const u8, ssid_len : usize, password: *const u8, password_len : usize);
  #[link_name = "wifiStatus"] fn unsafe_wifi_status() -> u32;
  #[link_name = "wifiLocalIp"] fn unsafe_wifi_local_ip(buf : *mut u8);
  #[link_name = "printWifiLocalIp"] fn unsafe_print_wifi_local_ip();
}

#[link(wasm_import_module = "communication")]
extern {
  #[link_name = "rpcCall"] fn unsafe_rpcCall(func_name: *const u8, func_name_len: usize, data_ptr: *const u8, data_size: usize);
}

#[link(wasm_import_module = "http")]
extern {
  #[link_name = "httpPost"] fn unsafe_httpPost(server_name: *const u8, server_name_len: u32, content: *const u8, content_len: u32) -> u32;
  #[link_name = "http_post"] fn unsafe_http_post(server_name: *const u8, server_name_len : usize, content: *const u8, content_len : usize);
}

// Peripherals

#[link(wasm_import_module = "camera")]
extern {
  #[link_name = "takeImageDynamicSize"] fn unsafe_takeImageDynamicSize(data_ptr_ptr: *const u8, data_size_ptr: *const u8);
  #[link_name = "takeImageStaticSize"] fn unsafe_takeImageStaticSize(data_ptr: *const u8, data_size_ptr: *const u8);
}

#[link(wasm_import_module = "dht")]
extern {
  #[link_name = "readTemperature"] fn unsafe_read_temperature() -> f32;
  #[link_name = "readHumidity"] fn unsafe_read_humidity() -> f32;
}

pub static LOW:u32  = 0;
pub static HIGH:u32 = 1;

pub static INPUT:u32          = 0x0;
pub static OUTPUT:u32         = 0x1;
pub static INPUT_PULLUP:u32   = 0x2;

/* Wifi Status */
pub static WL_NO_SHIELD: u32        = 255;
pub static WL_IDLE_STATUS: u32      = 0;
pub static WL_NO_SSID_AVAIL: u32    = 1;
pub static WL_SCAN_COMPLETED: u32   = 2;
pub static WL_CONNECTED: u32        = 0x03;
pub static WL_CONNECT_FAILED: u32   = 4;
pub static WL_CONNECTION_LOST: u32  = 5;
pub static WL_DISCONNECTED: u32     = 6;

pub fn millis         () -> u32              { unsafe { unsafe_millis() } }
pub fn delay          (ms: u32)              { unsafe { unsafe_delay(ms); } }
pub fn pinMode       (pin:u32, mode:u32)    { unsafe { unsafe_pinMode(pin, mode) } }
pub fn digitalWrite  (pin:u32, value:u32)   { unsafe { unsafe_digitalWrite(pin, value) } }
pub fn serialPrintInt(out: u32) { unsafe { unsafe_print_int(out); } }
pub fn serialPrintFloat(out: f32) {unsafe {unsafe_print_float(out);}}
pub fn serialPrint     (out: &str)       {
  unsafe {
    unsafe_print(out.as_bytes().as_ptr() as *const u8, out.len());
  }
}

pub fn serialPrintln     (out: &str)       {
  serialPrint(out);
  serialPrint("\n");
}

pub fn getPinLED    () -> u32 { unsafe { unsafe_getPinLED() } }

pub fn wifiConnect (ssid :&str, password : &str){
  unsafe {
    unsafe_wifi_connect(
      ssid.as_bytes().as_ptr() as *const u8, ssid.len(),
      password.as_bytes().as_ptr() as *const u8, password.len()
    );
  }
}
pub fn wifiStatus    () -> u32 { unsafe { unsafe_wifi_status() } }
pub fn printWifiLocalIp () { unsafe { unsafe_print_wifi_local_ip() } }

pub fn httpPost (server_name : &str, content : &str) -> u32 {
  unsafe {
    unsafe_httpPost(
      server_name.as_bytes().as_ptr() as *const u8, server_name.len() as u32,
      content.as_bytes().as_ptr() as *const u8, content.len() as u32
    )
  }
}
pub fn http_post (server_name :&str, content : &str){
  unsafe {
    unsafe_http_post(
      server_name.as_bytes().as_ptr() as *const u8, server_name.len(),
      content.as_bytes().as_ptr() as *const u8, content.len()
    );
  }
}

pub fn readTemperature () -> f32 { unsafe {unsafe_read_temperature() } }
pub fn readHumidity    () -> f32 { unsafe {unsafe_read_humidity() } }

pub fn takeImageDynamicSize(data_ptr_ptr: *const u8, data_size_ptr: *const u8) {
  unsafe {
    unsafe_takeImageDynamicSize(data_ptr_ptr, data_size_ptr);
  }
}

pub fn takeImageStaticSize(data_ptr: *const u8, data_size_ptr: *const u8) {
  unsafe {
    unsafe_takeImageStaticSize(data_ptr, data_size_ptr);
  }
}

pub fn testiFunction(value: i32) -> *const f32 {
  unsafe { unsafe_testiFunction(value) as *const f32 }
}

pub fn rpcCall (func_name: &str, data_ptr: *const u8, data_size: usize) {
  unsafe {
    unsafe_rpcCall(
      func_name.as_bytes().as_ptr() as *const u8, func_name.len(), data_ptr, data_size
    );
  }
}

/// Copied from:
/// https://github.com/radu-matei/wasi-tensorflow-inference/blob/master/crates/wasi-mobilenet-inference/src/lib.rs
///
/// Allocate memory into the module's linear memory
/// and return the offset to the start of the block.
#[no_mangle]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    // create a new mutable buffer with reserved capacity `len`
    let mut buf = Vec::with_capacity(len);
    // take a mutable pointer to the buffer
    let ptr = buf.as_mut_ptr();
    // take ownership of the memory block and
    // ensure that its destructor is not
    // called when the object goes out of scope
    // at the end of the function
    std::mem::forget(buf);
    // return the pointer so the runtime
    // can write data at this offset
    return ptr;
}
