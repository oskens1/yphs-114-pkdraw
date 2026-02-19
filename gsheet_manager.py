import os
import json
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
from models import WorkItem

class GSheetManager:
    def __init__(self):
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.credentials_json = os.getenv("GOOGLE_CREDENTIALS")
        self.client = None
        self.sheet = None

    def _get_client(self):
        if self.client is None:
            if not self.credentials_json:
                raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
            
            try:
                # 終極解析邏輯 v2：應對 Vercel 的各種轉義地獄
                json_str = self.credentials_json.strip()
                
                # 1. 嘗試基本解析
                try:
                    creds_dict = json.loads(json_str)
                except json.JSONDecodeError:
                    # 如果基本解析失敗，可能是因為裡面有真實換行符號
                    # 嘗試將真實換行替換回 \n 再解析
                    fixed_json = json_str.replace('\n', '\\n').replace('\r', '')
                    # 但這樣會把 JSON 結構也弄壞，所以更保險的做法是讓使用者重新貼上
                    raise ValueError("JSON 格式不合法，請確認貼上的是 Vercel 後台的一整行完整 JSON (包含 {})")

                # 2. 針對 private_key 進行「暴力還原」
                if "private_key" in creds_dict:
                    pk = creds_dict["private_key"]
                    # 處理各種可能的轉義組合：\\n, \n, 以及真實的換行
                    pk = pk.replace('\\\\n', '\n') # 處理雙重轉義
                    pk = pk.replace('\\n', '\n')   # 處理單重轉義
                    
                    # 移除可能夾雜在金鑰中的任何非列印字元或多餘空格
                    # 但要小心保留 PEM 的開頭與結尾標籤
                    creds_dict["private_key"] = pk.strip()
                
                creds = Credentials.from_service_account_info(creds_dict, scopes=self.scope)
                self.client = gspread.authorize(creds)
            except Exception as e:
                # 這裡的錯誤訊息會被前端捕捉並顯示
                import traceback
                print(f"DEBUG: GSheet Auth Error:\n{traceback.format_exc()}")
                raise ValueError(f"Google 憑證解析失敗。錯誤詳情: {e}")
        return self.client

    def _get_works_sheet(self):
        client = self._get_client()
        try:
            sh = client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            raise ValueError(f"無法打開試算表，請確認 GOOGLE_SHEET_ID 是否正確以及服務帳號 Email 是否已加入共用。錯誤: {e}")
            
        try:
            return sh.worksheet("Works")
        except gspread.exceptions.WorksheetNotFound:
            # 初始化工作表
            ws = sh.add_worksheet(title="Works", rows="100", cols="10")
            ws.append_row(["id", "image_url", "elo", "match_count", "win_count", "team"])
            return ws

    def _get_history_sheet(self):
        client = self._get_client()
        try:
            sh = client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            raise ValueError(f"無法打開試算表，請確認 GOOGLE_SHEET_ID 是否正確。錯誤: {e}")
            
        try:
            return sh.worksheet("History")
        except gspread.exceptions.WorksheetNotFound:
            # 初始化歷史紀錄表
            ws = sh.add_worksheet(title="History", rows="1000", cols="10")
            ws.append_row(["round", "A_id", "B_id", "winner", "votes_A", "votes_B", "elo_A_old", "elo_A_new", "elo_B_old", "elo_B_new"])
            return ws

    def load_works(self) -> List[WorkItem]:
        ws = self._get_works_sheet()
        records = ws.get_all_records()
        works = []
        for r in records:
            works.append(WorkItem(
                id=str(r["id"]),
                image_url=r["image_url"],
                elo=int(r["elo"]),
                match_count=int(r["match_count"]),
                win_count=int(r["win_count"]),
                team=r["team"]
            ))
        return works

    def save_works(self, works: List[WorkItem]):
        ws = self._get_works_sheet()
        # 清除舊資料（除了標題）
        ws.clear()
        ws.append_row(["id", "image_url", "elo", "match_count", "win_count", "team"])
        
        rows = []
        for w in works:
            rows.append([w.id, w.image_url, w.elo, w.match_count, w.win_count, w.team])
        
        if rows:
            ws.append_rows(rows)

    def load_history(self) -> List[Dict[str, Any]]:
        ws = self._get_history_sheet()
        records = ws.get_all_records()
        history = []
        for r in records:
            history.append({
                "round": r["round"],
                "A_id": r["A_id"],
                "B_id": r["B_id"],
                "winner": r["winner"],
                "votes": {"A": r["votes_A"], "B": r["votes_B"]},
                "elo_changes": {
                    "A": {"old": r["elo_A_old"], "new": r["elo_A_new"]},
                    "B": {"old": r["elo_B_old"], "new": r["elo_B_new"]}
                }
            })
        return history

    def add_history(self, entry: Dict[str, Any]):
        ws = self._get_history_sheet()
        row = [
            entry["round"],
            entry["A_id"],
            entry["B_id"],
            entry["winner"],
            entry["votes"]["A"],
            entry["votes"]["B"],
            entry["elo_changes"]["A"]["old"],
            entry["elo_changes"]["A"]["new"],
            entry["elo_changes"]["B"]["old"],
            entry["elo_changes"]["B"]["new"]
        ]
        ws.append_row(row)

    def test_connection(self):
        """強行測試連線並在 Works 表格第一列寫入測試字串"""
        client = self._get_client()
        sh = client.open_by_key(self.spreadsheet_id)
        # 嘗試獲取或建立一個名為 "ConnectionTest" 的分頁，避免弄亂原本資料
        try:
            ws = sh.worksheet("ConnectionTest")
        except:
            ws = sh.add_worksheet(title="ConnectionTest", rows="10", cols="2")
        
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update_acell("A1", "Connection Success!")
        ws.update_acell("B1", f"Last tested: {now}")
        return f"Successfully wrote to sheet at {now}"

    def clear_all(self):
        """完全清空 Works 和 History 分頁（保留標題列）"""
        client = self._get_client()
        sh = client.open_by_key(self.spreadsheet_id)
        
        try:
            ws_works = sh.worksheet("Works")
            ws_works.clear()
            ws_works.append_row(["id", "image_url", "elo", "match_count", "win_count", "team"])
        except: pass

        try:
            ws_history = sh.worksheet("History")
            ws_history.clear()
            ws_history.append_row(["round", "A_id", "B_id", "winner", "votes_A", "votes_B", "elo_A_old", "elo_A_new", "elo_B_old", "elo_B_new"])
        except: pass
