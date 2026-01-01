import os
import re
import random
import requests
from lxml.etree import HTML
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = [
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15'},
    {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0 Safari/537.36'},
]

def random_header():
    return random.choice(HEADERS)

# 相册解锁

def unlock_album(session: requests.Session, album_url: str, password: str):
    r = session.get(album_url, timeout=10)
    r.raise_for_status()

    token = re.search(r'name="auth_token" value="([^"]+)"', r.text)
    if not token:
        raise RuntimeError("未找到 auth_token")

    auth_token = token.group(1)

    post_url = album_url
    data = {
        "content-password": password,
        "auth_token": auth_token
    }

    res = session.post(
        post_url,
        data=data,
        headers={
            "Referer": album_url,
            "Origin": "https://ibb.co"
        },
        timeout=10
    )
    res.raise_for_status()

    if "需要密码" in res.text:
        raise RuntimeError("密码错误或解锁失败")

    print("相册解锁成功")

# 相册页面解析

class IMGBBPageExtractor:
    def __init__(self, session: requests.Session, album_url: str):
        self.session = session
        self.start_url = self._normalize_url(album_url)
        self.image_page_links = []

    def _normalize_url(self, url: str) -> str:
        if "?sort=" not in url:
            url += "?sort=name_asc&page=1"
        return url

    def extract_all(self):
        url = self.start_url
        page_count = 1

        while True:
            res = self.session.get(url, headers=random_header(), timeout=10)
            res.raise_for_status()
            html = res.text

            links = re.findall(r"https://ibb\.co/\w{7,8}", html)
            links = list(dict.fromkeys(links))

            if not links:
                break

            for link in links:
                if link not in self.image_page_links:
                    self.image_page_links.append(link)

            dom = HTML(html)
            next_page = dom.xpath("//a[contains(text(),'›') or contains(text(),'Next')]/@href")
            if not next_page:
                break

            url = next_page[0]
            if not url.startswith("http"):
                url = "https://ibb.co" + url

            print(f"\r📄 已解析第 {page_count} 页，共 {len(self.image_page_links)} 张图片", end="")
            page_count += 1

        print(f"\n解析完成，共 {len(self.image_page_links)} 张图片")

# 原图解析

def extract_original_image_url(session: requests.Session, image_page_url: str) -> str:
    r = session.get(image_page_url, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    meta = soup.find("meta", property="og:image")
    if meta and meta.get("content"):
        return meta["content"]

    img = soup.find("img", src=re.compile(r"https://i\.ibb\.co/"))
    if img:
        return img["src"]

    raise RuntimeError("未找到原图地址")

# 下载器

def download_image(session: requests.Session, image_url: str, save_dir: str):
    os.makedirs(save_dir, exist_ok=True)

    filename = os.path.basename(urlparse(image_url).path)
    save_path = os.path.join(save_dir, filename)

    if os.path.exists(save_path):
        print(f"⏭ 已存在，跳过 {filename}")
        return

    with session.get(image_url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

    print(f"下载完成 {filename}")

def download_from_image_pages(session, image_pages, save_dir):
    total = len(image_pages)
    for i, page_url in enumerate(image_pages, 1):
        try:
            print(f"[{i}/{total}] 解析原图 {page_url}")
            image_url = extract_original_image_url(session, page_url)
            download_image(session, image_url, save_dir)
        except Exception as e:
            print(f"失败 {page_url} → {e}")

# 主入口

if __name__ == "__main__":
    album_url = "https://ibb.co/album/Z681jF"
    password = "123456"
    save_dir = "downloads"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": album_url,
        "Origin": "https://ibb.co"
    })

    unlock_album(session, album_url, password)

    spider = IMGBBPageExtractor(session, album_url)
    spider.extract_all()

    download_from_image_pages(
        session,
        spider.image_page_links,
        save_dir
    )

    print("所有图片下载完成")
