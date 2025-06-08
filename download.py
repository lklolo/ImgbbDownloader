import os
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

import write_json
from Imgbb_downloader import DOWNLOAD_DIR
from Imgbb_downloader import headers

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
def download_file(download_url, file_name, chunk_size=1024 * 1024, retries=5, timeout=30):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    attempt = 0
    while attempt < retries:
        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                with open(file_path, 'wb') as f, tqdm(
                        total=total_size, unit='B', unit_scale=True, desc=file_name, leave=False
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            write_json.update_status(download_url, "t")
            return None
        except requests.RequestException:
            attempt += 1
    return download_url

def download_files_concurrently(url_to_filename_map, max_workers=10, retries=5):
    failed_urls = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_file, url, filename, retries=retries): url
            for url, filename in url_to_filename_map.items()
        }
        for future in tqdm(futures, desc="总进度"):
            result = future.result()
            if result:
                failed_urls.append(result)
    return failed_urls
