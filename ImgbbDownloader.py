import os

import requests
from bs4 import BeautifulSoup
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
# 伪装请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'Accept': 'application/octet-stream',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}

def get_download_link(url, retries=10, timeout=10):
    attempt = 0
    while attempt < retries:
        try:
            # 发送GET请求获取网页内容
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                # 使用BeautifulSoup解析网页
                soup = BeautifulSoup(response.text, 'html.parser')

                # 找到目标的<a>标签
                download_link = soup.find('a', {'class': 'btn btn-download default'})

                # 提取href属性中的下载链接
                if download_link and 'href' in download_link.attrs:
                    return download_link['href']
                else:
                    return "未找到下载链接"
            else:
                return f"网页请求失败，状态码: {response.status_code}"

        except requests.RequestException as e:
            attempt += 1
            print(f"请求失败，重试 {attempt}/{retries} 次... 错误: {e}")
            time.sleep(2)

    return "请求失败，请稍后重试。"

def download_file(download_url, file_name, chunk_size=1024 * 1024, retries=5, timeout=30):
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    # 检查文件是否已存在
    if os.path.exists(file_path):
        return None
    
    attempt = 0
    while attempt < retries:
        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=timeout) as response:
                response.raise_for_status()  # 检查请求是否成功
                total_size = int(response.headers.get('content-length', 0))
                with open(file_path, 'wb') as f, tqdm(
                        total=total_size, unit='B', unit_scale=True, desc=file_name
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # 避免空块
                            f.write(chunk)
                            pbar.update(len(chunk))
            return None  # 成功下载返回 None
        except requests.RequestException as e:
            attempt += 1
    return download_url

# 多线程下载
def download_files_concurrently(download_urls, max_workers=10, retries=5):
    failed_urls = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file, url, url.split('/')[-1], retries=retries): url for url in download_urls}
        for future in tqdm(futures, desc="总进度"):
            result = future.result()
            if result:
                failed_urls.append(result)
    return failed_urls

if __name__ == "__main__":
    import sys
    import re

    download_urls = []
    if input("是否直接读取上次运行提取的下载链接(y/n, default:no) ") in ["y", "Y", "yes", "Yes"]:
        try:
            with open('download_urls.txt', 'r') as url:
                download_urls = [line.strip() for line in url]
        except FileNotFoundError:
            print("文件 'download_urls.txt' 不存在")
    else:
        # 从控制台获取多行输入
        print("请输入链接，使用 Ctrl + D 或 Ctrl + Z 来结束输入")
        input_text = sys.stdin.read()
        # 提取URL
        urls = re.findall(r'https?://\S+', input_text)
        if urls:
            for i, url in enumerate(urls, 1):
                print(f"{i}. {url}")
            print(f"检测到上述{str(len(urls))}个链接，开始提取原图...")
        else:
            print("没有检测到任何链接。")

        # 提取下载链接
        for i, link in enumerate(urls, 1):
            download_url = get_download_link(link)
            download_urls.append(download_url)
            print(f"已提取原图 {i}/{str(len(urls))}: {download_url}")

        with open('download_urls.txt', 'w') as url:
            for item in download_urls:
                url.write(f"{item}\n")
        print("本次提取的原图链接已保存，开始下载原图...")

    while True:
        failed = download_files_concurrently(download_urls)
        if failed:
            print(f"共 {len(failed)} 个文件下载失败，正在重试失败的下载...")
        else:
            print("所有文件下载成功！")
            break
        
        