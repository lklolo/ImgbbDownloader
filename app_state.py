import threading

shutdown_event = threading.Event()
pause_event = threading.Event()
pause_event.set()

DOWNLOAD_DIR = None
json_file = None
headers = None
