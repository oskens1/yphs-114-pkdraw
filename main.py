import os
import json
import random
import shutil
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
# 在 Vercel 環境中，靜態文件由 vercel.json 路由處理，但為了本地開發仍保留掛載
if os.path.exists(os.path.join(UPLOAD_DIR, "images")):
    app.mount("/static/uploads/images", StaticFiles(directory=os.path.join(UPLOAD_DIR, "images")), name="work_images")
if os.path.exists(UPLOAD_DIR):
    app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
if os.path.exists(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 修正 templates 目錄，確保在 Vercel 中能正確找到
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 版本資訊
APP_VERSION = "v1.1.0"
UPDATE_LOG = "修復 Vercel 環境下的 PDF 圖片上傳路徑問題，並加入版本號顯示系統。"

# 全域狀態
class State:
    works: List[WorkItem] = []
    current_match: Optional[dict] = None
    history: List[dict] = []
    last_picked_ids: List[str] = [] # 避免短時間重複出現
    
    gsheet = GSheetManager()
    cloudinary = CloudinaryManager()

state = State()

def save_data():
    # 僅保存作品數據（如果需要全量覆蓋）
    try:
        state.gsheet.save_works(state.works)
    except Exception as e:
        print(f"Error saving works to GSheet: {e}")

def load_data():
    try:
        state.works = state.gsheet.load_works()
        state.history = state.gsheet.load_history()
    except Exception as e:
        print(f"Error loading data from GSheet: {e}")
        # Fallback to local if env not set (for local dev)
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                state.works = [WorkItem.from_dict(d) for d in data]

@app.on_event("startup")
async def startup_event():
    # 在 Vercel 中，我們不在啟動時加載數據，以避免啟動超時
    # 改為在第一次請求時加載，或在 API 內部加載
    pass

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not state.works:
        load_data()
    return templates.TemplateResponse("index.html", {"request": request, "works": state.works})

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if not state.works:
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
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # 處理 PDF 轉圖片
    extracted_images_dir = os.path.join(UPLOAD_DIR, "images")
    if os.path.exists(extracted_images_dir):
        shutil.rmtree(extracted_images_dir)
    os.makedirs(extracted_images_dir, exist_ok=True)
    
    temp_works = process_pdf(file_path, extracted_images_dir)
    
    # 上傳圖片到 Cloudinary 並更新 URL
    for work in temp_works:
        # 修正：直接從 extracted_images_dir 獲取圖片檔名
        img_filename = os.path.basename(work.image_url)
        local_img_path = os.path.join(extracted_images_dir, img_filename)
        
        if os.path.exists(local_img_path):
            print(f"Uploading {local_img_path} to Cloudinary...")
            cloudinary_url = state.cloudinary.upload_image(local_img_path, work.id)
            if cloudinary_url:
                work.image_url = cloudinary_url
            else:
                print(f"Failed to upload {work.id} to Cloudinary")
        else:
            print(f"File not found: {local_img_path}")
    
    state.works = temp_works
    save_data()
    return JSONResponse({"status": "ok", "count": len(state.works)})

@app.post("/next_round")
async def next_round():
    if len(state.works) < 2:
        return JSONResponse({"error": "作品不足"}, status_code=400)
    
    # 強制結束上一輪（如果忘了按紅色的話）
    if state.current_match and state.current_match["status"] == "voting":
        # 如果上一輪沒按結束，我們自動幫他結算 (可選，但這裡我們先簡單清除)
        pass

    # 策略：完全隨機，但排除「最近剛出現過」的作品
    available_works = [w for w in state.works if w.id not in state.last_picked_ids]
    
    # 如果剩餘作品不足 2 個，就重設排除名單
    if len(available_works) < 2:
        state.last_picked_ids = []
        available_works = state.works

    # 從可用作品中隨機抽選 2 個
    picked = random.sample(available_works, 2)
    state.current_match = {
        "A": picked[0].to_dict(),
        "B": picked[1].to_dict(),
        "votes": {"A": 0, "B": 0},
        "status": "voting"
    }
    
    # 更新最近出現列表
    state.last_picked_ids.append(picked[0].id)
    state.last_picked_ids.append(picked[1].id)
    if len(state.last_picked_ids) > len(state.works) // 2:
        state.last_picked_ids = state.last_picked_ids[2:]
        
    return JSONResponse(state.current_match)

@app.post("/vote")
async def vote(choice: str = Form(...)):
    if not state.current_match or state.current_match["status"] != "voting":
        return JSONResponse({"error": "不在投票時間"}, status_code=400)
    
    if choice in ["A", "B"]:
        state.current_match["votes"][choice] += 1
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "無效選擇"}, status_code=400)

@app.post("/end_round")
async def end_round():
    if not state.current_match or state.current_match["status"] != "voting":
        return JSONResponse({"error": "沒有進行中的對戰"}, status_code=400)
    
    votes = state.current_match["votes"]
    if votes["A"] == votes["B"]:
        winner = random.choice(["A", "B"]) # 平手隨機
    else:
        winner = "A" if votes["A"] > votes["B"] else "B"
    
    # 更新 Elo
    work_a = next(w for w in state.works if w.id == state.current_match["A"]["id"])
    work_b = next(w for w in state.works if w.id == state.current_match["B"]["id"])
    
    old_elo_a = work_a.elo
    old_elo_b = work_b.elo
    
    new_elo_a, new_elo_b = EloManager.update_elo(old_elo_a, old_elo_b, winner)
    
    # 確保分數有變化，若兩者實力相近且勝負符合預期，Elo 可能變動極小
    # 但為了教學回饋感，我們可以確保至少有 1 分的變動（可選）
    
    work_a.elo = int(new_elo_a)
    work_a.match_count += 1
    if winner == "A": work_a.win_count += 1
    
    work_b.elo = int(new_elo_b)
    work_b.match_count += 1
    if winner == "B": work_b.win_count += 1
    
    print(f"DEBUG: Round Result - Winner: {winner}")
    print(f"DEBUG: A({work_a.id}): {old_elo_a} -> {work_a.elo}")
    print(f"DEBUG: B({work_b.id}): {old_elo_b} -> {work_b.elo}")
    
    state.current_match["status"] = "finished"
    state.current_match["winner"] = winner
    
    # 紀錄歷史
    history_entry = {
        "round": len(state.history) + 1,
        "A_id": work_a.id,
        "B_id": work_b.id,
        "votes": votes,
        "winner": winner,
        "elo_changes": {
            "A": {"old": old_elo_a, "new": new_elo_a},
            "B": {"old": old_elo_b, "new": new_elo_b}
        }
    }
    state.history.append(history_entry)
    
    # 保存到 GSheet (同時保存作品狀態與新增歷史)
    save_data()
    try:
        state.gsheet.add_history(history_entry)
    except Exception as e:
        print(f"Error adding history to GSheet: {e}")
        
    return JSONResponse(state.current_match)

@app.get("/status")
async def get_status():
    return JSONResponse({
        "current_match": state.current_match,
        "round_count": len(state.history)
    })

@app.get("/export")
async def export_excel():
    import pandas as pd
    data = []
    # 排名
    sorted_works = sorted(state.works, key=lambda x: x.elo, reverse=True)
    for i, w in enumerate(sorted_works):
        data.append({
            "排名": i + 1,
            "作品ID": w.id,
            "Elo分數": w.elo,
            "對戰次數": w.match_count,
            "勝場數": w.win_count,
            "隊伍": w.team
        })
    
    df = pd.DataFrame(data)
    export_path = os.path.join(DATA_DIR, "results.xlsx")
    df.to_excel(export_path, index=False)
    return FileResponse(export_path, filename="results.xlsx")

@app.post("/reset")
async def reset():
    state.works = []
    state.current_match = None
    state.history = []
    state.last_picked_ids = []
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    # 也清除圖片
    img_dir = os.path.join(UPLOAD_DIR, "images")
    if os.path.exists(img_dir):
        import shutil
        shutil.rmtree(img_dir)
    return JSONResponse({"status": "ok"})
