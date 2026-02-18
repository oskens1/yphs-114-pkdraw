# pk_draw 專案工作日誌 - 2026/02/18

## 📌 目前進度摘要
已完成本地端「兩兩比較投票系統（畫知紅白大對抗）」的開發，具備完整的 PDF 處理、Elo 計分、隨機 PK 與 UI 介面。

## 🛠️ 技術細節
- **後端架構**：FastAPI (Python)
- **核心算法**：Elo Rating (K=32)，具備最小 1 分變動的視覺回饋修正。
- **抽選邏輯**：排除最近出現的作品後隨機抽選，確保 5-30 件作品皆能公平出現。
- **UI 設計**：和風配色（米白背景 #e9e4d1, 深藍字 #004098, 深紅區塊 #c00010）。
- **資料儲存**：目前使用本地 `data/*.json` 儲存作品與對戰歷史；圖片存於 `uploads/images/`。

## 📂 檔案結構說明
- `main.py`: API 邏輯、靜態目錄掛載、對戰流程控制。
- `models.py`: EloManager 類別與 WorkItem 資料結構。
- `pdf_utils.py`: 使用 PyMuPDF (fitz) 將 PDF 轉為 2x 解析度之 PNG。
- `run.py`: 啟動腳本，具備路徑偵錯功能。
- `啟動系統.bat`: Windows 一鍵啟動環境 (自動安裝套件 + 啟動)。
- `templates/`: `index.html` (學生 PK 頁), `admin.html` (老師控制台)。

## 🚀 接下來的任務 (Vercel 移植計畫)
1.  **環境遷移**：將專案由桌面搬回 `pytool/pk_draw`。
2.  **資料庫轉型**：
    *   廢棄本地 `.json` 儲存，改接 **Google Sheets API** 或 **Supabase**，以便 Vercel 讀寫。
    *   需閱讀 `學生積分系統` 中的 GAS/Sheet 連動邏輯以保持資料一致性。
3.  **圖片雲端化**：
    *   Vercel 無法永久儲存圖片。需串接 **Cloudinary API** 或 **Google Drive API**。
    *   流程：本地 PDF 轉圖 -> 自動上傳雲端 -> 存網址到 Sheet。
4.  **Vercel 部署**：
    *   建立 `vercel.json` 設定檔。
    *   處理 Python Runtime 在雲端環境的相依性問題（特別是 PyMuPDF 可能需替換為 pdf2image 或處理底層庫）。
5.  **手把手教學需求**：
    *   Vercel 專案建立、環境變數 (Secrets) 設定。
    *   Git/GitHub 連動部署流程教學。

## ⚠️ 待解決/注意事項
- 確認 `PyMuPDF` 在 Vercel Serverless Function 上的相容性。
- 確定使用的 Vercel 網域 (yphs-114-106 或新申請)。
- 建立 Google Cloud Console 憑證以操作 Sheets。
