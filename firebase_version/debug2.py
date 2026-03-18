import firebase_admin
from firebase_admin import credentials, firestore

KEY_PATH = "pk-draw-firebase-adminsdk-fbsvc-65d71e3f1c.json"
cred = credentials.Certificate(KEY_PATH)
try:
    app = firebase_admin.get_app('test2')
except ValueError:
    app = firebase_admin.initialize_app(cred, name='test2')
db = firestore.client(app=app)

doc = db.collection('system').document('current').get()
print(f"Exists: {doc.exists}")
if doc.exists:
    print(doc.to_dict())
