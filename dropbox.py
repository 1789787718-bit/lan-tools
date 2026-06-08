#!/usr/bin/env python3
"""
局域网工具箱 — 文件传输 + 手机遥控(触摸板+键盘)
手机浏览器打开即可用，无需安装 App
"""

import http.server
from http.server import ThreadingHTTPServer
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
# 媒体键
VK_MEDIA_PLAY_PAUSE  = 0xB3
VK_MEDIA_NEXT_TRACK  = 0xB0
VK_MEDIA_PREV_TRACK  = 0xB1
VK_VOLUME_UP         = 0xAF
VK_VOLUME_DOWN       = 0xAE
VK_VOLUME_MUTE       = 0xAD

KEY_MAP = {
    'Enter': VK_RETURN, 'Backspace': VK_BACK, 'Tab': VK_TAB, 'Escape': VK_ESCAPE,
    'Space': VK_SPACE, ' ': VK_SPACE,
    'ArrowLeft': VK_LEFT, 'ArrowUp': VK_UP, 'ArrowRight': VK_RIGHT, 'ArrowDown': VK_DOWN,
    'Delete': VK_DELETE, 'Home': VK_HOME, 'End': VK_END,
    'MediaPlayPause': VK_MEDIA_PLAY_PAUSE,
    'MediaNextTrack': VK_MEDIA_NEXT_TRACK,
    'MediaPrevTrack': VK_MEDIA_PREV_TRACK,
    'VolumeUp': VK_VOLUME_UP,
    'VolumeDown': VK_VOLUME_DOWN,
    'VolumeMute': VK_VOLUME_MUTE,
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
<title>工具箱 v2.3</title>
<style>
:root{--bg:#0f0f0f;--card:#1a1a1a;--accent:#4dabf7;--text:#e0e0e0;--sub:#888;--danger:#ff6b6b;--border:#2a2a2a;--green:#51cf66;}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:100%;height:100%;overflow:hidden;position:fixed;touch-action:none;}
body{font-family:-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text);padding:16px;padding-bottom:100px;overflow-y:auto;}
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

.file-list{display:flex;flex-direction:column;gap:8px;overflow-y:auto;max-height:calc(100vh - 200px);}
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
.mouse-layout{display:flex;gap:10px;height:55vh;}
.pad{background:var(--card);border:2px solid var(--border);border-radius:16px;touch-action:none;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:0.9rem;user-select:none;-webkit-user-select:none;flex:1;height:100%;}
.pad.active{border-color:var(--accent);}
.pad.clicking{border-color:var(--green);}
.mouse-buttons{width:90px;display:flex;flex-direction:column;gap:8px;}
.mouse-btn{flex:1;border:none;border-radius:12px;background:var(--card);color:var(--text);font-size:0.95rem;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;transition:background .1s;border:1px solid var(--border);}
.mouse-btn:active,.mouse-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);}
.mouse-btn.drag-btn:active,.mouse-btn.drag-btn.active{background:var(--green);color:#000;border-color:var(--green);}
.btn-row{display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;}
.btn-r{padding:12px 0;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:0.9rem;cursor:pointer;flex:1;min-width:60px;text-align:center;}
.btn-r:active{background:var(--accent);}
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
  <div class="btn-row" style="margin-bottom:10px;">
    <button class="btn-r" id="btnFullscreen" style="font-size:0.8rem;">📺 全屏</button>
    <button class="btn-r" id="btnWakeLock" style="font-size:0.8rem;">💡 常亮:关</button>
  </div>
  <div class="mouse-layout">
    <div class="pad" id="pad">👆 单指移 | 点=左键 | 双点=双击 | 长按=拖 | 双指=滚</div>
    <div class="mouse-buttons">
      <button class="mouse-btn" id="btnRight" style="height:100%;">右键</button>
    </div>
  </div>
  <!-- 灵敏度预设 -->
  <div class="btn-row" style="margin-top:10px;" id="sensRow">
    <button class="btn-r sens" data-s="1">🎯 精准</button>
    <button class="btn-r sens" data-s="1.5">🐢 慢</button>
    <button class="btn-r sens active" data-s="2">🐇 标准</button>
    <button class="btn-r sens" data-s="3">🚀 快</button>
    <button class="btn-r sens" data-s="5">⚡ 疯狂</button>
  </div>
  <!-- 媒体控制 -->
  <div class="btn-row" style="margin-top:10px;">
    <button class="btn-r" data-key="MediaPrevTrack">⏮</button>
    <button class="btn-r accent" data-key="MediaPlayPause">⏯</button>
    <button class="btn-r" data-key="MediaNextTrack">⏭</button>
    <button class="btn-r" data-key="VolumeDown">🔉</button>
    <button class="btn-r" data-key="VolumeMute">🔇</button>
    <button class="btn-r" data-key="VolumeUp">🔊</button>
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

// ====== 全局：禁止页面滚动 ======
document.addEventListener('touchmove', function(e) { e.preventDefault(); }, {passive: false});

// ====== 全屏切换 ======
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(function(){});
  } else {
    document.exitFullscreen().catch(function(){});
  }
}
document.getElementById('btnFullscreen').addEventListener('click', toggleFullscreen);
document.addEventListener('fullscreenchange', function() {
  var btn = document.getElementById('btnFullscreen');
  btn.textContent = document.fullscreenElement ? '❌ 退出全屏' : '📺 全屏';
});

// ====== 屏幕常亮 ======
var wakeLock = null;
var wakeLockOn = false;
var btnWake = document.getElementById('btnWakeLock');
btnWake.addEventListener('click', async function() {
  if (wakeLockOn) {
    if (wakeLock) { wakeLock.release(); wakeLock = null; }
    wakeLockOn = false;
    btnWake.textContent = '💡 常亮:关';
    toast('常亮已关闭');
  } else {
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLockOn = true;
      btnWake.textContent = '💡 常亮:开';
      toast('屏幕常亮已开启');
      wakeLock.addEventListener('release', function() {
        wakeLockOn = false;
        btnWake.textContent = '💡 常亮:关';
      });
    } catch(e) {
      toast('当前浏览器不支持常亮');
    }
  }
});

// ====== 遥控器 - 触摸板 ======
const PAD = document.getElementById('pad');
let lastX = 0, lastY = 0;
let moveAccX = 0, moveAccY = 0;
let moveTimer = null;
const MOVE_DEADZONE = 1;
const MOVE_INTERVAL = 8; // 125Hz
var sending = false;

function flushMoves() {
  moveTimer = null;
  if (sending) return;
  var dx = Math.round(moveAccX);
  var dy = Math.round(moveAccY);
  moveAccX = 0; moveAccY = 0;
  if (Math.abs(dx) + Math.abs(dy) < MOVE_DEADZONE) return;
  sending = true;
  fetch('/api/mouse/move', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dx, dy})})
    .finally(function(){ sending = false; });
}

function scheduleFlush() {
  if (!moveTimer) moveTimer = setTimeout(flushMoves, MOVE_INTERVAL);
}

function sendClick(btn) {
  fetch('/api/mouse/click', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({button:btn})}).catch(function(){});
}

function sendScroll(delta) {
  fetch('/api/mouse/scroll', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta:delta})}).catch(function(){});
}

// ====== 灵敏度预设按钮 ======
var sensitivity = parseFloat(localStorage.getItem('mouse_sensitivity')) || 2.0;

document.querySelectorAll('.sens').forEach(function(btn) {
  var val = parseFloat(btn.dataset.s);
  if (val === sensitivity) btn.classList.add('active');
  btn.addEventListener('click', function() {
    sensitivity = val;
    localStorage.setItem('mouse_sensitivity', sensitivity);
    document.querySelectorAll('.sens').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    toast(btn.textContent.trim() + ' (x' + sensitivity.toFixed(1) + ')');
  });
});

// ====== 手势系统 ======
var isScrolling = false;
var lastMidX = 0, lastMidY = 0;
var moved = false;
var touchStartTime = 0;
var longPressTimer = null;
var tapTimer = null;
var tapCount = 0;
var dragging = false;

function applyAccel(dx, dy) {
  var speed = Math.sqrt(dx*dx + dy*dy);
  var factor = 1;
  if (speed > 10) factor = 1.5;
  if (speed > 25) factor = 2;
  if (speed > 50) factor = 3;
  if (speed > 80) factor = 4;
  factor *= sensitivity;
  return [dx * factor, dy * factor];
}

PAD.addEventListener('touchstart', function(e) {
  e.preventDefault();
  var now = Date.now();
  if (e.touches.length >= 2) {
    // 双指 = 滚动
    isScrolling = true; moved = true; dragging = false;
    clearTimeout(longPressTimer); clearTimeout(tapTimer);
    var t0 = e.touches[0], t1 = e.touches[1];
    lastMidX = (t0.clientX + t1.clientX) / 2;
    lastMidY = (t0.clientY + t1.clientY) / 2;
    PAD.classList.add('active');
  } else {
    // 单指
    isScrolling = false; moved = false; touchStartTime = now;
    var t = e.touches[0];
    lastX = t.clientX; lastY = t.clientY;
    PAD.classList.add('active');
    // 长按 300ms = 按住左键（拖拽）
    longPressTimer = setTimeout(function() {
      if (!moved) { sendDown('left'); dragging = true; PAD.classList.add('clicking'); }
    }, 300);
  }
}, {passive: false});

PAD.addEventListener('touchmove', function(e) {
  e.preventDefault();
  if (e.touches.length >= 2) {
    var t0 = e.touches[0], t1 = e.touches[1];
    var midY = (t0.clientY + t1.clientY) / 2;
    var dy = (lastMidY - midY) * 5;
    lastMidY = midY;
    if (Math.abs(dy) > 0) sendScroll(Math.round(dy));
  } else if (e.touches.length === 1) {
    var t = e.touches[0];
    var dx = t.clientX - lastX;
    var dy = t.clientY - lastY;
    lastX = t.clientX; lastY = t.clientY;
    if (Math.abs(dx) > 0 || Math.abs(dy) > 0) moved = true;
    if (dragging) return; // 拖拽时不动鼠标，靠系统按住移动
    var acc = applyAccel(dx, dy);
    moveAccX += acc[0];
    moveAccY += acc[1];
    scheduleFlush();
  }
}, {passive: false});

PAD.addEventListener('touchend', function(e) {
  e.preventDefault();
  clearTimeout(longPressTimer);
  if (dragging) { sendUp('left'); dragging = false; PAD.classList.remove('clicking'); }
  if (e.touches.length === 0) {
    PAD.classList.remove('active', 'clicking');
    isScrolling = false;
    flushMoves();
    // 判断 tap/双击
    if (!moved && !dragging) {
      var elapsed = Date.now() - touchStartTime;
      if (elapsed < 200) {
        tapCount++;
        if (tapCount === 1) {
          tapTimer = setTimeout(function() {
            sendClick('left'); // 单击 = 左键
            tapCount = 0;
          }, 250);
        } else if (tapCount >= 2) {
          clearTimeout(tapTimer);
          sendClick('left'); sendClick('left'); // 双击
          tapCount = 0;
        }
      }
    } else {
      tapCount = 0;
    }
  } else if (e.touches.length === 1 && isScrolling) {
    isScrolling = false;
    var t = e.touches[0];
    lastX = t.clientX; lastY = t.clientY;
  }
}, {passive: false});

// PC鼠标调试
PAD.addEventListener('mousemove', function(e) {
  if (!e.buttons) return;
  var dx = e.movementX || 0;
  var dy = e.movementY || 0;
  moveAccX += dx;
  moveAccY += dy;
  scheduleFlush();
});

// ====== 侧边栏按钮：按下保持 ======
function sendDown(btn) {
  fetch('/api/mouse/down', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({button:btn})}).catch(function(){});
}
function sendUp(btn) {
  fetch('/api/mouse/up', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({button:btn})}).catch(function(){});
}

function bindBtn(id, btnType) {
  var el = document.getElementById(id);
  var active = false;
  el.addEventListener('touchstart', function(e) {
    e.preventDefault();
    sendDown(btnType);
    el.classList.add('active');
    active = true;
  });
  el.addEventListener('touchend', function(e) {
    e.preventDefault();
    if (active) { sendUp(btnType); el.classList.remove('active'); active = false; }
  });
  el.addEventListener('touchcancel', function(e) {
    if (active) { sendUp(btnType); el.classList.remove('active'); active = false; }
  });
  // PC 鼠标调试
  el.addEventListener('mousedown', function(e) { e.preventDefault(); sendDown(btnType); el.classList.add('active'); });
  el.addEventListener('mouseup', function(e) { e.preventDefault(); sendUp(btnType); el.classList.remove('active'); });
  el.addEventListener('mouseleave', function(e) { if (active) { sendUp(btnType); el.classList.remove('active'); active = false; } });
}

bindBtn('btnRight', 'right');

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
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        print(f"[{self.client_address[0]}] {args[0]}")

    def _send_headers(self, code=200, content_type=None):
        self.send_response(code)
        if content_type:
            self.send_header('Content-Type', content_type)
        self.send_header('Connection', 'keep-alive')
        self.send_header('Keep-Alive', 'timeout=5, max=100')
        self.end_headers()

    def _send_no_content(self):
        """204 无正文 — 遥控器高频请求用"""
        self.send_response(204)
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

    def send_json(self, data, code=200):
        self._send_headers(code, 'application/json')
        self.wfile.write(json.dumps(data).encode())

    def send_html(self, html, code=200):
        self._send_headers(code, 'text/html; charset=utf-8')
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
                fsize = filepath.stat().st_size
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filepath.name}"')
                self.send_header('Content-Length', str(fsize))
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(1024*1024)
                        if not chunk: break
                        self.wfile.write(chunk)
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
        elif path == '/api/mouse/down':
            self.handle_mouse_down()
        elif path == '/api/mouse/up':
            self.handle_mouse_up()
        elif path == '/api/mouse/scroll':
            self.handle_mouse_scroll()
        elif path == '/api/key/type':
            self.handle_key_type()
        elif path == '/api/key/special':
            self.handle_key_special()
        elif path == '/api/key/win':
            send_key(VK_LWIN, True)
            send_key(VK_LWIN, False)
            self._send_no_content()
        elif path == '/api/key/alttab':
            send_key(VK_MENU, True)
            send_key(VK_TAB, True)
            send_key(VK_TAB, False)
            send_key(VK_MENU, False)
            self._send_no_content()
        elif path == '/api/key/taskview':
            send_key(VK_LWIN, True)
            send_key(VK_TAB, True)
            send_key(VK_TAB, False)
            send_key(VK_LWIN, False)
            self._send_no_content()
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

    # ============== 文件上传（流式写入，不爆内存）==============
    def handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_json({'error': 'Bad request'}, 400)
            return
        # 提取 boundary
        bkey = b'boundary='
        idx = content_type.find('boundary=')
        if idx == -1:
            self.send_json({'error': 'No boundary'}, 400)
            return
        boundary = content_type[idx+len('boundary='):].encode()
        total = int(self.headers.get('Content-Length', 0))
        # 读头部（最多 8KB）
        head = b''
        head_size = min(8192, total)
        while len(head) < head_size:
            chunk = self.rfile.read(min(1024, head_size - len(head)))
            if not chunk: break
            head += chunk
            total -= len(chunk)
            if b'\r\n\r\n' in head:
                break
        # 解析文件名
        fname = 'unknown'
        for line in head.decode('utf-8', errors='ignore').split('\r\n'):
            if 'filename=' in line:
                fname = line.split('filename=')[1].strip('"').split('"')[0]
                break
        # 文件数据起点
        data_start = head.find(b'\r\n\r\n')
        if data_start == -1:
            self.send_json({'error': 'Parse error'}, 400)
            return
        tail_marker = b'\r\n--' + boundary + b'--'
        tail_len = len(tail_marker) + 2  # + \r\n
        filepath = UPLOAD_DIR / fname
        with open(filepath, 'wb') as f:
            # 头部尾部（已越过 \r\n\r\n 的部分）
            after_head = head[data_start+4:]
            f.write(after_head)
            # 流式读取剩余
            while total > 0:
                size = min(1024*1024, total)
                data = self.rfile.read(size)
                if not data: break
                total -= len(data)
                # 最后一块：裁剪尾部 boundary
                if total == 0:
                    idx = data.rfind(tail_marker)
                    if idx != -1:
                        data = data[:idx]
                    elif data.endswith(b'\r\n'):
                        data = data[:-2]
                f.write(data)
        self.send_json({'ok': True, 'name': fname})

    # ============== 鼠标操作 ==============
    def handle_mouse_move(self):
        try:
            data = json.loads(self.read_body())
            dx = int(data.get('dx', 0))
            dy = int(data.get('dy', 0))
            if dx or dy:
                mouse_move(dx, dy)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    def handle_mouse_click(self):
        try:
            data = json.loads(self.read_body())
            btn = data.get('button', 'left')
            mouse_click(btn)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    def handle_mouse_scroll(self):
        try:
            data = json.loads(self.read_body())
            delta = int(data.get('delta', 0))
            mouse_scroll(delta)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    def handle_mouse_down(self):
        try:
            data = json.loads(self.read_body())
            btn = data.get('button', 'left')
            mouse_down(btn)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    def handle_mouse_up(self):
        try:
            data = json.loads(self.read_body())
            btn = data.get('button', 'left')
            mouse_up(btn)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    # ============== 键盘操作 ==============
    def handle_key_type(self):
        try:
            data = json.loads(self.read_body())
            text = data.get('text', '')
            type_text(text)
            self._send_no_content()
        except Exception:
            self._send_no_content()

    def handle_key_special(self):
        try:
            data = json.loads(self.read_body())
            key = data.get('key', '')
            vk = KEY_MAP.get(key)
            if vk:
                type_key(vk)
            self._send_no_content()
        except Exception:
            self._send_no_content()


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
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n👋 已停止')
        server.shutdown()
