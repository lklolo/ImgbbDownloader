import os
import requests
from concurrent.futures import ThreadPoolExecutor

import write_json
from app_state import DOWNLOAD_DIR, headers
import time

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_file(download_url, file_name, log_func=print, chunk_size=1024*1024,
                  retries=5, timeout=30, file_index=0, total_files=1,
                  progress_callback=None):

    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    attempt = 0

    if progress_callback:
        progress_callback(file_index, total_files, file_name, "下载中")

    # 已下载大小（断点续传）
    downloaded = 0
    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)

    while attempt < retries:
        try:
            # ⚠️ 每次 copy headers，避免多线程污染
            local_headers = headers.copy()

            # ⚠️ Range 断点续传
            if downloaded > 0:
                local_headers["Range"] = f"bytes={downloaded}-"

            with requests.get(
                    download_url,
                    headers=local_headers,
                    stream=True,
                    timeout=timeout
            ) as response:

                # 206 = Partial Content（断点续传正常）
                if response.status_code not in (200, 206):
                    response.raise_for_status()

                mode = "ab" if downloaded > 0 else "wb"
                with open(file_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            write_json.update_status(download_url, "t")
            log_func(f"[完成] {file_name}")

            if progress_callback:
                progress_callback(file_index, total_files, file_name, "已完成")

            return None

        except requests.RequestException as e:
            attempt += 1
            wait_time = 2 ** (attempt - 1)  # 指数退避 1,2,4,8...
            log_func(f"[重试 {attempt}/{retries}] {file_name} 失败: {e}，{wait_time}s 后重试")
            time.sleep(wait_time)

    if progress_callback:
        progress_callback(file_index, total_files, file_name, "失败")

    return download_url

def download_files_concurrently(url_to_filename_map, log_func=print, max_workers=10,
                                retries=5, progress_callback=None):
    failed_urls = []
    urls = list(url_to_filename_map.items())
    total_files = len(urls)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for idx, (url, filename) in enumerate(urls, 1):
            future = executor.submit(
                download_file, url, filename, log_func,
                retries=retries, progress_callback=progress_callback,
                file_index=idx, total_files=total_files
            )
            futures[future] = url

        for future in futures:
            result = future.result()
            if result:
                failed_urls.append(result)

    return failed_urls
