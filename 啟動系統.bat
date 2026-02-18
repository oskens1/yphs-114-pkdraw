@echo off
chcp 65001 > nul
echo [1/3] 正在安裝必要套件...
python.exe -m pip install fastapi uvicorn pymupdf pandas openpyxl jinja2 python-multipart

echo.
echo [2/3] 正在建立測試 PDF (若已有 PDF 可略過)...
python.exe create_test_pdf.py

echo.
echo [3/3] 正在啟動系統...
echo --------------------------------------------------
echo 學生投票頁面: http://127.0.0.1:8000
echo 老師控制台:   http://127.0.0.1:8000/admin
echo --------------------------------------------------
:: 切換到檔案所在目錄
cd /d "%~dp0"
:: 直接啟動伺服器
python.exe run.py
echo Python 退出代碼: %errorlevel%
if %errorlevel% neq 0 (
    echo.
    echo 系統發生錯誤，請截圖上方錯誤訊息。
    pause
)
