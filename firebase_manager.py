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
                except json.JSONDecodeError:
                    # 如果基本解析失敗，可能是因為 private_key 內部有真實換行導致格式損壞
                    # 嘗試修復常見的 Private Key 換行損壞問題 (Vercel 後台貼上時常發生)
                    if "private_key" in clean_json and "\\n" not in clean_json:
                         # 這種情況代表 JSON 裡的 \n 被當成真正的換行，導致 JSON 格式失效
                         pass # 交由外部 Exception 捕捉
                    raise
                
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
        return self._db

    # --- Works Management ---
    def add_work(self, work_data):
        """Add or update a work in the 'works' collection."""
        work_id = str(work_data.get('id'))
        self._db.collection('works').document(work_id).set(work_data)

    def get_all_works(self):
        """Fetch all works from Firestore."""
        works_ref = self._db.collection('works')
        docs = works_ref.stream()
        return [doc.to_dict() for doc in docs]

    def clear_works(self):
        """Delete all works in the collection."""
        batch = self._db.batch()
        docs = self._db.collection('works').list_documents()
        for doc in docs:
            batch.delete(doc)
        batch.commit()

    # --- System State Management ---
    def get_system_state(self):
        """Retrieve the current system state."""
        doc = self._db.collection('system').document('current').get()
        if doc.exists:
            return doc.to_dict()
        return None

    def update_system_state(self, state_data):
        """Update the system state (e.g., status, match_A, match_B, system_id)."""
        self._db.collection('system').document('current').set(state_data, merge=True)

    # --- Voting ---
    def submit_vote(self, match_id, choice, team):
        """Log a vote in the 'votes' collection."""
        vote_data = {
            'match_id': match_id,
            'choice': choice, # 'A' or 'B'
            'team': team,     # 'red' or 'white' (voter's team)
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        self._db.collection('votes').add(vote_data)

    def get_votes_for_match(self, match_id):
        """Aggregate votes for a specific match ID."""
        votes_ref = self._db.collection('votes').where('match_id', '==', match_id)
        docs = votes_ref.stream()
        
        results = {'A': 0, 'B': 0}
        for doc in docs:
            data = doc.to_dict()
            results[data['choice']] += 1
        return results

    # --- History ---
    def add_history(self, round_data):
        """Archive a finished round."""
        self._db.collection('history').add(round_data)

# Singleton instance
firebase_manager = FirebaseManager()
