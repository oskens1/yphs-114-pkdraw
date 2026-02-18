import uvicorn
import os
import sys

# 取得目前檔案所在的目錄，並加入到 Python 路徑中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

if __name__ == "__main__":
    try:
        print("--- 系統啟動測試 ---")
        print(f"目前目錄: {os.getcwd()}")
        
        # 測試導入 main.py
        print("正在測試導入 main.py...")
        import main
        print("導入 main.py 成功！")
        
        # 啟動伺服器
        print("正在啟動 uvicorn...")
        uvicorn.run(main.app, host="127.0.0.1", port=8000)
        
    except Exception as e:
        print("\n❌ 啟動發生嚴重錯誤：")
        print("==============================")
        import traceback
        traceback.print_exc()
        print("==============================")
        print("\n請截圖以上錯誤訊息。")
        input("按任意鍵結束...")
