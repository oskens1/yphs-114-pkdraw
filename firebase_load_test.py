import firebase_admin
from firebase_admin import credentials, firestore
import random
import time
import concurrent.futures
import os

# 初始化 Firebase (使用本地金鑰)
KEY_PATH = "pk-draw-firebase-adminsdk-fbsvc-65d71e3f1c.json"
if not os.path.exists(KEY_PATH):
    print(f"Error: {KEY_PATH} not found. Please make sure the key is in the folder.")
    exit(1)

cred = credentials.Certificate(KEY_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

def get_current_match():
    doc = db.collection('system').document('current').get()
    if doc.exists:
        data = doc.to_dict()
        if data.get('status') == 'voting':
            return data.get('match_id')
    return None

def send_vote(match_id):
    choice = random.choice(['A', 'B'])
    team = random.choice(['red', 'white'])
    try:
        db.collection('votes').add({
            'match_id': match_id,
            'choice': choice,
            'team': team,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Vote failed: {e}")
        return False

def main():
    print("=== PK Draw Firebase 壓力測試 ===")
    match_id = get_current_match()
    
    if not match_id:
        print("目前沒有進行中的對戰 (status 必須是 'voting')。")
        print("請先在管理後台點擊 '開始新回合'。")
        return

    num_votes = 100 # 模擬 100 次投票
    print(f"開始對 Match ID: {match_id} 進行 {num_votes} 次併發投票...")
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(send_vote, match_id) for _ in range(num_votes)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    end_time = time.time()
    success_count = sum(results)
    
    print(f"\n測試完成！")
    print(f"成功次數: {success_count}/{num_votes}")
    print(f"總耗時: {end_time - start_time:.2f} 秒")
    print(f"平均每秒處理: {success_count / (end_time - start_time):.2f} 次投票")
    print("\n請檢查管理後台的即時票數與進度條是否正確跳動。")

if __name__ == "__main__":
    main()
