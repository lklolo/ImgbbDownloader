import json
import os
import time
import threading
from urllib.parse import urlparse

from app_state import task_status_file

_lock = threading.Lock()

def extract_filename(url):
    path = urlparse(url).path
    return os.path.basename(path)

def load_data():
    if os.path.exists(task_status_file):
        with open(task_status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(task_status_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
def add_link(url):
    with _lock:
        data = load_data()
        if url not in data:
            data[url] = {
                "filename": extract_filename(url),
                "status": "f",
                "downloaded": 0,
                "total": None,
                "error": None,
                "updated_at": int(time.time())
            }
        save_data(data)

def update_status(url, status, error=None):
    with _lock:
        data = load_data()
        if url not in data:
            return
        data[url]["status"] = status
        data[url]["error"] = error
        data[url]["updated_at"] = int(time.time())
        save_data(data)

def update_progress(url, downloaded, total=None):
    with _lock:
        data = load_data()
        if url not in data:
            return
        data[url]["status"] = "downloading"
        data[url]["downloaded"] = downloaded
        if total:
            data[url]["total"] = total
        data[url]["updated_at"] = int(time.time())
        save_data(data)

def rename_duplicates():
    if not os.path.exists(task_status_file):
        return
    with _lock:
        with open(task_status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        filename_count = {}
        updated = False
        for url, info in data.items():
            original = info["filename"]
            name, ext = os.path.splitext(original)
            if original not in filename_count:
                filename_count[original] = 1
            else:
                count = filename_count[original]
                new_name = f"{name}_{count}{ext}"
                while new_name in filename_count:
                    count += 1
                    new_name = f"{name}_{count}{ext}"
                filename_count[original] += 1
                filename_count[new_name] = 1
                data[url]["filename"] = new_name
                updated = True
        if updated:
            save_data(data)

def get_failed_map(log_func=print):
    try:
        rename_duplicates()
        if not os.path.exists(task_status_file):
            return {}
        with open(task_status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            url: info["filename"]
            for url, info in data.items()
            if info.get("status") != "t"
        }
    except Exception as e:
        log_func(f"❗ 读取失败: {e}")
        return {}

def reset_all_to_pending(log_func=print):
    if not os.path.exists(task_status_file):
        return

    with _lock:
        try:
            with open(task_status_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = False
            now = int(time.time())

            for url, info in data.items():
                info["status"] = "f"
                info["downloaded"] = 0
                info["total"] = None
                info["error"] = None
                info["updated_at"] = now
                updated = True

            if updated:
                save_data(data)
                log_func("🔄 已重置下载状态")

        except Exception as e:
            log_func(f"❗ 重置下载状态失败：{e}")

def clear_json():
    with _lock:
        save_data({})