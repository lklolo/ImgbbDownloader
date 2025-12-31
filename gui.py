import sys
import os
import re
import threading

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox, QFrame, QProgressBar,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from config import load_config
import app_state

class Logger(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    max_progress_signal = pyqtSignal(int)
    file_status_signal = pyqtSignal(str, str)  # file_name, status

logger = Logger()

class ImgbbDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Imgbb 批量原图下载器")
        self.resize(700, 1000)
        self.setWindowIcon(QIcon("icon.ico"))
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ffffff; font-family: Arial; }
        """)

        self.config = load_config(log_func=self.log)
        app_state.DOWNLOAD_DIR = self.config["download_directory"]
        app_state.json_file = self.config["task_status"]
        app_state.headers = self.config["headers"]

        self.completed_files = 0
        self.total_files = 0

        self.init_ui()

        logger.log_signal.connect(self._append_log)
        logger.progress_signal.connect(self._update_progress)
        logger.max_progress_signal.connect(self._set_progress_max)
        logger.file_status_signal.connect(self._update_file_status)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 12, 12, 12)

        input_label = QLabel("请输入链接")
        input_layout.addWidget(input_label)

        self.link_input = QTextEdit()
        self.link_input.setFixedHeight(150)
        self.link_input.setStyleSheet("background-color: #2b2b2b; color: #ffffff; border:1px solid #555555; border-radius:5px;")
        input_layout.addWidget(self.link_input)
        main_layout.addWidget(input_frame)

        log_frame = QFrame()
        log_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 12, 12, 12)

        log_label = QLabel("日志 / 状态")
        log_layout.addWidget(log_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #2b2b2b; color: #ffffff; border:1px solid #555555; border-radius:5px;")
        log_layout.addWidget(self.log_output)
        main_layout.addWidget(log_frame, stretch=1)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["文件名 / 链接", "状态"])
        self.file_table.setStyleSheet("""
            QTableWidget { background-color: #2b2b2b; color: #ffffff; gridline-color:#555555; }
            QHeaderView::section { background-color:#3c3f41; color:#ffffff; }
        """)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.file_table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border:1px solid #555555; border-radius:5px; text-align:center; background-color:#2b2b2b; color:#ffffff; }
            QProgressBar::chunk { background-color:#4caf50; border-radius:5px; }
        """)
        main_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始新任务")
        self.start_btn.clicked.connect(self.start_new_task)
        btn_layout.addWidget(self.start_btn)
        self.resume_btn = QPushButton("继续上次下载")
        self.resume_btn.clicked.connect(self.resume_last_task)
        btn_layout.addWidget(self.resume_btn)
        main_layout.addLayout(btn_layout)
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)

    def log(self, msg: str):
        logger.log_signal.emit(msg)

    def _append_log(self, msg: str):
        self.log_output.append(msg)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _set_progress_max(self, max_value: int):
        self.progress_bar.setMaximum(max_value)

    def _update_progress(self, value: int):
        self.progress_bar.setValue(value)

    def add_file_to_table(self, file_name, status="未下载"):
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        self.file_table.setItem(row, 0, QTableWidgetItem(file_name))
        self.file_table.setItem(row, 1, QTableWidgetItem(status))

    def _update_file_status(self, file_name, status):
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item and item.text() == file_name:
                self.file_table.item(row, 1).setText(status)
                break

    def update_progress_signal(self, file_index, total_files, file_name, status):

        logger.file_status_signal.emit(file_name, status)

        if status in ["已完成", "失败"]:
            self.completed_files += 1
            logger.progress_signal.emit(self.completed_files)

    def extract_links(self):
        input_text = self.link_input.toPlainText()
        links = re.findall(r'https://ibb\.co/[a-zA-Z0-9]+', input_text)
        return list(set(links))

    def start_new_task(self):
        import write_json, read_json, download, get_download_links

        links = self.extract_links()
        if not links:
            QMessageBox.warning(self, "提示", "没有检测到任何有效链接")
            return

        write_json.clear_json()
        self.log(f"检测到 {len(links)} 个链接，正在清空状态并开始下载...")

        self.file_table.setRowCount(0)

        def worker():
            try:
                get_download_links.process_download_links_until_success(links, log_func=self.log)
                self.log("原图链接获取成功，开始下载...")

                url_map = read_json.get_failed_map(log_func=self.log)
                self.total_files = len(url_map)
                self.completed_files = 0
                logger.max_progress_signal.emit(self.total_files)

                for file_name in url_map.values():
                    self.add_file_to_table(file_name, "未下载")

                download.download_files_concurrently(
                    url_map,
                    log_func=self.log,
                    progress_callback=self.update_progress_signal
                )
                self.log("下载完成！")
            except Exception as e:
                self.log(f"发生错误：{e}")

        threading.Thread(target=worker, daemon=True).start()

    def resume_last_task(self):
        from app_state import json_file
        import download, read_json

        if not os.path.exists(json_file) or os.path.getsize(json_file) == 0:
            QMessageBox.information(self, "提示", "未找到上次下载任务")
            return

        self.log("恢复上次下载任务...")

        url_map = read_json.get_failed_map(log_func=self.log)
        self.total_files = len(url_map)
        self.completed_files = 0
        logger.max_progress_signal.emit(self.total_files)

        self.file_table.setRowCount(0)
        for file_name in url_map.values():
            self.add_file_to_table(file_name, "未下载")

        def worker():
            try:
                download.download_files_concurrently(
                    url_map,
                    log_func=self.log,
                    progress_callback=self.update_progress_signal
                )
                self.log("下载完成！")
            except Exception as e:
                self.log(f"发生错误：{e}")

        threading.Thread(target=worker, daemon=True).start()

    def closeEvent(self, event):
        from app_state import shutdown_event, pause_event
        pause_event.set()
        shutdown_event.set()
        self.log("正在安全退出程序...")
        event.accept()

    def toggle_pause(self):
        from app_state import pause_event

        if pause_event.is_set():
            pause_event.clear()
            self.pause_btn.setText("继续")
            self.log("⏸ 下载已暂停")
        else:
            pause_event.set()
            self.pause_btn.setText("暂停")
            self.log("▶ 下载已继续")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImgbbDownloaderApp()
    window.show()
    sys.exit(app.exec())
