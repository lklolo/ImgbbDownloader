import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, CancelledError

import task_status
from app_state import download_dir, headers
from app_state import shutdown_event, pause_event

os.makedirs(download_dir, exist_ok=True)

def check_file_complete_by_head(url, file_path, timeout=10):
    if not os.path.exists(file_path):
        return False

    try:
        resp = requests.head(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )

        if resp.status_code != 200:
            return None

        content_length = resp.headers.get("Content-Length")
        if content_length is None:
            return None

        try:
            remote_size = int(content_length)
        except ValueError:
            return None

        local_size = os.path.getsize(file_path)
        return local_size == remote_size

    except requests.exceptions.Timeout:
        return None

    except requests.exceptions.ConnectionError:
        return None

    except requests.exceptions.RequestException:
        return None

    except OSError:
        return None

def download_file(download_url, file_name, log_func=print,
                  chunk_size=1024 * 1024,
                  retries=5, timeout=30,
                  file_index=0, total_files=1,
                  progress_callback=None):

    if shutdown_event.is_set():
        return None

    file_path = os.path.join(download_dir, file_name)

    head_ok = check_file_complete_by_head(download_url, file_path)
    if head_ok is True:
        task_status.update_status(download_url, "t")
        log_func(f"[跳过] {file_name} 已完整（HEAD）")
        if progress_callback:
            progress_callback(file_index, total_files, file_name, "已完成")
        return None

    data = task_status.load_data().get(download_url, {})
    downloaded = data.get("downloaded", 0)

    if os.path.exists(file_path):
        downloaded = os.path.getsize(file_path)

    if progress_callback:
        progress_callback(file_index, total_files, file_name, "下载中")

    attempt = 0
    while attempt < retries:
        pause_event.wait()
        if shutdown_event.is_set():
            return None
        if shutdown_event.is_set():
            return None

        try:
            local_headers = headers.copy()
            if downloaded > 0:
                local_headers["Range"] = f"bytes={downloaded}-"

            with requests.get(
                    download_url,
                    headers=local_headers,
                    stream=True,
                    timeout=timeout
            ) as r:

                if r.status_code not in (200, 206):
                    r.raise_for_status()

                total = r.headers.get("Content-Length")
                total = int(total) + downloaded if total else None

                mode = "ab" if downloaded > 0 else "wb"
                with open(file_path, mode) as f:
                    for chunk in r.iter_content(chunk_size):
                        pause_event.wait()
                        
                        if shutdown_event.is_set():
                            return None

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            task_status.update_progress(
                                download_url,
                                downloaded,
                                total
                            )

            task_status.update_status(download_url, "t")
            log_func(f"[完成] {file_name}")
            if progress_callback:
                progress_callback(file_index, total_files, file_name, "已完成")
            return None

        except requests.exceptions.HTTPError as e:
            attempt += 1

            if e.response is not None and e.response.status_code == 416:
                log_func(f"[416] {file_name} 断点无效，重新完整下载")

                if os.path.exists(file_path):
                    os.remove(file_path)

                downloaded = 0
                task_status.update_progress(download_url, 0, None)
                continue

            wait = 2 ** (attempt - 1)
            task_status.update_status(download_url, "f", str(e))
            log_func(
                f"[重试 {attempt}/{retries}] {file_name} 失败: {e}，{wait}s 后重试"
            )
            time.sleep(wait)

        except Exception as e:
            attempt += 1
            wait = 2 ** (attempt - 1)
            task_status.update_status(download_url, "f", str(e))
            log_func(
                f"[重试 {attempt}/{retries}] {file_name} 失败: {e}，{wait}s 后重试"
            )
            time.sleep(wait)

    if progress_callback:
        progress_callback(file_index, total_files, file_name, "失败")

    return download_url

def download_files_concurrently(
        url_to_filename_map,
        log_func=print,
        max_workers=6,
        retries=5,
        progress_callback=None
):
    urls = list(url_to_filename_map.items())
    total_files = len(urls)
    failed = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        for idx, (url, filename) in enumerate(urls, 1):
            if shutdown_event.is_set():
                break

            future = executor.submit(
                download_file,
                url,
                filename,
                log_func,
                timeout=30,
                chunk_size=1024 * 1024,
                retries=retries,
                file_index=idx,
                total_files=total_files,
                progress_callback=progress_callback
            )
            futures.append(future)

        for future in futures:
            if shutdown_event.is_set():
                break

            try:
                res = future.result()
                if res:
                    failed.append(res)

            except CancelledError:
                log_func("❌ 下载任务被取消")

            except Exception as e:
                log_func(f"❗ 下载线程异常: {e}")
                failed.append("unknown")

    return failed