import os
import subprocess
import sys

MAIN_SCRIPT = "gui.py"
APP_NAME = "ImgbbDownloader"
ICON_PATH = "icon.ico"
VERSION = "1.3.0"
COMPANY = "LucKShark"
DESCRIPTION = "Imgbb 下载器"

cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",

    "--windows-console-mode=disable",

    "--enable-plugin=pyqt6",

    f"--include-data-files={os.path.abspath(ICON_PATH)}={ICON_PATH}",
    f"--windows-icon-from-ico={ICON_PATH}",

    f"--output-filename={APP_NAME}",
    f"--windows-company-name={COMPANY}",
    f"--windows-product-name={APP_NAME}",
    f"--windows-file-version={VERSION}.0",
    f"--windows-product-version={VERSION}.0",
    f"--windows-file-description={DESCRIPTION}",

    "--remove-output",
    "--output-dir=dist",

    MAIN_SCRIPT
]

print(f"🚀Start packing {APP_NAME} v{VERSION}...")
try:
    subprocess.run(cmd, check=True)
    print(f"\nSuccessful! {os.path.join(os.getcwd(), 'dist')}")
except subprocess.CalledProcessError:
    print("\nFailed to pack!")