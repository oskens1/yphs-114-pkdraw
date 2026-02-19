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
                # 終極解析邏輯：處理 Vercel 貼上 JSON 時可能產生的所有格式問題
                json_str = self.credentials_json.strip()
                
                # 如果 private_key 裡的 \n 被轉成了真實換行，把它轉回來
                if "-----BEGIN PRIVATE KEY-----" in json_str and "\\n" not in json_str:
                    # 這代表換行符號變成了真實換行，我們需要修復它
                    # 先解析成字典，如果解析失敗則手動處理
                    try:
                        creds_dict = json.loads(json_str)
                    except:
                        # 暴力修復：將 JSON 字串中的真實換行替換掉，但保留 key 格式
                        # 這種情況較複雜，我們先嘗試標準解析
                        raise ValueError("JSON 格式毀損，請確認貼上的是完整的 { ... } 內容")
                else:
                    creds_dict = json.loads(json_str)

                # 關鍵修復：確保 private_key 中的換行符號正確
                if "private_key" in creds_dict:
                    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
                creds = Credentials.from_service_account_info(creds_dict, scopes=self.scope)
                self.client = gspread.authorize(creds)
            except Exception as e:
                raise ValueError(f"Google 憑證解析失敗。請確保貼入 Vercel 的是完整的 JSON 內容。錯誤詳情: {e}")
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
