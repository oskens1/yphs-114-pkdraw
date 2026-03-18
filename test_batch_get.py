import os
import json
from gsheet_manager import GSheetManager
from dotenv import load_dotenv
load_dotenv()

gm = GSheetManager()
sh = gm._get_spreadsheet()
res = sh.values_batch_get(['Works!A:F', 'SystemState!A:B', 'VotesLog!A:C'])
print(res)
