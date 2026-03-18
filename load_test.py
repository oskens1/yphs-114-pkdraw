import threading
import requests
import random
import time
import argparse

def send_vote(url, choice):
    """發送一次投票"""
    # 模擬真人隨機間隔 0.1~0.5s，避免 Google API 瞬間併發配額限制
    time.sleep(random.uniform(0.1, 0.5))
    try:
        response = requests.post(f"{url}/vote", data={"choice": choice})
        if response.status_code == 200:
            print(f"[OK] Vote {choice} successful.")
        else:
            print(f"[FAIL] Vote {choice} failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Request error: {e}")

def run_load_test(url, count=30):
    """執行併發壓力測試"""
    print(f"Starting load test for {url} with {count} concurrent votes...")
    threads = []
    
    # 首先檢查當前是否有進行中的回合
    try:
        status_resp = requests.get(f"{url}/status")
        status_data = status_resp.json()
        if not status_data.get("current_match") or status_data["current_match"].get("status") != "voting":
            print("[INFO] No active round found. Attempting to start a new round via /next_round...")
            next_round_resp = requests.post(f"{url}/next_round")
            if next_round_resp.status_code != 200:
                print("[ERROR] Failed to start a new round. Please ensure there are works uploaded.")
                return
            print("[OK] New round started.")
    except Exception as e:
        print(f"[ERROR] Failed to check status: {e}")
        return

    # 建立 30 個執行緒模擬併發
    for i in range(count):
        choice = random.choice(["A", "B"])
        t = threading.Thread(target=send_vote, args=(url, choice))
        threads.append(t)

    # 同時開始
    for t in threads:
        t.start()

    # 等待結束
    for t in threads:
        t.join()

    print("\nLoad test completed.")
    print("Please check Google Sheets 'VotesLog' sheet to verify the count.")
    
    # 讀取最終票數結果 (從後端 API)
    try:
        time.sleep(1) # 稍等一秒讓寫入穩定
        final_status = requests.get(f"{url}/status").json()
        votes = final_status.get("current_match", {}).get("votes", {"A": 0, "B": 0})
        print(f"Final votes from API: A={votes['A']}, B={votes['B']}, Total={votes['A'] + votes['B']}")
    except:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="紅白對抗賽壓力測試腳本")
    parser.add_argument("--url", default="http://localhost:8000", help="伺服器地址 (預設: http://localhost:8000)")
    parser.add_argument("--count", type=int, default=30, help="模擬人數 (預設: 30)")
    args = parser.parse_args()

    run_load_test(args.url, args.count)
