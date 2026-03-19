import os
import uuid
import random
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil

from firebase_manager import firebase_manager
from cloudinary_manager import CloudinaryManager
from pdf_utils import process_pdf
from models import WorkItem, EloManager

app = FastAPI(title="紅白對抗賽 Firebase 版")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cloudinary_mgr = CloudinaryManager()

UPLOAD_DIR = "uploads"
IMAGE_DIR = os.path.join(UPLOAD_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.get("/")
def student_page():
    return FileResponse("index.html")

@app.get("/admin")
def admin_page():
    return FileResponse("admin.html")

@app.post("/admin/reset")
async def reset_system():
    """重置系統：清空作品、投票紀錄與狀態"""
    try:
        firebase_manager.clear_works()
        # 清空 system 狀態
        initial_state = {
            "status": "waiting",
            "match_A": None,
            "match_B": None,
            "system_id": str(uuid.uuid4()),
            "round_number": 0
        }
        firebase_manager.update_system_state(initial_state)
        # 刪除本地上傳檔案
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        
        return {"status": "success", "message": "System reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """上傳 PDF，切割圖片，上傳 Cloudinary 並存入 Firebase"""
    try:
        # 1. 保存 PDF
        pdf_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. 處理 PDF (切割圖片)
        work_items = process_pdf(pdf_path, IMAGE_DIR)
        
        # 3. 上傳 Cloudinary 並更新 Firebase
        final_works = []
        for item in work_items:
            # 上傳到 Cloudinary
            public_id = f"work_{item.id}_{uuid.uuid4().hex[:6]}"
            cloud_url = cloudinary_mgr.upload_image(item.image_url, public_id)
            
            if cloud_url:
                item.image_url = cloud_url
                # 存入 Firebase
                firebase_manager.add_work(item.to_dict())
                final_works.append(item.to_dict())
        
        # 更新系統狀態為 ready
        firebase_manager.update_system_state({"status": "ready", "total_works": len(final_works)})
        
        return {"status": "success", "count": len(final_works)}
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/start_round")
async def start_round():
    """開始新回合：隨機抽出兩個作品進行對決"""
    try:
        works = firebase_manager.get_all_works()
        
        if len(works) < 2:
            raise HTTPException(status_code=400, detail="作品數量不足，無法開始回合")
        
        # 隨機挑選兩個不同的作品 (擂台模式，不分隊伍)
        work_a, work_b = random.sample(works, 2)
        
        state = firebase_manager.get_system_state()
        new_round_number = state.get('round_number', 0) + 1
        
        match_id = f"M{new_round_number:03d}_{uuid.uuid4().hex[:6]}"
        
        update_data = {
            "status": "voting",
            "match_A": work_a,
            "match_B": work_b,
            "match_id": match_id,
            "round_number": new_round_number,
            "start_time": str(uuid.uuid4()) # 用來觸發前端更新
        }
        firebase_manager.update_system_state(update_data)
        
        return {"status": "success", "match_id": match_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/end_round")
async def end_round():
    """結束回合：結算票數，更新 ELO，存入歷史紀錄"""
    try:
        state = firebase_manager.get_system_state()
        if state['status'] != 'voting':
            raise HTTPException(status_code=400, detail="No active round to end")
        
        match_id = state['match_id']
        votes = firebase_manager.get_votes_for_match(match_id)
        
        # 判斷勝者
        winner = 'A' if votes['A'] >= votes['B'] else 'B'
        
        # 更新 ELO
        work_a_data = state['match_A']
        work_b_data = state['match_B']
        
        new_elo_a, new_elo_b = EloManager.update_elo(
            work_a_data['elo'], 
            work_b_data['elo'], 
            winner
        )
        
        # 更新作品資料
        work_a_data['elo'] = new_elo_a
        work_a_data['match_count'] += 1
        if winner == 'A': work_a_data['win_count'] += 1
        
        work_b_data['elo'] = new_elo_b
        work_b_data['match_count'] += 1
        if winner == 'B': work_b_data['win_count'] += 1
        
        firebase_manager.add_work(work_a_data)
        firebase_manager.add_work(work_b_data)
        
        # 存入歷史
        history_entry = {
            "match_id": match_id,
            "round_number": state['round_number'],
            "work_A": work_a_data,
            "work_B": work_b_data,
            "votes": votes,
            "winner": winner,
            "timestamp": str(uuid.uuid4())
        }
        firebase_manager.add_history(history_entry)
        
        # 更新系統狀態為展示結果 (或回到 ready)
        firebase_manager.update_system_state({
            "status": "result", 
            "last_result": history_entry
        })
        
        return {"status": "success", "result": history_entry}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
