import os
import json
import random
import shutil
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional

try:
    from models import EloManager, WorkItem
    from pdf_utils import process_pdf
    from gsheet_manager import GSheetManager
    from cloudinary_manager import CloudinaryManager
except ImportError as e:
    print(f"Import Error: {e}")

app = FastAPI()

# 設定路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 在 Vercel 中，只有 /tmp 資料夾是可寫入的
IS_VERCEL = "VERCEL" in os.environ
if IS_VERCEL:
    UPLOAD_DIR = "/tmp/uploads"
    DATA_DIR = "/tmp/data"
else:
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
    DATA_DIR = os.path.join(BASE_DIR, "data")

DATA_FILE = os.path.join(DATA_DIR, "works.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# 確保目錄存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 掛載靜態文件 (供圖片讀取)
if os.path.exists(os.path.join(UPLOAD_DIR, "images")):
    app.mount("/static/uploads/images", StaticFiles(directory=os.path.join(UPLOAD_DIR, "images")), name="work_images")
if os.path.exists(UPLOAD_DIR):
    app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
if os.path.exists(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 修正 templates 目錄
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 版本資訊
APP_VERSION = "v1.2.3"
UPDATE_LOG = "修復 429 錯誤導致的同步卡死迴圈，並修正 Vercel 環境下的重設邏輯與阻塞問題。"

# 全域狀態
class State:
    works: List[WorkItem] = []
    current_match: Optional[dict] = None
    history: List[dict] = []
    last_picked_ids: List[str] = [] 
    debug_mode: bool = False
    
    # 系統識別碼，用於強制客戶端清除舊的投票快取
    system_id: str = "init"
    
    # 用於快取，減少對 GSheet 的頻繁讀取
    last_sync_time: float = 0
    sync_interval: int = 12 # 學生端每 12 秒同步一次
    data_loaded: bool = False
    last_load_attempt: float = 0 # 上次嘗試載入資料的時間
    
    gsheet = GSheetManager()
    cloudinary = CloudinaryManager()

state = State()

def save_data():
    try:
        state.gsheet.save_works(state.works)
    except Exception as e:
        print(f"Error saving works to GSheet: {e}")

def load_data():
    now = time.time()
    # 防止短時間內頻繁重試 (10秒冷卻)
    if now - state.last_load_attempt < 10:
        return
    state.last_load_attempt = now
    
    try:
        # 使用批次讀取優化 (1次 API 呼叫)
        data = state.gsheet.load_all_data()
        
        state.works = data["works"]
        state.history = data["history"]
        state.current_match = data["current_match"]
        sid = data["system_id"]
        
        # 同步 System ID
        if sid:
            state.system_id = sid
        else:
            state.system_id = str(int(time.time()))
            state.gsheet.save_system_id(state.system_id)

        # 如果 GSheet 為空且「非Vercel環境」，才嘗試從本地備份讀取並同步到 GSheet
        if not state.works and not IS_VERCEL and os.path.exists(DATA_FILE):
            print("GSheet is empty, loading from local backup...")
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                state.works = [WorkItem.from_dict(d) for d in local_data]
            save_data() # 同步到 GSheet
            
        state.data_loaded = True # 只有成功載入後才標記完成
        print(f"Data successfully loaded from GSheet (Batch). Works: {len(state.works)}")
    except Exception as e:
        print(f"Error loading data from GSheet: {e}")
        state.data_loaded = False # 標記為未完成，下次請求會再重試
        
        # 如果是本地環境且失敗，嘗試從本地備份讀取以便維持基本運作
        if not IS_VERCEL and not state.works and os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                state.works = [WorkItem.from_dict(d) for d in local_data]

@app.on_event("startup")
async def startup_event():
    pass

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not state.data_loaded:
        load_data()
    return templates.TemplateResponse("index.html", {"request": request, "works": state.works})

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not state.data_loaded:
        load_data()
    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "works": state.works, 
        "current_match": state.current_match,
        "version": APP_VERSION,
        "update_log": UPDATE_LOG
    })

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        extracted_images_dir = os.path.join(UPLOAD_DIR, "images")
        if os.path.exists(extracted_images_dir):
            shutil.rmtree(extracted_images_dir)
        os.makedirs(extracted_images_dir, exist_ok=True)
        
        try:
            temp_works = process_pdf(file_path, extracted_images_dir)
        except Exception as e:
            raise ValueError(f"PDF 處理失敗: {e}")
        
        total_works = len(temp_works)
        for i, work in enumerate(temp_works):
            img_filename = os.path.basename(work.image_url)
            local_img_path = os.path.join(extracted_images_dir, img_filename)
            if os.path.exists(local_img_path):
                print(f"Uploading image {i+1}/{total_works} to Cloudinary...")
                cloudinary_url = state.cloudinary.upload_image(local_img_path, work.id)
                if cloudinary_url:
                    work.image_url = cloudinary_url
            
        state.works = temp_works
        save_data()
        return JSONResponse({"status": "ok", "count": len(state.works)})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/next_round")
def next_round():
    if not state.data_loaded:
        load_data()

    if len(state.works) < 2:
        return JSONResponse({"error": "作品不足"}, status_code=400)
    
    available_works = [w for w in state.works if w.id not in state.last_picked_ids]
    if len(available_works) < 2:
        state.last_picked_ids = []
        available_works = state.works

    picked = random.sample(available_works, 2)
    state.current_match = {
        "A": picked[0].to_dict(),
        "B": picked[1].to_dict(),
        "votes": {"A": 0, "B": 0},
        "status": "voting"
    }
    
    state.last_picked_ids.extend([picked[0].id, picked[1].id])
    if len(state.last_picked_ids) > len(state.works) // 2:
        state.last_picked_ids = state.last_picked_ids[2:]
    
    try:
        state.gsheet.save_system_state(state.current_match)
        # 開啟新回合時清空舊投票紀錄
        state.gsheet.clear_votes_log()
        state.last_sync_time = time.time() # 標記已同步
    except Exception as e:
        print(f"Error saving system state: {e}")
        
    return JSONResponse(state.current_match)

@app.post("/vote")
def vote(choice: str = Form(...)):
    if not state.data_loaded:
        load_data()

    if not state.current_match or state.current_match["status"] != "voting":
        return JSONResponse({"error": "不在投票時間"}, status_code=400)
    
    if choice in ["A", "B"]:
        match_id = f"{state.current_match['A']['id']}_{state.current_match['B']['id']}"
        try:
            # 1. 寫入 GSheet
            state.gsheet.record_vote(match_id, choice)
            # 2. 更新記憶體
            state.current_match["votes"][choice] += 1
            return JSONResponse({"status": "ok"})
        except Exception as e:
            print(f"Vote Recording Error: {e}")
            return JSONResponse({"error": "投票紀錄失敗"}, status_code=500)
    return JSONResponse({"error": "無效選擇"}, status_code=400)

@app.post("/end_round")
def end_round():
    if not state.data_loaded:
        load_data()

    # 結束回合時，從 GSheet 取得最終正確票數
    try:
        current = state.gsheet.load_system_state()
        if current:
            match_id = f"{current['A']['id']}_{current['B']['id']}"
            current["votes"] = state.gsheet.get_votes_count(match_id)
            state.current_match = current
    except: pass

    if not state.current_match or state.current_match["status"] != "voting":
        return JSONResponse({"error": "沒有進行中的對戰"}, status_code=400)
    
    votes = state.current_match["votes"]
    winner = "A" if votes["A"] > votes["B"] else ("B" if votes["B"] > votes["A"] else random.choice(["A", "B"]))
    
    work_a = next(w for w in state.works if w.id == state.current_match["A"]["id"])
    work_b = next(w for w in state.works if w.id == state.current_match["B"]["id"])
    
    old_elo_a, old_elo_b = work_a.elo, work_b.elo
    new_elo_a, new_elo_b = EloManager.update_elo(old_elo_a, old_elo_b, winner)
    
    work_a.elo, work_a.match_count = int(new_elo_a), work_a.match_count + 1
    work_b.elo, work_b.match_count = int(new_elo_b), work_b.match_count + 1
    if winner == "A": work_a.win_count += 1
    else: work_b.win_count += 1
    
    state.current_match["status"] = "finished"
    state.current_match["winner"] = winner
    
    try:
        state.gsheet.save_system_state(state.current_match)
    except: pass

    history_entry = {
        "round": len(state.history) + 1,
        "A_id": work_a.id, "B_id": work_b.id,
        "votes": votes, "winner": winner,
        "elo_changes": {
            "A": {"old": old_elo_a, "new": new_elo_a},
            "B": {"old": old_elo_b, "new": new_elo_b}
        }
    }
    state.history.append(history_entry)
    save_data()
    try:
        state.gsheet.add_history(history_entry)
    except: pass
        
    return JSONResponse(state.current_match)

@app.get("/status")
def get_status():
    sync_ok = True
    now = time.time()
    try:
        if not state.data_loaded:
            load_data()
        
        if state.current_match is None or (now - state.last_sync_time > state.sync_interval):
            try:
                # 使用批次讀取優化 (1次 API 呼叫)
                current, sid = state.gsheet.load_status_data()
                state.current_match = current
                if sid: state.system_id = sid
            except Exception as e:
                print(f"Sync Inner Error: {e}")
                sync_ok = False
            finally:
                state.last_sync_time = now
    except Exception as e:
        print(f"Global Status Error: {e}")
        sync_ok = False

    return JSONResponse(
        content={
            "current_match": state.current_match,
            "round_count": len(state.history),
            "works": [w.to_dict() for w in state.works],
            "sync_ok": sync_ok,
            "debug_mode": state.debug_mode,
            "system_id": state.system_id
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )

@app.get("/admin_status")
def get_admin_status():
    """老師專用的即時狀態路由，繞過快取直接讀取 GSheet"""
    try:
        if not state.data_loaded:
            load_data()
        
        # 使用批次讀取優化 (1次 API 呼叫)
        current, sid = state.gsheet.load_status_data()
        
        state.current_match = current
        if sid: state.system_id = sid
        
        return JSONResponse(content={
            "current_match": state.current_match,
            "works": [w.to_dict() for w in state.works],
            "sync_ok": True,
            "system_id": state.system_id,
            "debug_mode": state.debug_mode
        })
    except Exception as e:
        return JSONResponse(content={"sync_ok": False, "message": str(e)}, status_code=500)

@app.post("/toggle_debug")
async def toggle_debug():
    state.debug_mode = not state.debug_mode
    return JSONResponse({"debug_mode": state.debug_mode})

@app.get("/test_sheet")
async def test_sheet():
    try:
        msg = state.gsheet.test_connection()
        return JSONResponse({"status": "ok", "message": msg})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/test_cloudinary")
async def test_cloudinary():
    try:
        test_path = os.path.join(UPLOAD_DIR, "test_conn.png")
        from PIL import Image
        Image.new('RGB', (10, 10), color = 'red').save(test_path)
        url = state.cloudinary.upload_image(test_path, "test_connection")
        return JSONResponse({"status": "ok", "url": url})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/export")
async def export_excel():
    import pandas as pd
    data = []
    sorted_works = sorted(state.works, key=lambda x: x.elo, reverse=True)
    for i, w in enumerate(sorted_works):
        data.append({
            "排名": i + 1, "作品ID": w.id, "Elo分數": w.elo,
            "對戰次數": w.match_count, "勝場數": w.win_count, "隊伍": w.team
        })
    df = pd.DataFrame(data)
    export_path = os.path.join(DATA_DIR, "results.xlsx")
    df.to_excel(export_path, index=False)
    return FileResponse(export_path, filename="results.xlsx")

@app.post("/reset")
def reset():
    state.works, state.current_match, state.history, state.last_picked_ids = [], None, [], []
    state.last_sync_time = 0 
    state.data_loaded = True
    state.system_id = str(int(time.time()))
    
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    
    extracted_images_dir = os.path.join(UPLOAD_DIR, "images")
    if os.path.exists(extracted_images_dir):
        shutil.rmtree(extracted_images_dir)
        os.makedirs(extracted_images_dir, exist_ok=True)

    try:
        state.gsheet.clear_all()
        # 同步 System ID 到雲端
        state.gsheet.save_system_id(state.system_id)
    except Exception as e:
        print(f"Reset GSheet Error: {e}")
        
    return JSONResponse({"status": "ok"})
