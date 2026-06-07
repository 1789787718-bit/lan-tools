#!/usr/bin/env python3
"""
局域网工具箱 — 文件传输 + 手机遥控(触摸板+键盘)
手机浏览器打开即可用，无需安装 App
"""

import http.server
import os
import sys
import json
import urllib.parse
import ctypes
from pathlib import Path

UPLOAD_DIR = Path(__file__).parent / "files"
UPLOAD_DIR.mkdir(exist_ok=True)

# ====================== Win32 API 封装 ======================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 鼠标常量
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800
MOUSEEVENTF_ABSOLUTE   = 0x8000

# 键盘常量
KEYEVENTF_KEYUP   = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE  = 0x0004
INPUT_KEYBOARD     = 1

VK_RETURN = 0x0D
VK_BACK   = 0x08
VK_TAB    = 0x09
VK_ESCAPE = 0x1B
VK_SPACE  = 0x20
VK_LEFT   = 0x25
VK_UP     = 0x26
VK_RIGHT  = 0x27
VK_DOWN   = 0x28
VK_DELETE = 0x2E
VK_HOME   = 0x24
VK_END    = 0x23
VK_F1     = 0x70
VK_SHIFT  = 0x10
VK_LWIN   = 0x5B
VK_MENU   = 0x12  # Alt

KEY_MAP = {
    'Enter': VK_RETURN, 'Backspace': VK_BACK, 'Tab': VK_TAB, 'Escape': VK_ESCAPE,
    'Space': VK_SPACE, ' ': VK_SPACE,
    'ArrowLeft': VK_LEFT, 'ArrowUp': VK_UP, 'ArrowRight': VK_RIGHT, 'ArrowDown': VK_DOWN,
    'Delete': VK_DELETE, 'Home': VK_HOME, 'End': VK_END,
}

for i in range(1, 13):
    KEY_MAP[f'F{i}'] = VK_F1 + i - 1

# --- SendInput 结构体 ---
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", ctypes.c_char * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]

def send_input(vin):
    """发送键盘输入事件"""
    user32.SendInput(1, ctypes.byref(vin), ctypes.sizeof(vin))

def mouse_move(dx, dy):
    """相对移动鼠标"""
    user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)

def mouse_click(button='left'):
    """模拟鼠标点击"""
    if button == 'left':
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif button == 'right':
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif button == 'middle':
        user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)

def mouse_down(button='left'):
    if button == 'left':
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

def mouse_up(button='left'):
    if button == 'left':
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def mouse_scroll(delta):
    """滚动 (正=上, 负=下)"""
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)

def send_key(vk_code, keydown=True):
    """发送按键 (SendInput)"""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk_code
    inp.ki.dwFlags = 0 if keydown else KEYEVENTF_KEYUP
    send_input(inp)

def type_key(vk_code):
    """按下并释放一个键"""
    send_key(vk_code, True)
    send_key(vk_code, False)

def type_text(text):
    """输入文本 - 使用 Unicode 键盘事件"""
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.ki.dwFlags = KEYEVENTF_UNICODE

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    for ch in text:
        if ch == '\n':
            type_key(VK_RETURN)
        elif ch == '\r':
            pass
        else:
            code = ord(ch)
            inp_down.ki.wScan = code
            inp_up.ki.wScan = code
            send_input(inp_down)
            send_input(inp_up)

# ====================== HTML 页面 ======================

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>工具箱</title>
<style>
:root{--bg:#0f0f0f;--card:#1a1a1a;--accent:#4dabf7;--text:#e0e0e0;--sub:#888;--danger:#ff6b6b;--border:#2a2a2a;--green:#51cf66;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:16px;padding-bottom:100px;}
h1{text-align:center;font-size:1.3rem;margin:16px 0 4px;}
.subtitle{text-align:center;color:var(--sub);font-size:0.8rem;margin-bottom:20px;}

.nav{display:flex;gap:8px;margin-bottom:20px;justify-content:center;}
.nav a{color:var(--sub);text-decoration:none;padding:8px 20px;border-radius:20px;font-size:0.85rem;background:var(--card);border:1px solid var(--border);}
.nav a.active{background:var(--accent);color:#fff;border-color:var(--accent);}

.dropzone{border:2px dashed var(--border);border-radius:16px;padding:40px 20px;text-align:center;margin-bottom:24px;transition:all .2s;cursor:pointer;background:var(--card);}
.dropzone.drag{border-color:var(--accent);background:#1a2330;}
.dropzone .icon{font-size:3rem;margin-bottom:12px;}
.dropzone p{color:var(--sub);font-size:0.9rem;}
.dropzone .btn{display:inline-block;margin-top:12px;padding:10px 24px;background:var(--accent);color:#fff;border-radius:8px;font-size:0.9rem;cursor:pointer;border:none;}

.file-list{display:flex;flex-direction:column;gap:8px;}
.file-item{display:flex;align-items:center;justify-content:space-between;background:var(--card);border-radius:10px;padding:12px 16px;border:1px solid var(--border);}
.file-info{flex:1;min-width:0;}
.file-name{font-size:0.95rem;word-break:break-all;}
.file-size{font-size:0.78rem;color:var(--sub);margin-top:4px;}
.file-actions{display:flex;gap:8px;flex-shrink:0;margin-left:12px;}
.btn-sm{padding:8px 16px;border-radius:8px;font-size:0.85rem;cursor:pointer;border:none;text-decoration:none;display:inline-block;}
.btn-dl{background:var(--accent);color:#fff;}
.btn-del{background:transparent;color:var(--danger);border:1px solid var(--danger);}
.empty{text-align:center;color:var(--sub);padding:40px;}

#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:12px 24px;border-radius:12px;font-size:0.9rem;opacity:0;transition:opacity .3s;pointer-events:none;z-index:99;}
#toast.show{opacity:1;}

input[type=file]{display:none;}

/* ====== 遥控器 ====== */
.remote-container{display:none;}
.pad{background:var(--card);border:2px solid var(--border);border-radius:16px;height:250px;touch-action:none;margin-bottom:16px;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:0.9rem;user-select:none;-webkit-user-select:none;}
.pad.active{border-color:var(--accent);}

.btn-row{display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;}
.btn-r{padding:12px 0;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:0.9rem;cursor:pointer;flex:1;min-width:60px;text-align:center;}
.btn-r:active{background:var(--accent);}
.btn-r.wide{flex:2;}
.btn-r.accent{background:var(--accent);border-color:var(--accent);}
.btn-r.green{background:var(--green);border-color:var(--green);color:#000;}

#keyInput{width:100%;padding:14px;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:1rem;margin-bottom:12px;outline:none;}
#keyInput:focus{border-color:var(--accent);}
</style>
</head>
<body>

<div class="nav">
  <a href="#" class="active" data-page="files">📦 文件传输</a>
  <a href="#" data-page="remote">🎮 遥控器</a>
</div>

<h1 id="title">📦 局域网文件传输</h1>
<p class="subtitle" id="ip"></p>

<!-- ====== 文件传输页 ====== -->
<div id="page-files">
<div class="dropzone" id="dropzone">
  <div class="icon">📤</div>
  <p>拖文件到这里 / 点击上传</p>
  <button class="btn" onclick="document.getElementById('fileInput').click()">选择文件</button>
</div>
<input type="file" id="fileInput" multiple>
<div class="file-list" id="fileList"></div>
</div>

<!-- ====== 遥控器页 ====== -->
<div id="page-remote" class="remote-container">
  <div class="pad" id="pad">👆 手指在这里滑动控制鼠标</div>

  <div class="btn-row">
    <button class="btn-r" id="btnLeft">🖱️ 左键</button>
    <button class="btn-r" id="btnRight">🖱️ 右键</button>
    <button class="btn-r wide" id="btnScroll">↕️ 上下滚动</button>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px;">
  <input type="text" id="keyInput" placeholder="在这里打字..." autocomplete="off" autocorrect="off" style="flex:1;">
  <button id="btnSend" class="btn-r accent" style="flex:0;white-space:nowrap;padding:12px 20px;">发送</button>
</div>

  <div class="btn-row">
    <button class="btn-r" data-key="Tab">Tab</button>
    <button class="btn-r" data-key="Escape">Esc</button>
    <button class="btn-r" data-key="Backspace">⌫退格</button>
    <button class="btn-r" data-key="Space">空格</button>
  </div>
  <div class="btn-row">
    <button class="btn-r" data-key="Enter">Enter</button>
    <button class="btn-r" data-key="ArrowUp">↑</button>
    <button class="btn-r" data-key="ArrowDown">↓</button>
    <button class="btn-r" data-key="ArrowLeft">←</button>
    <button class="btn-r" data-key="ArrowRight">→</button>
  </div>
  <div class="btn-row">
    <button class="btn-r green" id="btnWin">⊞ Win</button>
    <button class="btn-r green" id="btnAltTab">Alt+Tab</button>
    <button class="btn-r green" id="btnTask">任务视图</button>
  </div>
</div>

<div id="toast"></div>

<script>
// ====== 导航切换 ======
const PAGES = {files:document.getElementById('page-files'),remote:document.getElementById('page-remote')};
const NAVS = document.querySelectorAll('.nav a');
const TITLE = document.getElementById('title');

NAVS.forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const page = a.dataset.page;
    NAVS.forEach(n => n.classList.remove('active'));
    a.classList.add('active');
    Object.values(PAGES).forEach(p => p.style.display='none');
    PAGES[page].style.display = page==='files'?'block':'block';
    TITLE.textContent = page==='files'?'📦 局域网文件传输':'🎮 手机遥控器';
  });
});

// ====== IP显示 ======
fetch('/api/ip').then(r=>r.json()).then(d=>{
  document.getElementById('ip').textContent = '本机: '+d.ip+':'+d.port;
});

// ====== Toast ======
const TOAST = document.getElementById('toast');
function toast(msg,d=2000){TOAST.textContent=msg;TOAST.classList.add('show');setTimeout(()=>TOAST.classList.remove('show'),d);}

// ====== 文件上传/下载/删除 ======
const DROP = document.getElementById('dropzone');
const INPUT = document.getElementById('fileInput');
const LIST = document.getElementById('fileList');

DROP.addEventListener('dragover',e=>{e.preventDefault();DROP.classList.add('drag');});
DROP.addEventListener('dragleave',e=>{e.preventDefault();DROP.classList.remove('drag');});
DROP.addEventListener('drop',e=>{e.preventDefault();DROP.classList.remove('drag');upload(e.dataTransfer.files);});
INPUT.addEventListener('change',e=>upload(e.target.files));

async function upload(files){for(const f of files){const fd=new FormData();fd.append('file',f);try{const r=await fetch('/upload',{method:'POST',body:fd});if(r.ok){toast('✅ '+f.name+' 上传成功');loadFiles();}else{toast('❌ '+await r.text());}}catch(e){toast('❌ '+e.message);}}}

async function loadFiles(){try{const r=await fetch('/api/files');const files=await r.json();if(!files.length){LIST.innerHTML='<div class="empty">📭 还没传过文件，拖文件进来吧</div>';return;}LIST.innerHTML=files.map(f=>`<div class="file-item"><div class="file-info"><div class="file-name">${esc(f.name)}</div><div class="file-size">${f.size}</div></div><div class="file-actions"><a href="/download/${encodeURIComponent(f.name)}" class="btn-sm btn-dl">下载</a><button class="btn-sm btn-del" onclick="del('${esc(f.name)}')">删除</button></div></div>`).join('');}catch(e){}}

async function del(name){if(!confirm('删除 '+name+' ?'))return;const r=await fetch('/api/delete/'+encodeURIComponent(name),{method:'DELETE'});if(r.ok){toast('已删除');loadFiles();}}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}

loadFiles();

// ====== 遥控器 - 触摸板 ======
const PAD = document.getElementById('pad');
let touchMode = 'mouse'; // mouse | scroll
let lastX = 0, lastY = 0;
let moving = false;
let moveQueue = [];
let moveTimer = null;

function sendMove(dx, dy) {
  moveQueue.push([dx, dy]);
  if (!moveTimer) {
    moveTimer = setTimeout(flushMoves, 20);
  }
}

function flushMoves() {
  if (!moveQueue.length) { moveTimer = null; return; }
  const batch = moveQueue;
  moveQueue = [];
  moveTimer = null;
  const total = batch.reduce((acc, m) => [acc[0]+m[0], acc[1]+m[1]], [0,0]);
  fetch('/api/mouse/move', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dx:total[0], dy:total[1]})}).catch(()=>{});
}

function sendClick(btn) {
  fetch('/api/mouse/click', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({button:btn})}).catch(()=>{});
}

function sendScroll(delta) {
  fetch('/api/mouse/scroll', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta:delta})}).catch(()=>{});
}

PAD.addEventListener('touchstart', e => {
  e.preventDefault();
  const t = e.touches[0];
  lastX = t.clientX; lastY = t.clientY;
  PAD.classList.add('active');
});

PAD.addEventListener('touchmove', e => {
  e.preventDefault();
  const t = e.touches[0];
  const dx = (t.clientX - lastX) * 1.5;
  const dy = (t.clientY - lastY) * 1.5;
  lastX = t.clientX; lastY = t.clientY;
  if (touchMode === 'scroll') {
    sendScroll(Math.round(-dy));
  } else {
    sendMove(Math.round(dx), Math.round(dy));
  }
});

PAD.addEventListener('touchend', e => {
  e.preventDefault();
  PAD.classList.remove('active');
  flushMoves();
});

// 也支持鼠标（PC调试用）
PAD.addEventListener('mousemove', e => {
  if (!e.buttons) return;
  const dx = e.movementX || 0;
  const dy = e.movementY || 0;
  if (touchMode === 'scroll') {
    sendScroll(Math.round(-dy));
  } else {
    sendMove(Math.round(dx), Math.round(dy));
  }
});

// 按钮事件
document.getElementById('btnLeft').addEventListener('click', () => sendClick('left'));
document.getElementById('btnRight').addEventListener('click', () => sendClick('right'));

const btnScroll = document.getElementById('btnScroll');
btnScroll.addEventListener('click', () => {
  touchMode = touchMode === 'scroll' ? 'mouse' : 'scroll';
  btnScroll.textContent = touchMode === 'scroll' ? '↕️ 滚动模式(点我切回)' : '↕️ 上下滚动';
  btnScroll.classList.toggle('accent', touchMode === 'scroll');
});

// 键盘输入
const KEY_INPUT = document.getElementById('keyInput');
const BTN_SEND = document.getElementById('btnSend');

function sendText() {
  const text = KEY_INPUT.value;
  if (!text) return;
  KEY_INPUT.value = '';
  fetch('/api/key/type', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text})}).catch(()=>{});
  toast('已发送: ' + text.substring(0,20));
}

BTN_SEND.addEventListener('click', sendText);

KEY_INPUT.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    sendText();
  }
});

// 兼容手机输入法：监听 compositionend
KEY_INPUT.addEventListener('compositionend', () => {
  // 输入法组合完成，不做额外处理，等用户点发送或按回车
});

// 特殊按键
document.querySelectorAll('[data-key]').forEach(btn => {
  btn.addEventListener('click', () => {
    sendSpecialKey(btn.dataset.key);
  });
});

function sendSpecialKey(key) {
  fetch('/api/key/special', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key})}).catch(()=>{});
}

// Win键
document.getElementById('btnWin').addEventListener('click', () => {
  fetch('/api/key/special', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:'F1'})}).catch(()=>{});
  // 实际发送 Win键
  fetch('/api/key/win', {method:'POST'}).catch(()=>{});
});

// Alt+Tab
document.getElementById('btnAltTab').addEventListener('click', () => {
  fetch('/api/key/alttab', {method:'POST'}).catch(()=>{});
});

// 任务视图 Win+Tab
document.getElementById('btnTask').addEventListener('click', () => {
  fetch('/api/key/taskview', {method:'POST'}).catch(()=>{});
});
</script>
</body>
</html>
"""

# ====================== 服务端逻辑 ======================

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.client_address[0]}] {args[0]}")

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_html(self, html, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode() if isinstance(html, str) else html)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    # ============== GET ==============
    def do_GET(self):
        path = urllib.parse.unquote(self.path.split('?')[0])
        if path == '/' or path == '/index.html':
            self.send_html(INDEX_HTML)
        elif path == '/api/ip':
            self.send_json({'ip': get_local_ip(), 'port': PORT})
        elif path == '/api/files':
            files = []
            for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file():
                    files.append({'name': f.name, 'size': format_size(f.stat().st_size)})
            self.send_json(files)
        elif path.startswith('/download/'):
            filename = path[len('/download/'):]
            filepath = UPLOAD_DIR / filename
            if filepath.is_file() and filepath.resolve().parent == UPLOAD_DIR.resolve():
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filepath.name}"')
                self.send_header('Content-Length', str(filepath.stat().st_size))
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_json({'error': 'File not found'}, 404)
        else:
            self.send_json({'error': 'Not found'}, 404)

    # ============== POST ==============
    def do_POST(self):
        path = urllib.parse.unquote(self.path.split('?')[0])

        if path == '/upload':
            self.handle_upload()
        elif path == '/api/mouse/move':
            self.handle_mouse_move()
        elif path == '/api/mouse/click':
            self.handle_mouse_click()
        elif path == '/api/mouse/scroll':
            self.handle_mouse_scroll()
        elif path == '/api/key/type':
            self.handle_key_type()
        elif path == '/api/key/special':
            self.handle_key_special()
        elif path == '/api/key/win':
            send_key(VK_LWIN, True)
            send_key(VK_LWIN, False)
            self.send_json({'ok': True, 'action': 'win'})
        elif path == '/api/key/alttab':
            send_key(VK_MENU, True)
            send_key(VK_TAB, True)
            send_key(VK_TAB, False)
            send_key(VK_MENU, False)
            self.send_json({'ok': True, 'action': 'alttab'})
        elif path == '/api/key/taskview':
            send_key(VK_LWIN, True)
            send_key(VK_TAB, True)
            send_key(VK_TAB, False)
            send_key(VK_LWIN, False)
            self.send_json({'ok': True, 'action': 'taskview'})
        else:
            self.send_json({'error': 'Not found'}, 404)

    # ============== DELETE ==============
    def do_DELETE(self):
        path = urllib.parse.unquote(self.path.split('?')[0])
        if path.startswith('/api/delete/'):
            filename = path[len('/api/delete/'):]
            filepath = UPLOAD_DIR / filename
            if filepath.is_file() and filepath.resolve().parent == UPLOAD_DIR.resolve():
                filepath.unlink()
                self.send_json({'ok': True})
            else:
                self.send_json({'error': 'File not found'}, 404)
        else:
            self.send_json({'error': 'Not found'}, 404)

    # ============== 文件上传 ==============
    def handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_json({'error': 'Bad request'}, 400)
            return
        boundary = content_type.split('boundary=')[1].encode() if 'boundary=' in content_type else None
        if not boundary:
            self.send_json({'error': 'No boundary'}, 400)
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        parts = body.split(b'--' + boundary)
        for part in parts:
            if b'filename=' in part:
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1: continue
                header = part[:header_end].decode('utf-8', errors='ignore')
                file_data = part[header_end+4:]
                if file_data.endswith(b'\r\n'): file_data = file_data[:-2]
                fname = 'unknown'
                for line in header.split('\r\n'):
                    if 'filename=' in line:
                        fname = line.split('filename=')[1].strip('"')
                        break
                filepath = UPLOAD_DIR / fname
                with open(filepath, 'wb') as f:
                    f.write(file_data)
                self.send_json({'ok': True, 'name': fname})
                return
        self.send_json({'error': 'No file'}, 400)

    # ============== 鼠标操作 ==============
    def handle_mouse_move(self):
        try:
            data = json.loads(self.read_body())
            dx = int(data.get('dx', 0))
            dy = int(data.get('dy', 0))
            mouse_move(dx, dy)
            self.send_json({'ok': True, 'dx': dx, 'dy': dy})
        except Exception as e:
            self.send_json({'error': str(e)}, 400)

    def handle_mouse_click(self):
        try:
            data = json.loads(self.read_body())
            btn = data.get('button', 'left')
            mouse_click(btn)
            self.send_json({'ok': True, 'button': btn})
        except Exception as e:
            self.send_json({'error': str(e)}, 400)

    def handle_mouse_scroll(self):
        try:
            data = json.loads(self.read_body())
            delta = int(data.get('delta', 0))
            mouse_scroll(delta)
            self.send_json({'ok': True, 'delta': delta})
        except Exception as e:
            self.send_json({'error': str(e)}, 400)

    # ============== 键盘操作 ==============
    def handle_key_type(self):
        try:
            data = json.loads(self.read_body())
            text = data.get('text', '')
            type_text(text)
            self.send_json({'ok': True, 'text': text})
        except Exception as e:
            self.send_json({'error': str(e)}, 400)

    def handle_key_special(self):
        try:
            data = json.loads(self.read_body())
            key = data.get('key', '')
            vk = KEY_MAP.get(key)
            if vk:
                type_key(vk)
                self.send_json({'ok': True, 'key': key})
            else:
                self.send_json({'error': f'Unknown key: {key}'}, 400)
        except Exception as e:
            self.send_json({'error': str(e)}, 400)


if __name__ == '__main__':
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    HOST = '0.0.0.0'
    ip = get_local_ip()

    print(f"""
╔══════════════════════════════════════╗
║     局域网工具箱                    ║
║                                    ║
║  本机:  http://{ip}:{PORT}      ║
║  手机浏览器打开网页即可            ║
║                                    ║
║  文件传输 | 手机遥控              ║
║                                    ║
║  按 Ctrl+C 停止                    ║
╚══════════════════════════════════════╝
""")
    server = http.server.HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n👋 已停止')
        server.shutdown()
