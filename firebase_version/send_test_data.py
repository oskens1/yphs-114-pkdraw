import firebase_admin
from firebase_admin import credentials, firestore
import os

KEY_PATH = "pk-draw-firebase-adminsdk-fbsvc-65d71e3f1c.json"

if not os.path.exists(KEY_PATH):
    print(f"Error: {KEY_PATH} not found.")
    exit(1)

cred = credentials.Certificate(KEY_PATH)

try:
    app = firebase_admin.get_app('test_app')
except ValueError:
    app = firebase_admin.initialize_app(cred, name='test_app')

db = firestore.client(app=app)

def main():
    print("Writing test data to Firestore...")
    try:
        db.collection('test_collection').document('test_doc').set({'message': 'Hello from local test!'})
        print("Data written successfully.")
    except Exception as e:
        print(f"Failed to write data: {e}")

if __name__ == "__main__":
    main()
