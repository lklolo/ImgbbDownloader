import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import threading
import re

from config import load_config
import get_download_links
import download
import read_json
import write_json

config = load_config()
DOWNLOAD_DIR = config["download_dir"]
json_file = config["download_list_file"]

class ImgbbDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("Imgbb 批量原图下载器")
        root.geometry("600x500")

        self.create_widgets()

    def create_widgets(self):
        # 多行文本框：链接输入
        tk.Label(self.root, text="请输入链接（每行一个或多条）").pack(anchor="w", padx=10, pady=5)
        self.link_input = scrolledtext.ScrolledText(self.root, height=10)
        self.link_input.pack(fill="both", expand=False, padx=10)

        # 日志输出框
        tk.Label(self.root, text="日志 / 状态").pack(anchor="w", padx=10, pady=5)
        self.log_output = scrolledtext.ScrolledText(self.root, height=12, state="disabled")
        self.log_output.pack(fill="both", expand=True, padx=10, pady=(0,10))

        # 按钮区
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="开始新任务", command=self.start_new_task).pack(side="left", padx=10)
        tk.Button(btn_frame, text="继续上次下载", command=self.resume_last_task).pack(side="left", padx=10)

    def log(self, msg):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.log_output.config(state="normal")
        self.log_output.insert("end", msg + "\n")
        self.log_output.see("end")
        self.log_output.config(state="disabled")

    def extract_links(self):
        input_text = self.link_input.get("1.0", "end")
        links = re.findall(r'https://ibb\.co/[a-zA-Z0-9]+', input_text)
        return list(set(links))

    def start_new_task(self):
        links = self.extract_links()
        if not links:
            messagebox.showwarning("提示", "没有检测到任何有效链接")
            return

        self.log(f"检测到 {len(links)} 个链接，正在清空状态并开始下载...")
        write_json.clear_json()

        def worker():
            try:
                get_download_links.process_download_links_until_success(links, log_func=self.log)
                self.log("原图链接获取成功，开始下载...")
                download.download_files_concurrently(read_json.get_failed_map(), log_func=self.log)
                self.log("下载完成！")
            except Exception as e:
                self.log(f"发生错误：{e}")

        threading.Thread(target=worker).start()

    def resume_last_task(self):
        if not os.path.exists(json_file) or os.path.getsize(json_file) == 0:
            messagebox.showinfo("提示", "未找到上次下载任务")
            return

        self.log("恢复上次下载任务...")

        def worker():
            try:
                download.download_files_concurrently(read_json.get_failed_map())
                self.log("下载完成！")
            except Exception as e:
                self.log(f"发生错误：{e}")

        threading.Thread(target=worker).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImgbbDownloaderApp(root)
    root.mainloop()
