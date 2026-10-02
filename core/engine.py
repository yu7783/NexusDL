"""
Multi-threaded Download Engine.
Handles streaming, chunk writing, progress telemetry (speed, ETA), resume, retries, and proxies.
Supports add-on dynamic options routing (Quality, Resolution, Format).
"""

import collections
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional
from urllib.parse import unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from plugins.base import BaseSiteExtractor, DownloadTarget

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    IDLE = "待機中"
    EXTRACTING = "URL解析中..."
    CONNECTING = "サーバー接続中..."
    DOWNLOADING = "ダウンロード中"
    COMPLETED = "完了"
    FAILED = "エラー"
    CANCELLED = "キャンセル済み"


@dataclass
class TelemetryData:
    task_id: str
    status: TaskStatus
    filename: str
    downloaded_bytes: int
    total_bytes: Optional[int]
    progress: float             # 0.0 to 1.0 (or -1.0 if indeterminate)
    speed_bps: float            # bytes per second
    speed_str: str              # e.g. "12.4 MB/s"
    eta_seconds: Optional[int]  # remaining seconds
    eta_str: str                # e.g. "00:15"
    error_message: Optional[str] = None
    save_path: Optional[str] = None


def format_bytes(num_bytes: Optional[int]) -> str:
    if num_bytes is None or num_bytes < 0:
        return "不明"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_speed(bps: float) -> str:
    if bps <= 0:
        return "0 KB/s"
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    else:
        return f"{bps / (1024 * 1024):.2f} MB/s"


def format_eta(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    if seconds > 3600 * 24:
        return "> 1日"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[\r\n\t\x00-\x1f\x7f]', ' ', filename)
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    base_name, ext = os.path.splitext(sanitized)
    base_name = base_name.strip().strip('.')
    if len(base_name) > 80:
        base_name = base_name[:80].strip()
    ext = ext.strip()[:10]
    result = f"{base_name}{ext}" if base_name else f"downloaded_file{ext}"
    return result


class DownloadTask:
    """単一のダウンロードタスクの実行・追跡インスタンス"""

    def __init__(
        self,
        task_id: str,
        input_url: str,
        save_dir: str,
        extractor: Optional[BaseSiteExtractor],
        selected_options: Optional[Dict[str, str]] = None,
        telemetry_callback: Optional[Callable[[TelemetryData], None]] = None,
        chunk_size_kb: int = 256,
        timeout_seconds: int = 30,
        request_retries: int = 3,
        proxy_url: Optional[str] = None,
        enable_resume: bool = True,
        user_agent: Optional[str] = None,
    ):
        self.task_id = task_id
        self.input_url = input_url
        self.save_dir = save_dir
        self.extractor = extractor
        self.selected_options = selected_options or {}
        self.telemetry_callback = telemetry_callback
        self.chunk_size = max(16, chunk_size_kb) * 1024
        self.timeout_seconds = timeout_seconds
        self.request_retries = request_retries
        self.proxy_url = proxy_url.strip() if proxy_url else None
        self.enable_resume = enable_resume
        self.user_agent = user_agent

        self.status = TaskStatus.IDLE
        self.filename = "解析待ち..."
        self.save_path: Optional[str] = None
        self.downloaded_bytes = 0
        self.total_bytes: Optional[int] = None
        self.error_message: Optional[str] = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._history = collections.deque(maxlen=10)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=f"Worker-{self.task_id}", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._stop_event.set()
        if self.status in (TaskStatus.EXTRACTING, TaskStatus.CONNECTING, TaskStatus.DOWNLOADING):
            self.status = TaskStatus.CANCELLED
            self._notify_telemetry(0.0, None)

    def _notify_telemetry(self, speed_bps: float, eta_sec: Optional[int]) -> None:
        if not self.telemetry_callback:
            return

        prog = 0.0
        if self.total_bytes and self.total_bytes > 0:
            prog = min(1.0, max(0.0, self.downloaded_bytes / self.total_bytes))
        elif self.status == TaskStatus.COMPLETED:
            prog = 1.0

        telemetry = TelemetryData(
            task_id=self.task_id,
            status=self.status,
            filename=self.filename,
            downloaded_bytes=self.downloaded_bytes,
            total_bytes=self.total_bytes,
            progress=prog,
            speed_bps=speed_bps,
            speed_str=format_speed(speed_bps),
            eta_seconds=eta_sec,
            eta_str=format_eta(eta_sec),
            error_message=self.error_message,
            save_path=self.save_path,
        )
        self.telemetry_callback(telemetry)

    def _run(self) -> None:
        temp_path = None
        try:
            # 1. プラグイン解析フェーズ (ユーザー指定オプションを渡す)
            self.status = TaskStatus.EXTRACTING
            self._notify_telemetry(0.0, None)

            if not self.extractor:
                raise ValueError("対応するプラグインが見つかりません。")

            target: DownloadTarget = self.extractor.extract(self.input_url, selected_options=self.selected_options)
            if not target or not target.source_url:
                raise ValueError("プラグインからのダウンロードURL取得に失敗しました。")

            if self._stop_event.is_set():
                self.status = TaskStatus.CANCELLED
                self._notify_telemetry(0.0, None)
                return

            raw_filename = target.filename
            if not raw_filename:
                parsed_path = urlparse(target.source_url).path
                raw_filename = unquote(os.path.basename(parsed_path)) or "downloaded_file.bin"

            self.filename = sanitize_filename(raw_filename)
            os.makedirs(self.save_dir, exist_ok=True)
            self.save_path = os.path.join(self.save_dir, self.filename)

            # 2. セッション作成
            session = requests.Session()
            if self.request_retries > 0:
                retries = Retry(
                    total=self.request_retries,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504]
                )
                adapter = HTTPAdapter(max_retries=retries)
                session.mount("http://", adapter)
                session.mount("https://", adapter)

            if self.proxy_url:
                session.proxies = {
                    "http": self.proxy_url,
                    "https": self.proxy_url
                }

            # 3. 接続・レジューム検証フェーズ
            self.status = TaskStatus.CONNECTING
            self._notify_telemetry(0.0, None)

            req_headers = {}
            if self.user_agent:
                req_headers["User-Agent"] = self.user_agent
            if target.headers:
                req_headers.update(target.headers)

            temp_path = self.save_path + ".part"
            existing_size = 0
            file_mode = "wb"

            if self.enable_resume and os.path.exists(temp_path):
                existing_size = os.path.getsize(temp_path)
                if existing_size > 0:
                    req_headers["Range"] = f"bytes={existing_size}-"
                    file_mode = "ab"

            response = None
            try:
                response = session.get(
                    target.source_url,
                    headers=req_headers,
                    stream=True,
                    timeout=self.timeout_seconds
                )
            except Exception as conn_err:
                if existing_size > 0:
                    existing_size = 0
                    file_mode = "wb"
                    req_headers.pop("Range", None)
                    response = session.get(
                        target.source_url,
                        headers=req_headers,
                        stream=True,
                        timeout=self.timeout_seconds
                    )
                else:
                    raise conn_err

            if existing_size > 0 and response.status_code in (403, 416):
                existing_size = 0
                file_mode = "wb"
                req_headers.pop("Range", None)
                response = session.get(
                    target.source_url,
                    headers=req_headers,
                    stream=True,
                    timeout=self.timeout_seconds
                )
            elif existing_size > 0 and response.status_code == 200:
                existing_size = 0
                file_mode = "wb"

            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                self.total_bytes = existing_size + int(content_length)
            elif target.expected_size:
                self.total_bytes = target.expected_size

            # 4. ダウンロードストリーミングフェーズ
            self.status = TaskStatus.DOWNLOADING
            self.downloaded_bytes = existing_size
            start_time = time.time()
            self._history.append((start_time, self.downloaded_bytes))
            last_ui_update = 0.0

            with open(temp_path, file_mode) as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if self._stop_event.is_set():
                        self.status = TaskStatus.CANCELLED
                        break

                    if chunk:
                        f.write(chunk)
                        self.downloaded_bytes += len(chunk)

                        now = time.time()
                        self._history.append((now, self.downloaded_bytes))

                        if now - last_ui_update >= 0.12:
                            last_ui_update = now
                            earliest_time, earliest_bytes = self._history[0]
                            time_delta = now - earliest_time
                            bytes_delta = self.downloaded_bytes - earliest_bytes

                            current_speed = (bytes_delta / time_delta) if time_delta > 0.05 else 0.0

                            eta_sec = None
                            if self.total_bytes and current_speed > 0:
                                remaining_bytes = max(0, self.total_bytes - self.downloaded_bytes)
                                eta_sec = int(remaining_bytes / current_speed)

                            self._notify_telemetry(current_speed, eta_sec)

            if self._stop_event.is_set():
                self.status = TaskStatus.CANCELLED
                self._notify_telemetry(0.0, None)
                return

            if os.path.exists(self.save_path):
                try:
                    os.remove(self.save_path)
                except Exception:
                    pass
            os.rename(temp_path, self.save_path)

            self.status = TaskStatus.COMPLETED
            self._notify_telemetry(0.0, 0)

        except Exception as e:
            logger.exception("Download task encountered an error")
            self.status = TaskStatus.FAILED
            self.error_message = str(e)
            self._notify_telemetry(0.0, None)


class DownloadManager:
    """ダウンローダーの全体キューと実行管理"""

    def __init__(
        self,
        chunk_size_kb: int = 256,
        timeout_seconds: int = 30,
        request_retries: int = 3,
        proxy_url: Optional[str] = None,
        enable_resume: bool = True,
        user_agent: Optional[str] = None
    ):
        self.chunk_size_kb = chunk_size_kb
        self.timeout_seconds = timeout_seconds
        self.request_retries = request_retries
        self.proxy_url = proxy_url
        self.enable_resume = enable_resume
        self.user_agent = user_agent
        self.tasks: dict[str, DownloadTask] = {}
        self._lock = threading.Lock()

    def update_config(
        self,
        chunk_size_kb: int,
        timeout_seconds: int = 30,
        request_retries: int = 3,
        proxy_url: Optional[str] = None,
        enable_resume: bool = True
    ):
        with self._lock:
            self.chunk_size_kb = chunk_size_kb
            self.timeout_seconds = timeout_seconds
            self.request_retries = request_retries
            self.proxy_url = proxy_url
            self.enable_resume = enable_resume

    def start_download(
        self,
        task_id: str,
        url: str,
        save_dir: str,
        extractor: Optional[BaseSiteExtractor],
        selected_options: Optional[Dict[str, str]] = None,
        telemetry_callback: Callable[[TelemetryData], None] = None
    ) -> DownloadTask:
        with self._lock:
            task = DownloadTask(
                task_id=task_id,
                input_url=url,
                save_dir=save_dir,
                extractor=extractor,
                selected_options=selected_options,
                telemetry_callback=telemetry_callback,
                chunk_size_kb=self.chunk_size_kb,
                timeout_seconds=self.timeout_seconds,
                request_retries=self.request_retries,
                proxy_url=self.proxy_url,
                enable_resume=self.enable_resume,
                user_agent=self.user_agent
            )
            self.tasks[task_id] = task
            task.start()
            return task

    def cancel_task(self, task_id: str) -> None:
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.cancel()

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self._lock:
            return self.tasks.get(task_id)
