import sys
import os

# 將父目錄加入 sys.path，以便導入根目錄的模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Vercel 要求的 entry point
# 不需要額外程式碼，FastAPI 的 app 實例會由 @vercel/python 自動掛載
