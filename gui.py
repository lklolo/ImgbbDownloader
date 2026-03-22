import sys
import os
import re
import threading
import ctypes
import platform
import subprocess
from urllib.parse import urlparse

from PyQt6.QtGui import QIcon, QPixmap, QMovie, QCursor, QPainter, QColor, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QSize
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox, QFrame, QProgressBar,
    QFileDialog, QScrollArea, QGridLayout, QSizePolicy, QMenu
)

import app_state
from config import load_config, write_config


def get_resource_path(relative_path):
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_stylesheet(file_path):
    """工具函数：读取 QSS 文件内容"""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

class ImageStatusCard(QFrame):
    def __init__(self, file_name, parent=None):
        super().__init__(parent)
        self.file_name = file_name
        self.full_path = ""
        self.is_completed = False

        self.setFixedSize(160, 190)
        self.setToolTip(f"文件名: {self.file_name}\n状态: 等待解析...")

        # 初始状态属性
        self.setProperty("completed", "false")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 5)
        layout.setSpacing(4)

        self.image_label = QLabel()
        self.image_label.setFixedSize(150, 125)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("CardImage")
        self.image_label.setText("⌛")

        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel()
        self.name_label.setFixedWidth(145)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setObjectName("CardName")

        metrics = self.name_label.fontMetrics()
        elided_name = metrics.elidedText(self.file_name, Qt.TextElideMode.ElideRight, 140)
        self.name_label.setText(elided_name)

        layout.addWidget(self.name_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("待下载")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("CardStatus")
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_image(self, file_path):
        if not os.path.exists(file_path):
            self.set_status("文件丢失", "#f44336")
            return

        self.full_path = file_path
        pixmap = QPixmap(file_path)

        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setText("")

            self.is_completed = True
            self.set_status("已完成")

            # 切换 QSS 属性并刷新样式
            self.setProperty("completed", "true")
            self.style().unpolish(self)
            self.style().polish(self)

            self.setToolTip(f"双击打开: {self.file_name}")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.set_status("损坏图片", "#f44336")

    def set_status(self, text, color=None):
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")
        else:
            self.status_label.setStyleSheet("") # 恢复 QSS 默认

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_completed and self.full_path and os.path.exists(self.full_path):
                self._open_with_system_default(self.full_path)

    def _open_with_system_default(self, path):
        try:
            curr_os = platform.system()
            if curr_os == "Windows":
                os.startfile(path)
            elif curr_os == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            print(f"无法打开图片: {e}")

class Logger(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    max_progress_signal = pyqtSignal(int)
    add_file_signal = pyqtSignal(str)
    file_status_signal = pyqtSignal(str, str)
    preview_signal = pyqtSignal(str)

logger = Logger()

class ImgbbDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Imgbb Downloader")
        self.resize(1000, 900)

        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # --- 应用外部 QSS 样式 ---
        qss_content = load_stylesheet(get_resource_path("style.qss"))
        self.setStyleSheet(qss_content)

        self.config = load_config(log_func=self.log)
        self.load_background_pixmap()
        app_state.download_dir = self.config["download_dir"]
        app_state.task_status_file = self.config["task_status_file"]
        app_state.headers = self.config["headers"]

        self.completed_files = 0
        self.total_files = 0
        self.card_map = {}

        self.init_ui()

        logger.log_signal.connect(self._append_log)
        logger.progress_signal.connect(self._update_progress)
        logger.max_progress_signal.connect(self._set_progress_max)
        logger.add_file_signal.connect(self._pre_create_card)
        logger.file_status_signal.connect(self._update_card_status)
        logger.preview_signal.connect(self._fill_card_image)

    def load_background_pixmap(self):
        """核心修复：优先从 config 读取路径"""
        bg_path = self.config.get("background_path", "")

        # 情况 A: 用户自定义了背景且文件还在
        if bg_path and os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path)
            # self.log(f"已加载自定义背景: {os.path.basename(bg_path)}")

        # 情况 B: 没有自定义，或者自定义的文件被删了，尝试读取默认 background.jpg
        else:
            default_bg = get_resource_path("background.jpg")
            if os.path.exists(default_bg):
                self.bg_pixmap = QPixmap(default_bg)
            else:
                self.bg_pixmap = None

        # 强制界面重绘
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 启用抗锯齿和高质量缩放，防止图片变糊
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 检查背景图是否存在且有效
        if hasattr(self, 'bg_pixmap') and self.bg_pixmap and not self.bg_pixmap.isNull():
            win_size = self.size()
            pix_size = self.bg_pixmap.size()

            # --- 1. 计算缩放比例 (KeepAspectRatioByExpanding) ---
            # 我们需要图片完全覆盖窗口，所以选择宽高缩放比中较大的那个
            scale_w = win_size.width() / pix_size.width()
            scale_h = win_size.height() / pix_size.height()
            scale = max(scale_w, scale_h)

            # 计算缩放后的实际尺寸
            draw_w = int(pix_size.width() * scale)
            draw_h = int(pix_size.height() * scale)

            # --- 2. 计算居中偏移量 (Center) ---
            # 将缩放后的图片中心与窗口中心对齐
            # 起始坐标 = (窗口尺寸 - 绘制尺寸) / 2
            # 结果通常是负数（图片左上角在窗口外面）
            draw_x = (win_size.width() - draw_w) // 2
            draw_y = (win_size.height() - draw_h) // 2

            # --- 3. 绘制图片 ---
            # 使用计算出的坐标和尺寸绘制
            painter.drawPixmap(draw_x, draw_y, draw_w, draw_h, self.bg_pixmap)

        else:
            # 如果没有背景图，绘制深色背景
            painter.fillRect(self.rect(), QColor(30, 30, 30))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)

        # 设置栏
        settings_frame = QFrame()
        settings_frame.setObjectName("GlassBlock")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(15, 10, 15, 10)

        dir_layout = QHBoxLayout()
        self.download_dir_label = QLabel(self.config["download_dir"])
        self.download_dir_label.setObjectName("PathLabel")
        self.download_dir_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dir_layout.addWidget(QLabel("📂"), stretch=0)
        dir_layout.addWidget(self.download_dir_label, stretch=1)

        self.choose_dir_btn = QPushButton("选择...")
        self.choose_dir_btn.setFixedWidth(70)
        self.choose_dir_btn.clicked.connect(self.choose_download_dir)
        dir_layout.addWidget(self.choose_dir_btn)

        self.reset_dir_btn = QPushButton("恢复")
        self.reset_dir_btn.setFixedWidth(60)
        self.reset_dir_btn.clicked.connect(self.reset_download_dir)
        dir_layout.addWidget(self.reset_dir_btn)

        settings_layout.addLayout(dir_layout)
        main_layout.addWidget(settings_frame)

        # 输入与日志
        input_log_layout = QHBoxLayout()
        input_log_layout.setSpacing(15)

        input_frame = QFrame()
        input_frame.setObjectName("GlassBlock")
        input_layout = QVBoxLayout(input_frame)

        self.link_input = QTextEdit()
        self.link_input.setPlaceholderText("在此粘贴相册链接或嵌入代码...")
        self.link_input.setFixedHeight(120)
        input_layout.addWidget(self.link_input)

        self.password_input = QTextEdit()
        self.password_input.setPlaceholderText("相册密码（可选）")
        self.password_input.setFixedHeight(35)
        input_layout.addWidget(self.password_input)

        input_log_layout.addWidget(input_frame, stretch=1)

        log_frame = QFrame()
        log_frame.setObjectName("GlassBlock")
        log_layout = QVBoxLayout(log_frame)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("LogOutput")
        log_layout.addWidget(self.log_output)

        input_log_layout.addWidget(log_frame, stretch=1)
        main_layout.addLayout(input_log_layout)

        # 图片预览区
        grid_frame = QFrame()
        grid_frame.setObjectName("GlassBlock")
        grid_layout_outer = QVBoxLayout(grid_frame)
        grid_layout_outer.setContentsMargins(10, 10, 10, 10)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("🖼️ 下载队列"))
        header_layout.addStretch()
        grid_layout_outer.addLayout(header_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("PreviewScroll")

        self.preview_container = QWidget()
        self.preview_container.setObjectName("TransparentWidget")
        self.preview_grid = QGridLayout(self.preview_container)
        self.preview_grid.setSpacing(10)
        self.preview_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.preview_container)
        grid_layout_outer.addWidget(self.scroll_area)

        main_layout.addWidget(grid_frame, stretch=3)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.start_btn = QPushButton("开始新任务")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.clicked.connect(self.start_new_task)
        btn_layout.addWidget(self.start_btn)

        self.resume_btn = QPushButton("恢复上次下载")
        self.resume_btn.clicked.connect(self.resume_last_task)
        btn_layout.addWidget(self.resume_btn)

        btn_layout.addStretch()

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setFixedWidth(80)
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)
        main_layout.addLayout(btn_layout)

        # --- 创建浮动齿轮按钮 ---
        self.bg_settings_btn = QPushButton("⚙️")
        self.bg_settings_btn.setObjectName("SettingsIconBtn")
        self.bg_settings_btn.setFixedSize(40, 40)

        self.bg_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_settings_btn.clicked.connect(self.show_bg_menu)
        btn_layout.addWidget(self.bg_settings_btn)

    def log(self, msg: str): logger.log_signal.emit(msg)

    def _append_log(self, msg: str):
        self.log_output.append(msg)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _set_progress_max(self, max_value: int): self.progress_bar.setMaximum(max_value)
    def _update_progress(self, value: int): self.progress_bar.setValue(value)

    def _pre_create_card(self, file_name):
        if file_name in self.card_map: return
        card = ImageStatusCard(file_name)
        count = len(self.card_map)
        row = count // 5
        col = count % 5
        self.preview_grid.addWidget(card, row, col)
        self.card_map[file_name] = card

    def _update_card_status(self, file_name, status_text):
        card = self.card_map.get(file_name)
        if not card: return
        if status_text == "下载中":
            card.set_status("⏳ 下载中...", "#ffeb3b")
        elif status_text == "失败":
            card.set_status("❌ 失败", "#ff5252")
        elif status_text == "待下载":
            card.set_status("待下载")

    def _fill_card_image(self, full_file_path):
        file_name = os.path.basename(full_file_path)
        card = self.card_map.get(file_name)
        if not card: return
        card.set_image(full_file_path)

    def update_progress_signal(self, file_index, total_files, file_name, status):
        if status != "已完成":
            logger.file_status_signal.emit(file_name, status)
        if status in ["已完成", "失败"]:
            self.completed_files += 1
            logger.progress_signal.emit(self.completed_files)
            if status == "已完成":
                full_path = os.path.join(app_state.download_dir, file_name)
                logger.preview_signal.emit(full_path)

    def _clear_grid(self):
        self.card_map.clear()
        while self.preview_grid.count():
            item = self.preview_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def start_new_task(self):
        import task_status, download, get_download_links
        links = self.extract_links()
        if not links:
            QMessageBox.warning(self, "提示", "没有检测到任何有效链接")
            return
        task_status.clear_json()
        self.log(f"✔ 检测到 {len(links)} 个链接，正在解析...")
        self._clear_grid()
        def worker():
            try:
                password = self.password_input.toPlainText().strip() or None
                if get_download_links.process_download_links_until_success(
                        links, album_password=password, log_func=self.log
                ) is False: return
                url_map = task_status.get_failed_map(log_func=self.log)
                self.total_files = len(url_map)
                self.completed_files = 0
                logger.max_progress_signal.emit(self.total_files)
                for file_name in url_map.values():
                    logger.add_file_signal.emit(file_name)
                self.log(f"✔ 成功获取 {self.total_files} 张原图链接，准备下载...")
                download.download_files_concurrently(
                    url_map,
                    log_func=self.log,
                    progress_callback=self.update_progress_signal
                )
                self.log("🎉 所有下载任务已处理完成！")
            except Exception as e:
                self.log(f"❗ 发生全局错误：{e}")
        threading.Thread(target=worker, daemon=True).start()

    def resume_last_task(self):
        from app_state import task_status_file
        import download, task_status
        if not os.path.exists(task_status_file) or os.path.getsize(task_status_file) == 0:
            QMessageBox.information(self, "提示", "未找到上次下载任务的状态文件")
            return
        self._clear_grid()
        self.log("🔁 恢复上次未完成的下载任务...")
        url_map = task_status.get_failed_map(log_func=self.log)
        self.total_files = len(url_map)
        self.completed_files = 0
        logger.max_progress_signal.emit(self.total_files)
        for file_name in url_map.values():
            logger.add_file_signal.emit(file_name)
        def worker():
            try:
                download.download_files_concurrently(
                    url_map,
                    log_func=self.log,
                    progress_callback=self.update_progress_signal
                )
                self.log("🎉 恢复的任务已处理完成！")
            except Exception as e:
                self.log(f"❗ 发生错误：{e}")
        threading.Thread(target=worker, daemon=True).start()

    def extract_links(self):
        input_text = self.link_input.toPlainText()
        links = re.findall(r'https://ibb\.co/(?:album/[A-Za-z0-9]+|[A-Za-z0-9]+)', input_text)
        return list(set(links))

    def closeEvent(self, event):
        from app_state import shutdown_event, pause_event
        self.log("📴 正在安全退出...")
        pause_event.set()
        shutdown_event.set()
        event.accept()

    def toggle_pause(self):
        from app_state import pause_event
        if pause_event.is_set():
            pause_event.clear()
            self.pause_btn.setText("继续")
            self.pause_btn.setObjectName("PauseBtnActive")
            self.log("⏸️ 下载已暂停")
        else:
            pause_event.set()
            self.pause_btn.setText("暂停")
            self.pause_btn.setObjectName("")
            self.log("▶️ 下载已继续")

        # 强制更新 QSS
        self.pause_btn.style().unpolish(self.pause_btn)
        self.pause_btn.style().polish(self.pause_btn)

    def choose_download_dir(self):
        from config import write_config
        import task_status
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", self.config.get("download_dir", os.getcwd()))
        if not dir_path: return
        os.makedirs(dir_path, exist_ok=True)
        self.config["download_dir"] = dir_path
        write_config(self.config)
        app_state.download_dir = dir_path
        task_status.reset_all_to_pending(log_func=self.log)
        self.download_dir_label.setText(dir_path)
        self.log(f"📁 下载目录已切换：{dir_path}")

    def reset_download_dir(self):
        from config import write_config, default_config
        import task_status
        default_dir = default_config["download_dir"]
        reply = QMessageBox.question(self, "恢复默认", f"确定要恢复默认下载目录吗？\n\n{default_dir}", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        os.makedirs(default_dir, exist_ok=True)
        self.config["download_dir"] = default_dir
        write_config(self.config)
        app_state.download_dir = default_dir
        task_status.reset_all_to_pending(log_func=self.log)
        self.download_dir_label.setText(default_dir)
        self.log("🔄 下载目录已恢复默认")

    def show_bg_menu(self):
        """显示背景设置菜单"""
        menu = QMenu(self)
        change_action = QAction("🖼️ 更换背景图片", self)
        reset_action = QAction("🔄 恢复默认背景", self)

        change_action.triggered.connect(self.change_background)
        reset_action.triggered.connect(self.reset_background)

        menu.addAction(change_action)
        menu.addAction(reset_action)
        menu.exec(self.bg_settings_btn.mapToGlobal(self.bg_settings_btn.rect().bottomLeft()))

    def change_background(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.config["background_path"] = file_path
            write_config(self.config)
            self.load_background_pixmap()
            self.update() # 触发重绘
            self.log(f"✅ 背景已更换为: {os.path.basename(file_path)}")

    def reset_background(self):
        self.config["background_path"] = ""
        write_config(self.config)
        self.load_background_pixmap()
        self.update()
        self.log("🔄 已恢复默认背景")

    def resizeEvent(self, event):
        """窗口大小改变时，重新计算背景和齿轮位置"""
        super().resizeEvent(event)

        # 1. 如果你使用了背景缓存，记得更新它
        if hasattr(self, 'update_background_cache'):
            self.update_background_cache()

        # 2. 计算齿轮位置：右边距 20px，下边距 20px
        margin = 20
        btn_w = self.bg_settings_btn.width()
        btn_h = self.bg_settings_btn.height()

        new_x = self.width() - btn_w - margin
        new_y = self.height() - btn_h - margin

        self.bg_settings_btn.move(new_x, new_y)

if __name__ == "__main__":
    try:
        myappid = 'luckshark.imgbbdownloader.pro'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception: pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ImgbbDownloaderApp()
    window.show()
    sys.exit(app.exec())