import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FirebaseManager:
    _instance = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 檢查是否已經初始化
        try:
            firebase_admin.get_app()
            self._db = firestore.client()
            print("Firebase Admin SDK already initialized.")
            return
        except ValueError:
            pass

        # 優先從環境變數讀取 JSON 字串 (給 Vercel 使用)
        firebase_creds_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        
        if firebase_creds_json:
            try:
                # 強化 JSON 解析邏輯：處理 Vercel 可能的換行轉義與單引號問題
                clean_json = firebase_creds_json.strip()
                
                # 1. 處理常見的轉義換行
                clean_json = clean_json.replace('\\n', '\n')
                
                # 2. 如果 JSON 被單引號包圍，嘗試移除
                if clean_json.startswith("'") and clean_json.endswith("'"):
                    clean_json = clean_json[1:-1]
                
                try:
                    creds_dict = json.loads(clean_json)
                except json.JSONDecodeError as je:
                    # 如果基本解析失敗，可能是因為內部有真實換行導致格式損壞
                    # 嘗試把所有真實換行都換成 \n 再次嘗試
                    try:
                        # 只有在解析失敗時才嘗試這種暴力替換
                        brutal_json = clean_json.replace('\n', '\\n').replace('\r', '\\n')
                        creds_dict = json.loads(brutal_json)
                    except:
                        raise je # 如果還是失敗，丟出原始的 JSONDecodeError
                
                # 針對 private_key 內容進行二次清洗：處理被換成空格的換行符
                if "private_key" in creds_dict:
                    pk = creds_dict["private_key"]
                    # 如果金鑰中沒有換行符，但長度很長，很可能是原本的換行被變成了空格
                    if "-----BEGIN PRIVATE KEY-----" in pk and "\n" not in pk[30:-30]:
                        # 嘗試修復：將金鑰標籤中間的所有空格換回換行 (這是 PEM 的常見修復手段)
                        header = "-----BEGIN PRIVATE KEY-----"
                        footer = "-----END PRIVATE KEY-----"
                        if pk.startswith(header) and pk.endswith(footer + "\n"):
                             # 已經有換行的話就不動
                             pass
                        elif pk.startswith(header) and pk.endswith(footer):
                            inner = pk[len(header):-len(footer)].strip()
                            # 如果裡面全是空格分隔，試著把空格換回換行
                            if " " in inner:
                                fixed_inner = inner.replace(" ", "\n")
                                creds_dict["private_key"] = f"{header}\n{fixed_inner}\n{footer}\n"
                
                
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
                self._db = firestore.client()
                print("Firebase Admin SDK initialized from env variable.")
                return
            except Exception as e:
                print(f"Failed to initialize from env: {e}")
                # 額外偵錯：顯示字串前幾位確認格式 (不顯示私鑰以保安全)
                if firebase_creds_json:
                    print(f"Env string start with: {firebase_creds_json[:20]}...")

        # 次之尋找本地檔案
        key_path = "pk-draw-firebase-adminsdk-fbsvc-65d71e3f1c.json"
        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            self._db = firestore.client()
            print("Firebase Admin SDK initialized from file.")
        else:
            print("Error: No Firebase credentials found (neither env nor file).")

    @property
    def db(self):
        if self._db is None:
            raise Exception("Firebase Firestore 資料庫未成功初始化。請檢查 Vercel 環境變數 FIREBASE_SERVICE_ACCOUNT 是否為正確的單行 JSON 格式。")
        return self._db

    # --- Works Management ---
    def add_work(self, work_data):
        """Add or update a work in the 'works' collection."""
        work_id = str(work_data.get('id'))
        self.db.collection('works').document(work_id).set(work_data)

    def get_all_works(self):
        """Fetch all works from Firestore."""
        works_ref = self.db.collection('works')
        docs = works_ref.stream()
        return [doc.to_dict() for doc in docs]

    def clear_works(self):
        """Delete all works in the collection."""
        batch = self.db.batch()
        docs = self.db.collection('works').list_documents()
        for doc in docs:
            batch.delete(doc)
        batch.commit()

    # --- System State Management ---
    def get_system_state(self):
        """Retrieve the current system state."""
        doc = self.db.collection('system').document('current').get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_system_state(self, state_data):
        """Update the system state (e.g., status, match_A, match_B, system_id)."""
        self.db.collection('system').document('current').set(state_data, merge=True)

    # --- Voting ---
    def submit_vote(self, match_id, choice, team):
        """Log a vote in the 'votes' collection."""
        vote_data = {
            'match_id': match_id,
            'choice': choice, # 'A' or 'B'
            'team': team,     # 'red' or 'white' (voter's team)
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        self.db.collection('votes').add(vote_data)

    def get_votes_for_match(self, match_id):
        """Aggregate votes for a specific match ID."""
        votes_ref = self.db.collection('votes').where('match_id', '==', match_id)
        docs = votes_ref.stream()
        
        results = {'A': 0, 'B': 0}
        for doc in docs:
            data = doc.to_dict()
            results[data['choice']] += 1
        return results

    # --- History ---
    def add_history(self, round_data):
        """Archive a finished round."""
        self.db.collection('history').add(round_data)

# Singleton instance
firebase_manager = FirebaseManager()
