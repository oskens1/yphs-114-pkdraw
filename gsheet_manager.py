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
            
            creds_dict = json.loads(self.credentials_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=self.scope)
            self.client = gspread.authorize(creds)
        return self.client

    def _get_works_sheet(self):
        client = self._get_client()
        sh = client.open_by_key(self.spreadsheet_id)
        try:
            return sh.worksheet("Works")
        except gspread.exceptions.WorksheetNotFound:
            # 初始化工作表
            ws = sh.add_worksheet(title="Works", rows="100", cols="10")
            ws.append_row(["id", "image_url", "elo", "match_count", "win_count", "team"])
            return ws

    def _get_history_sheet(self):
        client = self._get_client()
        sh = client.open_by_key(self.spreadsheet_id)
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
