#!/usr/bin/env python3
# 二猫工作台 · 本地预览服务器（实时刷新版）
# - 文件一改动，浏览器/手机自动刷新（无需手动 Cmd+R）
# - 监听 0.0.0.0，同一 Wi-Fi 下的手机也能直接打开
# - 禁用缓存，避免"改了看不到"
import hashlib
import os
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PREVIEW_PORT", "8766"))
HOST = os.environ.get("PREVIEW_HOST", "0.0.0.0")
WATCH_DIRS = ["assets", "assets/stickers", "assets/jn"]
_stamp_cache = {"v": None, "t": 0}

RELOAD_SCRIPT = b"""
<script>
(function(){
  var first = null;
  async function check(){
    try{
      var r = await fetch('/__stamp?_=' + Date.now(), {cache:'no-store'});
      var v = (await r.text()).trim();
      if(first === null){ first = v; return; }
      if(v !== first){ location.reload(); }
    }catch(e){}
  }
  setInterval(check, 700);
  document.addEventListener('visibilitychange', function(){ if(!document.hidden) check(); });
})();
</script>
"""


def stamp():
    """index.html + 资源目录的内容指纹（mtime 与体积），用于判断是否有改动。"""
    now = time.time()
    if _stamp_cache["v"] and now - _stamp_cache["t"] < 0.4:
        return _stamp_cache["v"]
    h = hashlib.sha1()
    for rel in ["index.html"]:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            st = os.stat(p)
            h.update(f"{rel}:{st.st_mtime_ns}:{st.st_size}".encode())
    for d in WATCH_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        try:
            for name in sorted(os.listdir(dp)):
                fp = os.path.join(dp, name)
                if os.path.isfile(fp):
                    st = os.stat(fp)
                    h.update(f"{d}/{name}:{st.st_mtime_ns}:{st.st_size}".encode())
        except OSError:
            pass
    _stamp_cache["v"] = h.hexdigest()
    _stamp_cache["t"] = now
    return _stamp_cache["v"]


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/__stamp":
            body = stamp().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    data = f.read()
            except OSError:
                return super().do_GET()
            data = data.replace(b"</body>", RELOAD_SCRIPT + b"</body>") if b"</body>" in data \
                else data + RELOAD_SCRIPT
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # 静默，避免刷屏


if __name__ == "__main__":
    import socket

    lan = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan = s.getsockname()[0]
        s.close()
    except OSError:
        pass
    print("二猫工作台 · 实时预览已启动")
    print(f"  电脑浏览器：http://127.0.0.1:{PORT}/index.html")
    print(f"  手机（同 Wi-Fi）：http://{lan}:{PORT}/index.html")
    print("  改动保存后 1 秒内自动刷新；关闭本窗口即停止服务")
    ThreadingHTTPServer((HOST, PORT), PreviewHandler).serve_forever()
