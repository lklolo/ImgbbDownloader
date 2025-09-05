import json
import os
from urllib.parse import urlparse
from app_state import json_file

def extract_filename(url):
    path = urlparse(url).path
    return os.path.basename(path)

def load_data():
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_link(url):
    data = load_data()
    data[url] = {
        "filename": extract_filename(url),
        "status": "f"
    }
    save_data(data)

def update_status(url, new_status):
    data = load_data()
    data[url]["status"] = new_status
    save_data(data)
    
def rename_duplicates():
    if not os.path.exists(json_file):
        return
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    filename_count = {}
    updated = False
    for url, info in data.items():
        original_name = info["filename"]
        name, ext = os.path.splitext(original_name)
        if original_name not in filename_count:
            filename_count[original_name] = 1
        else:
            count = filename_count[original_name]
            new_name = f"{name}_{count}{ext}"
            while new_name in filename_count:
                count += 1
                new_name = f"{name}_{count}{ext}"

            filename_count[original_name] += 1
            filename_count[new_name] = 1
            data[url]["filename"] = new_name
            updated = True
    if updated:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

def clear_json():
    if os.path.exists(json_file):
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)