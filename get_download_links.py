import re
import requests

import json_editor

# =========================
# 判断相册是否需要密码
# （严格按 demo：是否存在 content-password）
# =========================
def album_need_password(html: str) -> bool:
    return 'name="content-password"' in html


# =========================
# 相册解锁（100% demo 等价）
# =========================
def unlock_album(session: requests.Session, album_url: str, password: str):
    r = session.get(album_url, timeout=10)
    r.raise_for_status()

    # 提取 auth_token（关键）
    token = re.search(r'name="auth_token" value="([^"]+)"', r.text)
    if not token:
        return False, "未找到 auth_token"

    auth_token = token.group(1)

    data = {
        "content-password": password,
        "auth_token": auth_token
    }

    res = session.post(
        album_url,
        data=data,
        headers={
            "Referer": album_url,
            "Origin": "https://ibb.co"
        },
        timeout=10
    )
    res.raise_for_status()

    # 如果解锁失败，页面中仍然存在密码表单
    if album_need_password(res.text):
        return False, "相册密码错误"

    return True, "相册解锁成功"


# =========================
# 解析相册中所有图片页面（你 demo 的方式）
# =========================
def extract_image_pages(session: requests.Session, album_url: str, log_func=print):
    image_pages = []
    page = 1

    while True:
        url = f"{album_url}?page={page}"
        r = session.get(url, timeout=10)
        r.raise_for_status()

        html = r.text

        links = re.findall(r"https://ibb\.co/[a-zA-Z0-9]{7,8}", html)
        links = list(dict.fromkeys(links))

        new_links = [l for l in links if l not in image_pages]
        if not new_links:
            break

        image_pages.extend(new_links)
        log_func(f"📄 相册第 {page} 页，累计 {len(image_pages)} 张")
        page += 1

    return image_pages


# =========================
# 提取原图链接（demo 原方法）
# =========================
def extract_original_image_url(session: requests.Session, image_page_url: str) -> str:
    r = session.get(image_page_url, timeout=10)
    r.raise_for_status()

    m = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("未找到原图链接")

    return m.group(1)


# =========================
# GUI 调用的主入口
# =========================
def process_download_links_until_success(
        links,
        log_func=print,
        album_password=None
):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://ibb.co",
        "Origin": "https://ibb.co"
    })

    for link in links:
        try:
            # ================= 单张图片（原逻辑） =================
            if "/album/" not in link:
                img_url = extract_original_image_url(session, link)
                json_editor.add_link(img_url)
                continue

            # ================= 相册 =================
            log_func(f"📁 解析相册：{link}")

            r = session.get(link, timeout=10)
            r.raise_for_status()

            # 判断是否需要密码
            if album_need_password(r.text):
                if not album_password:
                    raise RuntimeError("该相册需要密码")

                ok, msg = unlock_album(session, link, album_password)
                if not ok:
                    raise RuntimeError(msg)

                log_func("🔓 相册解锁成功")
            else:
                log_func("🔓 相册无需解锁")

            # 解锁后解析图片
            pages = extract_image_pages(session, link, log_func)
            if not pages:
                raise RuntimeError("❗ 相册中未解析到任何图片")

            log_func(f"📁 相册共 {len(pages)} 张图片")

            for page_url in pages:
                img_url = extract_original_image_url(session, page_url)
                json_editor.add_link(img_url)

        except Exception as e:
            log_func(f"❗ 解析失败 {link} → {e}")
