import os

import requests
from bs4 import BeautifulSoup
import time
from tqdm import tqdm

# 伪装请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
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

        # 重试
        except requests.RequestException as e:
            attempt += 1
            print(f"请求失败，重试 {attempt}/{retries} 次... 错误: {e}")
            time.sleep(2)

    return "请求失败，请稍后重试。"

lose = []
def download_file(download_url, file_name, retries=10, timeout=60, chunk_size=1024*1024):
    attempt = 0
    # 确保目标文件夹存在
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    # 检查文件是否已经存在
    file_path = f'downloads/{file_name}'
    if os.path.exists(file_path):
        print(f"文件已存在，跳过下载: {file_name}")
        return    

    # 获取文件已下载的大小（如果文件存在的话）
    file_path = f'downloads/{file_name}'
    existing_size = 0
    if os.path.exists(file_path):
        existing_size = os.path.getsize(file_path)
        print(f"已下载 {existing_size} 字节，继续下载...")

    while attempt < retries:
        try:
            # 设置请求头中的 Range 字段，表示从上次下载中断的地方继续下载
            range_header = {'Range': f"bytes={existing_size}-"} if existing_size > 0 else {}
            headers.update(range_header)

            # 发送GET请求，加入请求头并设置超时
            response = requests.get(download_url, headers=headers, stream=True, timeout=timeout)

            # 检查请求是否成功
            if response.status_code == 200 or response.status_code == 206:  # 206 为断点续传
                # 获取文件的总大小
                total_size = int(response.headers.get('content-length', 0)) + existing_size
                # 以追加模式打开文件，支持断点续传
                with open(file_path, 'ab') as f:
                    # 使用tqdm创建进度条
                    with tqdm(total=total_size, initial=existing_size, unit='B', unit_scale=True, desc=file_name) as pbar:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))  # 更新进度条
                return  # 下载成功后跳出重试循环
            else:
                print(f"下载失败，状态码: {response.status_code}，重试 {attempt + 1}/{retries}")

        except requests.RequestException as e:
            print(f"请求失败，错误: {e}，重试 {attempt + 1}/{retries}")

        # 重试
        attempt += 1
        time.sleep(2)

    print(f"下载失败，已重试 {retries} 次。放弃: {download_url}")
    lose.append(download_url)

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

    
    # 下载文件
    for i, download_url in enumerate(download_urls, 1):
        file_name = download_url.split('/')[-1]
        download_file(download_url, file_name)
    print("下载结束")
    if len(lose) != 0:
        print("下载失败" + str(len(lose)) + "个文件，您可重新运行本程序并选择直接读取上次运行提取的下载链接，程序将自动检索并尝试补全")
    else:
        print("全部下载成功！")
        