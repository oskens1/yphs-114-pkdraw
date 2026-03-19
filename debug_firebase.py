import firebase_admin
from firebase_admin import credentials, firestore
import os

# 初始化 Firebase
KEY_PATH = "pk-draw-firebase-adminsdk-fbsvc-65d71e3f1c.json"
cred = credentials.Certificate(KEY_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

def debug_system_state():
    print("--- Debug System State ---")
    docs = db.collection('system').stream()
    for doc in docs:
        print(f"Document ID: {doc.id} => {doc.to_dict()}")
    
    print("\n--- Debug Works ---")
    works = db.collection('works').limit(5).stream()
    for work in works:
        print(f"Work ID: {work.id} => {work.to_dict()}")

if __name__ == "__main__":
    debug_system_state()
