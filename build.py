import os
import subprocess
import sys

# --- 项目配置 ---
MAIN_SCRIPT = "gui.py"
APP_NAME = "ImgbbDownloader"
ICON_PATH = "icon.ico"
VERSION = "1.2.2"
COMPANY = "LucKShark"
DESCRIPTION = "Imgbb 批量原图下载器"

# --- Nuitka 命令构建 ---
cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",

    # 更新后的控制台参数
    "--windows-console-mode=disable",

    "--enable-plugin=pyqt6",

    # 修正后的资源文件路径：将 icon.ico 包含在运行根目录
    # 格式为: --include-data-files=源路径=目标路径
    f"--include-data-files={ICON_PATH}=./{ICON_PATH}",
    f"--windows-icon-from-ico={ICON_PATH}",

    # 版本元数据
    f"--output-filename={APP_NAME}",
    f"--windows-company-name={COMPANY}",
    f"--windows-product-name={APP_NAME}",
    f"--windows-file-version={VERSION}.0",
    f"--windows-product-version={VERSION}.0",
    f"--windows-file-description={DESCRIPTION}",

    # 优化
    "--remove-output",
    "--output-dir=dist",

    MAIN_SCRIPT
]

print(f"🚀 开始使用 Nuitka 打包 {APP_NAME} v{VERSION}...")
try:
    # 增加 env 解决某些编码问题
    subprocess.run(cmd, check=True)
    print(f"\n✅ 打包成功！文件已生成在: {os.path.join(os.getcwd(), 'dist')}")
except subprocess.CalledProcessError:
    print("\n❌ 打包过程中出现错误。")