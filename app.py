import os, sys, json, sqlite3, hashlib, shutil
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    STATIC_DIR = os.path.join(getattr(sys, '_MEIPASS', APP_DIR), 'static')
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(APP_DIR, 'static')
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
DB_PATH = os.path.join(APP_DIR, "awards.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            award_title TEXT,
            issuer TEXT,
            category TEXT,
            stamp_type TEXT,
            file_path TEXT,
            file_name TEXT,
            file_type TEXT,
            upload_date TEXT,
            notes TEXT,
            award_level TEXT,
            participant_count INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patent_title TEXT,
            patent_type TEXT,
            participant_count INTEGER DEFAULT 1,
            file_path TEXT,
            file_name TEXT,
            file_type TEXT,
            upload_date TEXT,
            notes TEXT
        )
    """)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(awards)").fetchall()}
    if "award_level" not in cols:
        conn.execute("ALTER TABLE awards ADD COLUMN award_level TEXT")
    if "participant_count" not in cols:
        conn.execute("ALTER TABLE awards ADD COLUMN participant_count INTEGER DEFAULT 1")
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def index():
    p = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>static/index.html not found</h1>"

@app.get("/manifest.json")
def manifest():
    p = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.loads(f.read()))
    return JSONResponse(content={})

@app.get("/icon.svg")
def icon_svg():
    p = os.path.join(STATIC_DIR, "icon.svg")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="image/svg+xml")
    return Response(content="", media_type="image/svg+xml")

@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    award_title: str = Form(""),
    issuer: str = Form(""),
    category: str = Form(""),
    stamp_type: str = Form(""),
    notes: str = Form(""),
    award_level: str = Form(""),
    participant_count: str = Form("1")
):
    ext = os.path.splitext(file.filename)[1].lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = hashlib.md5(f"{ts}_{file.filename}".encode()).hexdigest()[:12]
    saved_name = f"{safe_name}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        pc = int(participant_count) if participant_count else 1
    except (TypeError, ValueError):
        pc = 1
    if pc < 1:
        pc = 1
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO awards (award_title, issuer, category, stamp_type, file_path, file_name, file_type, upload_date, notes, award_level, participant_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (award_title, issuer, category, stamp_type, file_path, file.filename, ext, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), notes, award_level, pc)
    )
    conn.commit()
    award_id = cur.lastrowid
    conn.close()
    return JSONResponse({"id": award_id, "msg": "上传成功"})

@app.get("/api/awards")
def list_awards(
    search: Optional[str] = None,
    category: Optional[str] = None
):
    conn = get_db()
    q = "SELECT * FROM awards WHERE 1=1"
    params = []
    if search:
        q += " AND (award_title LIKE ? OR issuer LIKE ?)"
        kw = f"%{search}%"
        params += [kw, kw]
    if category:
        q += " AND category = ?"
        params.append(category)
    q += " ORDER BY upload_date DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return JSONResponse({"awards": [dict(r) for r in rows]})

@app.get("/api/categories")
def list_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM awards WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY count DESC"
    ).fetchall()
    conn.close()
    return JSONResponse({"categories": [dict(r) for r in rows]})

@app.get("/api/file/{award_id}")
def get_file(award_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM awards WHERE id=?", (award_id,)).fetchone()
    conn.close()
    if not row or not os.path.exists(row["file_path"]):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    return FileResponse(row["file_path"], filename=row["file_name"])

@app.delete("/api/awards/{award_id}")
def delete_award(award_id: int):
    conn = get_db()
    row = conn.execute("SELECT file_path FROM awards WHERE id=?", (award_id,)).fetchone()
    if row and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])
    conn.execute("DELETE FROM awards WHERE id=?", (award_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"msg": "已删除"})

@app.put("/api/awards/{award_id}")
async def update_award(award_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    fields = ["award_title", "issuer", "category", "stamp_type", "notes", "award_level", "participant_count"]
    sets = []
    params = []
    for f in fields:
        if f in data:
            val = data[f]
            if f == "participant_count":
                try:
                    val = int(val) if val else 1
                except (TypeError, ValueError):
                    val = 1
                if val < 1:
                    val = 1
            sets.append(f"{f}=?")
            params.append(val)
    if sets:
        params.append(award_id)
        conn.execute(f"UPDATE awards SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return JSONResponse({"msg": "已更新"})


# ============ 专利接口 ============

PATENT_TYPES = [
    "发明专利",
    "实用新型专利",
    "计算机软件著作权专利",
    "外观设计专利",
    "集成电路布图设计专有权",
]

@app.get("/api/patent/types")
def patent_types():
    return JSONResponse({"types": PATENT_TYPES})

@app.post("/api/patent/upload")
async def patent_upload(
    file: UploadFile = File(...),
    patent_title: str = Form(""),
    patent_type: str = Form(""),
    participant_count: str = Form("1"),
    notes: str = Form("")
):
    ext = os.path.splitext(file.filename)[1].lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = hashlib.md5(f"{ts}_{file.filename}".encode()).hexdigest()[:12]
    saved_name = f"pat_{safe_name}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        pc = int(participant_count) if participant_count else 1
    except (TypeError, ValueError):
        pc = 1
    if pc < 1:
        pc = 1
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO patents (patent_title, patent_type, participant_count, file_path, file_name, file_type, upload_date, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (patent_title, patent_type, pc, file_path, file.filename, ext, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), notes)
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return JSONResponse({"id": pid, "msg": "专利上传成功"})

@app.get("/api/patents")
def list_patents(
    search: Optional[str] = None,
    patent_type: Optional[str] = None
):
    conn = get_db()
    q = "SELECT * FROM patents WHERE 1=1"
    params = []
    if search:
        q += " AND (patent_title LIKE ? OR patent_type LIKE ?)"
        kw = f"%{search}%"
        params += [kw, kw]
    if patent_type:
        q += " AND patent_type = ?"
        params.append(patent_type)
    q += " ORDER BY upload_date DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return JSONResponse({"patents": [dict(r) for r in rows]})

@app.get("/api/patent/file/{pid}")
def get_patent_file(pid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM patents WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row or not os.path.exists(row["file_path"]):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    return FileResponse(row["file_path"], filename=row["file_name"])

@app.delete("/api/patents/{pid}")
def delete_patent(pid: int):
    conn = get_db()
    row = conn.execute("SELECT file_path FROM patents WHERE id=?", (pid,)).fetchone()
    if row and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])
    conn.execute("DELETE FROM patents WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return JSONResponse({"msg": "已删除"})

@app.put("/api/patents/{pid}")
async def update_patent(pid: int, request: Request):
    data = await request.json()
    conn = get_db()
    fields = ["patent_title", "patent_type", "participant_count", "notes"]
    sets = []
    params = []
    for f in fields:
        if f in data:
            val = data[f]
            if f == "participant_count":
                try:
                    val = int(val) if val else 1
                except (TypeError, ValueError):
                    val = 1
                if val < 1:
                    val = 1
            sets.append(f"{f}=?")
            params.append(val)
    if sets:
        params.append(pid)
        conn.execute(f"UPDATE patents SET {','.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return JSONResponse({"msg": "已更新"})


def _get_desktop_dir():
    user_home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    candidates = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "桌面"),
    ]
    for d in candidates:
        if os.path.isdir(d):
            return d
    return user_home


@app.post("/api/pack_all")
async def pack_all():
    desktop = _get_desktop_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"我的获奖文件_{ts}"
    folder_path = os.path.join(desktop, folder_name)
    awards_dir = os.path.join(folder_path, "奖状")
    patents_dir = os.path.join(folder_path, "专利")
    os.makedirs(awards_dir, exist_ok=True)
    os.makedirs(patents_dir, exist_ok=True)
    conn = get_db()
    awards_rows = conn.execute("SELECT * FROM awards").fetchall()
    patent_rows = conn.execute("SELECT * FROM patents").fetchall()
    conn.close()

    def _copy_unique(src, dst_dir, fname):
        base, ext = os.path.splitext(fname)
        dst = os.path.join(dst_dir, fname)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(dst_dir, f"{base}_{i}{ext}")
            i += 1
        shutil.copy2(src, dst)

    count = 0
    for r in awards_rows:
        fp = r["file_path"]
        if fp and os.path.exists(fp):
            fname = r["file_name"] or os.path.basename(fp)
            _copy_unique(fp, awards_dir, fname)
            count += 1
    for r in patent_rows:
        fp = r["file_path"]
        if fp and os.path.exists(fp):
            fname = r["file_name"] or os.path.basename(fp)
            _copy_unique(fp, patents_dir, fname)
            count += 1
    if count == 0:
        try:
            os.rmdir(awards_dir)
            os.rmdir(patents_dir)
            os.rmdir(folder_path)
        except Exception:
            pass
        return JSONResponse({"error": "没有可打包的文件"}, status_code=404)
    return JSONResponse({"msg": "打包成功", "count": count, "path": folder_path})


def open_browser_later(delay: float = 1.5):
    import threading, webbrowser
    def _open():
        import time
        time.sleep(delay)
        try:
            webbrowser.open(f"http://127.0.0.1:8091")
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def _port_in_use(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        log_path = os.path.join(APP_DIR, "运行日志.txt")
        try:
            sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
        except Exception:
            pass
        def _excepthook(exc_type, exc_value, exc_tb):
            import traceback
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
            except Exception:
                pass
        sys.excepthook = _excepthook
    HOST, PORT = "127.0.0.1", 8091
    if _port_in_use(HOST, PORT):
        try:
            import webbrowser
            webbrowser.open(f"http://{HOST}:{PORT}")
        except Exception:
            pass
        sys.exit(0)
    open_browser_later()
    uvicorn.run(app, host=HOST, port=PORT, reload=False)