import threading

shutdown_event = threading.Event()
pause_event = threading.Event()
pause_event.set()

download_dir = None
task_status_file = None
headers = None
