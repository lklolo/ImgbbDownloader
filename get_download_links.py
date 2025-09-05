import requests
from bs4 import BeautifulSoup
import time

import write_json
from app_state import headers

def get_download_link(p_url, retries=10, timeout=10, log_func=print):
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
            log_func(f"请求失败，重试 {attempt}/{retries} 次... 错误: {e}")
            time.sleep(2)
    return None

def process_download_links(p_urls, log_func=print):
    failed_urls = []
    for i, p_url in enumerate(p_urls, 1):
        d_url = get_download_link(p_url, log_func=log_func)
        if d_url is None:
            failed_urls.append(p_url)
            log_func(f"[失败 {i}/{len(p_urls)}] {p_url} 已跳过")
        else:
            write_json.add_link(d_url)
            log_func(f"[成功 {i}/{len(p_urls)}] 已提取原图链接 {d_url}")
    return failed_urls

def process_download_links_until_success(p_urls, log_func=print):
    attempt = 0
    while p_urls:
        attempt += 1
        if attempt > 1:
            log_func(f"第 {attempt} 次尝试获取链接...")
        p_urls = process_download_links(p_urls, log_func=log_func)
        if p_urls:
            log_func(f"第 {attempt} 次获取失败 {len(p_urls)} 个链接，正在重试...")
