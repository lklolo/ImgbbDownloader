import os
import yaml

CONFIG_FILE = "config.yaml"
default_config = {
    "download_dir": "downloads",
    "task_status_file": "task_status.json",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
        "Accept": "application/octet-stream",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
}

def load_config(log_func=print):
    if not os.path.exists(CONFIG_FILE):
        write_config(default_config)
        return default_config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict):
                raise ValueError("❗ 配置格式错误：应为字典类型")
            return merge_with_default(config, default_config)
    except (yaml.YAMLError, ValueError) as e:
        log_func(f"❗ 配置文件读取失败：{e}")
        backup_path = CONFIG_FILE + ".bak"
        os.rename(CONFIG_FILE, backup_path)
        log_func(f"🔁 正在恢复默认配置...已将损坏的配置重命名为：{backup_path}")
        write_config(default_config)
        return default_config

def write_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

def merge_with_default(user_cfg, default_cfg):
    for key, value in default_cfg.items():
        if key not in user_cfg:
            user_cfg[key] = value
        elif isinstance(value, dict):
            user_cfg[key] = merge_with_default(user_cfg.get(key, {}), value)
    return user_cfg