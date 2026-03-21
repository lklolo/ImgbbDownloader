import sys
import os
import re
import threading
import ctypes

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox, QFrame, QProgressBar,
    QTableWidget, QTableWidgetItem, QAbstractItemView,QFileDialog
)
from PyQt6.QtWidgets import QScrollArea, QGridLayout

import app_state
from config import load_config

def get_resource_path(relative_path):
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class Logger(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    max_progress_signal = pyqtSignal(int)
    file_status_signal = pyqtSignal(str, str)
    add_file_signal = pyqtSignal(str, str)
    preview_signal = pyqtSignal(str)

logger = Logger()

class ImgbbDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Imgbb下载器")
        self.resize(700, 1000)
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ffffff; font-family: Arial; }
        """)

        self.config = load_config(log_func=self.log)
        app_state.download_dir = self.config["download_dir"]
        app_state.task_status_file = self.config["task_status_file"]
        app_state.headers = self.config["headers"]

        self.completed_files = 0
        self.total_files = 0

        self.init_ui()

        logger.log_signal.connect(self._append_log)
        logger.progress_signal.connect(self._update_progress)
        logger.max_progress_signal.connect(self._set_progress_max)
        logger.file_status_signal.connect(self._update_file_status)
        logger.add_file_signal.connect(self.add_file_to_table)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(8)

        dir_layout = QHBoxLayout()
        dir_label = QLabel("下载目录：")
        dir_layout.addWidget(dir_label)
        
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        self.reset_dir_btn = QPushButton("恢复默认")
        self.reset_dir_btn.setToolTip("恢复默认下载目录")
        self.reset_dir_btn.clicked.connect(self.reset_download_dir)
        reset_layout.addWidget(self.reset_dir_btn)
        settings_layout.addLayout(reset_layout)
        
        
        self.download_dir_label = QLabel(self.config["download_dir"])
        self.download_dir_label.setStyleSheet(
            "color:#a9b7c6; border:1px solid #555; padding:4px; border-radius:4px;")
        self.download_dir_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        dir_layout.addWidget(self.download_dir_label, stretch=1)
        self.choose_dir_btn = QPushButton("选择目录")
        self.choose_dir_btn.clicked.connect(self.choose_download_dir)
        dir_layout.addWidget(self.choose_dir_btn)
        settings_layout.addLayout(dir_layout)
        main_layout.addWidget(settings_frame)

        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 12, 12, 12)

        input_label = QLabel("请输入相册内嵌入代码（仅支持无密码相册），或相册链接")
        input_layout.addWidget(input_label)

        self.link_input = QTextEdit()
        self.link_input.setAcceptRichText(False)
        self.link_input.setFixedHeight(150)
        self.link_input.setStyleSheet("background-color: #2b2b2b; color: #ffffff; border:1px solid #555555; border-radius:5px;")
        input_layout.addWidget(self.link_input)
        main_layout.addWidget(input_frame)
        self.password_input = QTextEdit()
        
        self.password_input.setPlaceholderText("相册密码（可选）")
        self.password_input.setFixedHeight(40)
        input_layout.addWidget(self.password_input)
        
        log_frame = QFrame()
        log_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 12, 12, 12)

        log_label = QLabel("日志")
        log_layout.addWidget(log_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #2b2b2b; color: #ffffff; border:1px solid #555555; border-radius:5px;")
        log_layout.addWidget(self.log_output)
        main_layout.addWidget(log_frame, stretch=1)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["文件", "状态"])
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setStyleSheet("""
            QTableWidget { background-color: #2b2b2b; color: #ffffff; gridline-color:#555555; }
            QHeaderView::section { background-color:#3c3f41; color:#ffffff; }
        """)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
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
        self.resume_btn = QPushButton("恢复上次的下载")
        self.resume_btn.clicked.connect(self.resume_last_task)
        btn_layout.addWidget(self.resume_btn)
        main_layout.addLayout(btn_layout)
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)

        # --- 预览区 (替换或放在 file_table 之后) ---
        preview_frame = QFrame()
        preview_frame.setStyleSheet("background-color: #3c3f41; border-radius: 8px;")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.addWidget(QLabel("实时预览"))

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: #2b2b2b;")

        self.preview_container = QWidget()
        self.preview_grid = QGridLayout(self.preview_container)
        self.preview_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.preview_container)

        preview_layout.addWidget(self.scroll_area)
        main_layout.addWidget(preview_frame, stretch=2) # 预览区可以占更多空间

        # 记录当前预览图的数量，用于计算网格位置
        self.preview_count = 0

        # 绑定信号
        logger.preview_signal.connect(self._add_preview_card)

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

        if status == "已完成":
            self.completed_files += 1
            logger.progress_signal.emit(self.completed_files)

            # 新增：构造完整路径并通知 UI 显示预览
            full_path = os.path.join(app_state.download_dir, file_name)
            logger.preview_signal.emit(full_path)

        elif status == "失败":
            self.completed_files += 1
            logger.progress_signal.emit(self.completed_files)

    def extract_links(self):
        input_text = self.link_input.toPlainText()
        links = re.findall(
            r'https://ibb\.co/(?:album/[A-Za-z0-9]+|[A-Za-z0-9]+)',
            input_text
        )
        return list(set(links))

    def _add_preview_card(self, file_path):
        """动态添加缩略图卡片"""
        if not os.path.exists(file_path):
            return

        card = QWidget()
        card_layout = QVBoxLayout(card)

        img_label = QLabel()
        img_label.setFixedSize(120, 120)
        img_label.setScaledContents(True)
        img_label.setStyleSheet("border-radius: 5px; background-color: #444;")

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            img_label.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

        name_label = QLabel(os.path.basename(file_path))
        name_label.setFixedWidth(120)
        name_label.setStyleSheet("font-size: 10px; color: #a9b7c6;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(img_label)
        card_layout.addWidget(name_label)

        # 计算网格位置（每行 4 个）
        row = self.preview_count // 4
        col = self.preview_count % 4
        self.preview_grid.addWidget(card, row, col)
        self.preview_count += 1

    def start_new_task(self):
        import task_status, download, get_download_links
        links = self.extract_links()
        if not links:
            QMessageBox.warning(self, "提示", "没有检测到任何有效链接")
            return

        task_status.clear_json()
        self.log(f"✔ 检测到 {len(links)} 个链接，正在清空状态并准备下载...")

        self.file_table.setRowCount(0)

        # --- 新增：重置 UI 状态 ---
        self.file_table.setRowCount(0)
        self.preview_count = 0
        # 清除预览网格中的所有组件
        while self.preview_grid.count():
            item = self.preview_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        # -----------------------

        def worker():
            try:
                password = self.password_input.toPlainText().strip() or None

                get_download_links.process_download_links_until_success(
                    links,
                    album_password=password,
                    log_func=self.log
                )
                
                self.log("✔ 原图获取成功，开始下载...")

                url_map = task_status.get_failed_map(log_func=self.log)
                self.total_files = len(url_map)
                self.completed_files = 0
                logger.max_progress_signal.emit(self.total_files)

                
                for file_name in url_map.values():
                    logger.add_file_signal.emit(file_name, "未下载")

                download.download_files_concurrently(
                    url_map,
                    log_func=self.log,
                    progress_callback=self.update_progress_signal
                )
                self.log("🎉 下载完成！")
            except Exception as e:
                self.log(f"❗ 发生错误：{e}")

        threading.Thread(target=worker, daemon=True).start()

    def resume_last_task(self):
        from app_state import task_status_file
        import download, task_status

        if not os.path.exists(task_status_file) or os.path.getsize(task_status_file) == 0:
            QMessageBox.information(self, "提示", "未找到上次下载任务")
            return

        self.log("🔁 恢复上次下载任务...")

        url_map = task_status.get_failed_map(log_func=self.log)
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
                self.log("🎉 下载完成！")
            except Exception as e:
                self.log(f"❗ 发生错误：{e}")

        threading.Thread(target=worker, daemon=True).start()

    def closeEvent(self, event):
        from app_state import shutdown_event, pause_event
        self.log("📴 正在安全退出程序...")
        pause_event.set()
        shutdown_event.set()
        event.accept()
    
    def toggle_pause(self):
        from app_state import pause_event

        if pause_event.is_set():
            pause_event.clear()
            self.pause_btn.setText("继续")
            self.log("⏸️ 下载已暂停")
        else:
            pause_event.set()
            self.pause_btn.setText("暂停")
            self.log("▶️ 下载已继续")

    def choose_download_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        from config import write_config
        import app_state
        import task_status
    
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.config.get("download_dir", os.getcwd())
        )
    
        if not dir_path:
            return
    
        os.makedirs(dir_path, exist_ok=True)

        self.config["download_dir"] = dir_path
        write_config(self.config)

        app_state.download_dir = dir_path
        task_status.reset_all_to_pending(log_func=self.log)
        self.download_dir_label.setText(dir_path)
    
        self.log(f"📁 下载目录已切换为：{dir_path}")

    def reset_download_dir(self):
        from config import write_config, default_config
        import app_state
        import task_status
    
        default_dir = default_config["download_dir"]
    
        reply = QMessageBox.question(
            self,
            "恢复默认设置",
            f"确定要将下载目录恢复为默认值吗？\n\n{default_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
    
        if reply != QMessageBox.StandardButton.Yes:
            return
    
        os.makedirs(default_dir, exist_ok=True)
    
        self.config["download_dir"] = default_dir
        write_config(self.config)
    
        app_state.download_dir = default_dir
        task_status.reset_all_to_pending(log_func=self.log)
    
        self.download_dir_label.setText(default_dir)
        self.log("🔄 下载目录已恢复为默认")

if __name__ == "__main__":
    try:
        myappid = 'luckshark.imgbbdownloader'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ImgbbDownloaderApp()
    window.show()
    sys.exit(app.exec())
