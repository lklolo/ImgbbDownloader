import json
import os

import save_json

json_file = "d_urls.json"

def read_json():
    if not os.path.exists(json_file):
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    for url, info in data.items():
        print(f"链接: {url}")
        print(f"文件名: {info['filename']}")
        print(f"状态: {info['status']}")
        print("-" * 30)

def get_failed_map():
    save_json.rename_duplicates()
    if not os.path.exists(json_file):
        return {}
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    failed_map = {
        url: info["filename"]
        for url, info in data.items()
        if info.get("status") == "f"
    }
    return failed_map
