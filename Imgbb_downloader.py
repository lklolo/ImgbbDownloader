import os
from config import load_config

config = load_config()

DOWNLOAD_DIR = config["download_dir"]
json_file = config["download_list_file"]
headers = config["headers"]

import sys
import re

import download
import get_download_links
import read_json
import write_json

if __name__ == "__main__":
    if input("是否继续上次的下载？(y/n, default:no) ") in ["y", "Y", "yes", "Yes"]:
        if os.path.exists(json_file) and os.path.getsize(json_file) > 0:
            download.download_files_concurrently(read_json.get_failed_map())
            sys.exit()
        else:
            print("没有找到上次的链接")
    
    print("请输入链接，使用Ctrl+D 或 Ctrl+Z，Enter来结束输入")
    input_text = sys.stdin.read()
    p_urls = re.findall(r'https://ibb\.co/[a-zA-Z0-9]+', input_text)
    if p_urls:
        print(f"检测到 {len(p_urls)} 个链接")
        write_json.clear_json()
        get_download_links.process_download_links_until_success(p_urls)
        print("开始下载原图...")
        download.download_files_concurrently(read_json.get_failed_map())
    else:
        print("没有检测到任何链接。")