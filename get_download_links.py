import requests
from bs4 import BeautifulSoup
import time

import save_json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'Accept': 'application/octet-stream',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}
def get_download_link(p_url, retries=10, timeout=10):
    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(p_url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                download_link = soup.find('a', {'class': 'btn btn-download default'})
                if download_link and 'href' in download_link.attrs:
                    return download_link['href']
                else:
                    return None
            else:
                return None
        except requests.RequestException as e:
            attempt += 1
            print(f"请求失败，重试 {attempt}/{retries} 次... 错误: {e}")
            time.sleep(2)
    return None
def process_download_links(p_urls):
    failed_urls = []
    for i, p_url in enumerate(p_urls, 1):
        d_url = get_download_link(p_url)
        if d_url is None:
            failed_urls.append(p_url)
            print(f"获取失败 {i}/{str(len(p_urls))}: {p_url} ，已跳过")
        else:
            save_json.add_link(d_url)
            print(f"已提取原图链接 {i}/{str(len(p_urls))}: {d_url}")
    return failed_urls

def process_download_links_until_success(p_urls):
    attempt = 0
    while p_urls:
        attempt += 1
        print(f"第 {attempt} 次尝试获取链接...")
        p_urls = process_download_links(p_urls)
        if p_urls:
            print(f"第 {attempt} 次获取共 {str(len(p_urls))} 个链接获取失败，正在重试...")