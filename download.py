import os
import requests
from concurrent.futures import ThreadPoolExecutor

import write_json
from app_state import DOWNLOAD_DIR, headers

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_file(download_url, file_name, log_func=print, chunk_size=1024*1024,
                  retries=5, timeout=30, file_index=0, total_files=1, progress_callback=None):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    attempt = 0

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

            # 下载完成后回调进度
            if progress_callback:
                progress_callback(file_index, total_files)

            return None
        except requests.RequestException as e:
            attempt += 1
            log_func(f"[重试 {attempt}/{retries}] {file_name} 下载失败: {e}")
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

        # 等待所有文件完成
        for future in futures:
            result = future.result()
            if result:
                failed_urls.append(result)

    return failed_urls
