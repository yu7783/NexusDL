"""
Application Settings & Persistence.
Extended with detailed networking, concurrency, and auto-tuning configurations.
"""

import json
import os
from pathlib import Path


class AppSettings:
    """設定管理クラス"""

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "settings.json")
        
        # デフォルト保存先: OSの「ダウンロード」フォルダ
        default_dl = str(Path.home() / "Downloads")
        
        self.data = {
            # 基本設定
            "download_directory": default_dl,
            "appearance_mode": "dark",        # "dark", "light", "system"
            "color_theme": "blue",
            
            # 詳細設定表示トグル
            "show_advanced_settings": False,

            # 速度テスト & 並列化最適化
            "auto_tune_concurrency": True,     # 起動時速度テスト結果で自動チューニング
            "max_concurrency": 4,              # 並列スレッド数
            "chunk_size_kb": 256,              # チャンクサイズ (KB)
            "last_speed_test_mbps": 0.0,
            "last_speed_test_summary": "未計測",

            # ネットワーク詳細設定
            "timeout_seconds": 30,             # HTTPタイムアウト
            "request_retries": 3,              # リトライ回数
            "proxy_url": "",                   # 例: http://127.0.0.1:7890
            "enable_resume": True,             # レジューム機能
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "auto_clear_finished": False,
        }
        self.load()

    def load(self) -> None:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception:
                pass

    def save(self) -> None:
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()
