import re
import requests

import task_status


# =========================
# 工具函数
# =========================

def album_need_password(html: str) -> bool:
    return 'name="content-password"' in html


# =========================
# 相册解锁
# =========================

def unlock_album(session: requests.Session, album_url: str, password: str):
    r = session.get(album_url, timeout=10)
    r.raise_for_status()

    token = re.search(r'name="auth_token" value="([^"]+)"', r.text)
    if not token:
        return False, "未找到 auth_token"

    auth_token = token.group(1)

    res = session.post(
        album_url,
        data={
            "content-password": password,
            "auth_token": auth_token
        },
        headers={
            "Referer": album_url,
            "Origin": "https://ibb.co"
        },
        timeout=10,
        allow_redirects=True
    )
    res.raise_for_status()

    # ⭐ 二次 GET 验证是否真正解锁
    verify = session.get(album_url, timeout=10)
    verify.raise_for_status()

    if album_need_password(verify.text):
        return False, "相册密码错误"

    return True, "相册解锁成功"


# =========================
# 提取相册中的图片页面链接
# =========================

def extract_image_pages(
        session: requests.Session,
        album_url: str,
        log_func=print
):
    image_pages = []
    page = 1

    while True:
        url = f"{album_url}?page={page}"

        r = session.get(url, timeout=10)
        r.raise_for_status()

        html = r.text

        links = re.findall(
            r"https://ibb\.co/[a-zA-Z0-9]{7,8}",
            html
        )
        links = list(dict.fromkeys(links))

        if not links:
            break

        new_links = [l for l in links if l not in image_pages]
        if not new_links:
            break

        image_pages.extend(new_links)

        page += 1

    return image_pages


# =========================
# 提取图片原图链接
# =========================

def extract_original_image_url(
        session: requests.Session,
        image_page_url: str,
        log_func=print
) -> str:

    r = session.get(image_page_url, timeout=10)
    r.raise_for_status()

    m = re.search(
        r'<meta property="og:image" content="([^"]+)"',
        r.text
    )

    if not m:
        log_func("❌ 未在页面中找到 og:image 元标签")
        raise RuntimeError("未找到原图链接")

    img_url = m.group(1)
    log_func(f"🖼️ 获取原图链接：{img_url}")

    return img_url


# =========================
# 主入口：处理所有链接
# =========================

def process_download_links_until_success(
        links,
        log_func=print,
        album_password=None
):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://ibb.co",
        "Origin": "https://ibb.co"
    })

    for link in links:
        try:
            # =====================
            # 单图页面
            # =====================
            if "/album/" not in link:
                log_func(f"🖼️ 解析单张图片：{link}")

                img_url = extract_original_image_url(
                    session,
                    link,
                    log_func
                )
                task_status.add_link(img_url)
                continue

            # =====================
            # 相册页面
            # =====================
            log_func(f"📁 解析相册：{link}")

            r = session.get(link, timeout=10)
            r.raise_for_status()

            if album_need_password(r.text):

                if not album_password:
                    raise RuntimeError("该相册需要密码")

                ok, msg = unlock_album(
                    session,
                    link,
                    album_password
                )
                if not ok:
                    raise RuntimeError(msg)

                log_func("🔓 相册解锁成功")
            else:
                log_func("🔓 相册无需解锁")

            # 二次确认
            if album_need_password(session.get(link).text):
                raise RuntimeError("相册仍处于锁定状态")

            pages = extract_image_pages(
                session,
                link,
                log_func
            )
            if not pages:
                raise RuntimeError("相册中未解析到任何图片")

            log_func(f"📁 相册共 {len(pages)} 张图片")

            for idx, page_url in enumerate(pages, start=1):

                img_url = extract_original_image_url(
                    session,
                    page_url,
                    log_func
                )
                task_status.add_link(img_url)

        except Exception as e:
            log_func(f"❗ 解析失败 {link} → {e}")
