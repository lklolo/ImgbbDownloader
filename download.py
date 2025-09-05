import os
import requests
from concurrent.futures import ThreadPoolExecutor

import write_json
from app_state import DOWNLOAD_DIR, headers

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_file(download_url, file_name, log_func=print, chunk_size=1024*1024,
                  retries=5, timeout=30, file_index=0, total_files=1,
                  progress_callback=None):
    """
    下载单个文件，完成后调用 progress_callback(file_index, total_files, file_name, status)
    status: "下载中" / "已完成" / "失败"
    """
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    attempt = 0

    if progress_callback:
        progress_callback(file_index, total_files, file_name, "下载中")

    while attempt < retries:
        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
            write_json.update_status(download_url, "t")
            log_func(f"[完成] {file_name}")
            if progress_callback:
                progress_callback(file_index, total_files, file_name, "已完成")
            return None
        except requests.RequestException as e:
            attempt += 1
            log_func(f"[重试 {attempt}/{retries}] {file_name} 下载失败: {e}")

    # 超过重试次数仍失败
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
