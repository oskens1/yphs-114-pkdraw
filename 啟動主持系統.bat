@echo off
chcp 65001 > nul
echo ==========================================
echo       紅白對抗賽 - 主持人啟動系統
echo ==========================================
echo.
echo [1/2] 正在啟動後端伺服器...
:: 使用剛才測試成功的 Anaconda Python
start /B C:\Users\osken\anaconda3\python.exe run.py

echo.
echo [2/2] 正在開啟老師控制台...
timeout /t 5 > nul
start http://127.0.0.1:8000/admin

echo.
echo ------------------------------------------
echo 系統已啟動！
echo.
echo 學生投票頁面: http://127.0.0.1:8000
echo 老師控制台:   http://127.0.0.1:8000/admin (已自動開啟)
echo ------------------------------------------
echo.
echo ※ 請保持本視窗不要關閉，否則系統會停止。
echo.
pause
