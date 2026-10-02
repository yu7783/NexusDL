"""
Startup Network Speed Benchmark & Auto-Tuning Engine.
Measures latency and bandwidth to optimize concurrency and chunk buffer sizes.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SpeedBenchmarkResult:
    latency_ms: float
    bandwidth_mbps: float
    recommended_concurrency: int
    recommended_chunk_kb: int
    summary_text: str


class NetworkSpeedTester:
    """軽量ネットワークベンチマーク測定器"""

    # 計測用エンドポイント (Cloudflare / GitHub Fast CDN などの軽量ファイル)
    TEST_ENDPOINTS = [
        "https://speed.cloudflare.com/__down?bytes=5000000",   # 5MB
        "https://proof.ovh.net/files/1Mio.dat",                # 1MB
    ]

    @classmethod
    def run_benchmark(cls, progress_callback: Optional[Callable[[str], None]] = None) -> SpeedBenchmarkResult:
        if progress_callback:
            progress_callback("レイテンシ測定中...")

        latency_ms = cls._measure_latency()
        
        if progress_callback:
            progress_callback("回線帯域テスト中...")

        bandwidth_mbps = cls._measure_download_speed()

        # 速度に応じた並列化・バッファ推奨値の自動算出
        if bandwidth_mbps < 15.0:  # 〜15Mbps
            rec_concurrency = 2
            rec_chunk = 128
        elif bandwidth_mbps < 60.0:  # 15〜60Mbps
            rec_concurrency = 4
            rec_chunk = 256
        elif bandwidth_mbps < 150.0: # 60〜150Mbps
            rec_concurrency = 8
            rec_chunk = 512
        else:                        # 150Mbps〜
            rec_concurrency = 12
            rec_chunk = 1024

        summary = (
            f"{bandwidth_mbps:.1f} Mbps (遅延 {latency_ms:.0f}ms) "
            f"→ 推奨並列数: {rec_concurrency} / チャンク: {rec_chunk}KB"
        )

        return SpeedBenchmarkResult(
            latency_ms=latency_ms,
            bandwidth_mbps=bandwidth_mbps,
            recommended_concurrency=rec_concurrency,
            recommended_chunk_kb=rec_chunk,
            summary_text=summary
        )

    @classmethod
    def _measure_latency(cls) -> float:
        url = "https://www.google.com/generate_204"
        latencies = []
        for _ in range(2):
            try:
                t0 = time.perf_counter()
                requests.head(url, timeout=4)
                latencies.append((time.perf_counter() - t0) * 1000)
            except Exception:
                pass
        return sum(latencies) / len(latencies) if latencies else 50.0

    @classmethod
    def _measure_download_speed(cls) -> float:
        for url in cls.TEST_ENDPOINTS:
            try:
                t0 = time.perf_counter()
                resp = requests.get(url, stream=True, timeout=6)
                if resp.status_code != 200:
                    continue

                total_downloaded = 0
                max_bytes = 4 * 1024 * 1024  # 最大4MBまで取得して速度を測定
                for chunk in resp.iter_content(chunk_size=128 * 1024):
                    if not chunk:
                        break
                    total_downloaded += len(chunk)
                    elapsed = time.perf_counter() - t0
                    # 2秒経過または4MB到達で計測終了（起動時なので高速に完了させる）
                    if elapsed >= 2.0 or total_downloaded >= max_bytes:
                        break

                elapsed = time.perf_counter() - t0
                if elapsed > 0.1 and total_downloaded > 100 * 1024:
                    bytes_per_sec = total_downloaded / elapsed
                    mbps = (bytes_per_sec * 8) / (1000 * 1000)
                    return round(mbps, 2)
            except Exception as e:
                logger.warning(f"Speed test endpoint {url} failed: {e}")

        # オフラインまたはテスト失敗時の妥当なデフォルト値 (30 Mbps)
        return 30.0
