"""
yt-dlp Dedicated Extractor Add-on.
Strictly limited to metadata and stream URL resolution.
Provides dynamic option menus (Quality, Format/Extension, Audio Bitrate) controllable by the add-on.
"""

from typing import Dict, List, Optional
from urllib.parse import urlparse
import yt_dlp

from plugins.base import BaseSiteExtractor, DownloadOption, DownloadTarget, OptionChoice


class YtDlpSiteExtractor(BaseSiteExtractor):
    """
    yt-dlp を用いた動画・音声共有プラットフォーム対応アドオン。
    対応サイト: YouTube, ニコニコ動画, X (Twitter), TikTok, Bilibili, Vimeo, Twitch, SoundCloud など
    """

    SUPPORTED_DOMAINS_LIST = [
        "youtube.com",
        "youtu.be",
        "nicovideo.jp",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "bilibili.com",
        "vimeo.com",
        "twitch.tv",
        "soundcloud.com",
        "facebook.com",
        "instagram.com",
        "dailymotion.com",
        "reddit.com",
    ]

    @property
    def plugin_id(self) -> str:
        return "ytdlp_universal_media"

    @property
    def plugin_name(self) -> str:
        return "yt-dlp メディア解析エンジン"

    @property
    def author(self) -> str:
        return "Community / yt-dlp"

    @property
    def version(self) -> str:
        return "2.3.0"

    @property
    def description(self) -> str:
        return (
            "YouTube, ニコニコ動画, X(Twitter), TikTok, Bilibili, Vimeo, Twitch, "
            "SoundCloud等の動画/音声ストリームURLおよびタイトルを高速解析します。"
        )

    @property
    def supported_domains(self) -> List[str]:
        return self.SUPPORTED_DOMAINS_LIST

    def can_handle(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        return any(domain in netloc for domain in self.SUPPORTED_DOMAINS_LIST)

    def get_supported_options(self, url: str) -> List[DownloadOption]:
        """
        アドオン側で制御するダウンロード設定メニュー項目。
        画面上にはここで指定したラベルと選択肢がそのまま動的生成されます。
        """
        # 1. 画質・解像度メニュー
        quality_option = DownloadOption(
            key="quality",
            label="画質・解像度",
            choices=[
                OptionChoice(id="best", label="最高画質 (自動)", is_default=True),
                OptionChoice(id="1080p", label="1080p (Full HD)"),
                OptionChoice(id="720p", label="720p (HD)"),
                OptionChoice(id="480p", label="480p (SD)"),
                OptionChoice(id="360p", label="360p (標準)"),
                OptionChoice(id="audio_only", label="🎵 音声のみ (Audio Only)"),
            ],
            description="ダウンロードする映像の品質を指定します"
        )

        # 2. 保存形式・拡張子メニュー
        format_option = DownloadOption(
            key="extension",
            label="保存形式・拡張子",
            choices=[
                OptionChoice(id="mp4", label="MP4 (.mp4)", is_default=True),
                OptionChoice(id="m4a", label="M4A (.m4a)"),
                OptionChoice(id="webm", label="WebM (.webm)"),
                OptionChoice(id="mp3", label="MP3 (.mp3)"),
            ],
            description="出力ファイルの拡張子・コンテナ形式"
        )

        # 3. 音質メニュー
        audio_option = DownloadOption(
            key="audio_quality",
            label="音質設定",
            choices=[
                OptionChoice(id="best", label="最高音質 (Best)", is_default=True),
                OptionChoice(id="medium", label="標準 (128 kbps)"),
                OptionChoice(id="low", label="省容量 (64 kbps)"),
            ],
            description="音声ビットレートの優先度"
        )

        return [quality_option, format_option, audio_option]

    def extract(self, url: str, selected_options: Optional[Dict[str, str]] = None) -> DownloadTarget:
        """
        指定されたオプション（画質・拡張子・音質）を反映してストリームを抽出
        """
        options = selected_options or {}
        req_quality = options.get("quality", "best")
        req_ext = options.get("extension", "mp4")

        is_audio_only = req_quality == "audio_only" or req_ext in ("m4a", "mp3")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"]
                }
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                try:
                    fallback_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
                    with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                        info = fallback_ydl.extract_info(url, download=False)
                except Exception:
                    raise ValueError(f"動画情報の取得に失敗しました: {e}")

            if not info:
                raise ValueError("メディア情報の解析に失敗しました。")

            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            formats = info.get("formats", [])
            chosen_format = None

            if is_audio_only:
                # 音声のみが要求された場合: audio-only ストリームから最良のものを選択
                audio_candidates = [
                    f for f in formats
                    if f.get("url")
                    and f.get("acodec") != "none"
                    and str(f.get("protocol", "")).startswith("http")
                ]
                if audio_candidates:
                    # 音声ビットレートが高いものを選択
                    audio_candidates.sort(key=lambda x: (x.get("abr") or 0))
                    chosen_format = audio_candidates[-1]
            else:
                # 映像ストリーム
                prog_candidates = [
                    f for f in formats
                    if f.get("url")
                    and f.get("vcodec") != "none"
                    and f.get("acodec") != "none"
                    and str(f.get("protocol", "")).startswith("http")
                ]

                # 指定解像度（1080p, 720p, 480p, 360p）の照合
                if req_quality != "best" and prog_candidates:
                    height_target = int(req_quality.replace("p", "")) if "p" in req_quality else None
                    if height_target:
                        matching = [f for f in prog_candidates if f.get("height") == height_target]
                        if matching:
                            chosen_format = matching[-1]

                # 指定が合致しない、またはbestの場合は最高画質プログレッシブ
                if not chosen_format and prog_candidates:
                    chosen_format = prog_candidates[-1]

                # プログレッシブがない場合のダイレクトフォールバック
                if not chosen_format:
                    directs = [
                        f for f in formats
                        if f.get("url") and str(f.get("protocol", "")).startswith("http")
                    ]
                    if directs:
                        chosen_format = directs[-1]

            stream_url = None
            ext = req_ext if is_audio_only else (chosen_format.get("ext") if chosen_format else req_ext)
            if is_audio_only and req_ext == "mp4":
                ext = "m4a"

            filesize = None
            http_headers = dict(info.get("http_headers", {}))

            if chosen_format:
                stream_url = chosen_format.get("url")
                filesize = chosen_format.get("filesize") or chosen_format.get("filesize_approx")
                if chosen_format.get("http_headers"):
                    http_headers.update(chosen_format["http_headers"])
            elif info.get("url"):
                stream_url = info.get("url")
                filesize = info.get("filesize") or info.get("filesize_approx")

            if not stream_url:
                raise ValueError("条件に合致するストリームURLが見つかりませんでした。")

            title = info.get("title", "downloaded_media")
            filename = f"{title}.{ext}"

            return DownloadTarget(
                source_url=stream_url,
                filename=filename,
                headers=http_headers,
                expected_size=filesize,
                extra_info={
                    "uploader": info.get("uploader", "Unknown"),
                    "duration": str(info.get("duration", 0)),
                    "resolution": chosen_format.get("resolution", "unknown") if chosen_format else "unknown",
                    "quality_mode": req_quality,
                    "format_mode": ext
                }
            )
