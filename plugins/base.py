"""
Base interfaces and data models for plugins.
Strictly limited to URL extraction and metadata parsing.
Supports dynamic add-on configurable options (Quality, Resolution, Audio, Extension, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class OptionChoice:
    """アドオンが提供する単一の選択肢"""
    id: str                   # 内部識別値 (例: "1080p", "mp4", "best")
    label: str                # UI表示用ラベル (例: "1080p Full HD", "MP4 (.mp4)")
    is_default: bool = False  # デフォルト選択フラグ


@dataclass(frozen=True)
class DownloadOption:
    """
    アドオン側が制御・定義するダウンロード設定項目。
    名前（label）や選択肢（choices）はアドオン側が完全に決定します。
    """
    key: str                          # パラメータキー (例: "quality", "format", "audio_rate")
    label: str                        # 画面に表示する名前 (例: "画質設定", "保存形式", "音質")
    choices: List[OptionChoice]       # 選択肢のリスト
    description: str = ""             # 補助説明文


@dataclass(frozen=True)
class DownloadTarget:
    """
    プラグインが解析完了時にコアエンジンへ渡す唯一のデータ構造。
    """
    source_url: str                                  # 実際のコンテンツ直接URL
    filename: str                                    # 提案ファイル名（拡張子含む）
    headers: Optional[Dict[str, str]] = None        # 追加HTTPヘッダー
    expected_size: Optional[int] = None             # 予想サイズ(bytes)
    extra_info: Dict[str, str] = field(default_factory=dict)


class BaseSiteExtractor(ABC):
    """
    ダウンロード対応サイト解析プラグインの抽象基底クラス。
    """

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """プラグインの一意な識別ID"""
        pass

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """表示用プラグイン名"""
        pass

    @property
    @abstractmethod
    def author(self) -> str:
        """作者名"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """バージョン文字列"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """プラグインの簡単な説明"""
        pass

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """対応するドメインのリスト"""
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """指定されたURLが本プラグインで解析可能かを判定"""
        pass

    def get_supported_options(self, url: str) -> List[DownloadOption]:
        """
        URLに応じてユーザーが指定できるメニュー項目（画質、音質、拡張子など）を返します。
        項目名（label）や選択肢（choices）はアドオン側で完全に制御できます。
        オプションが不要な場合は空リストを返します。
        """
        return []

    @abstractmethod
    def extract(self, url: str, selected_options: Optional[Dict[str, str]] = None) -> DownloadTarget:
        """
        URLおよびユーザーがメニューで選択したオプション値を受け取り、
        直接ダウンロード可能なURLおよびメタデータを解析・抽出して返します。
        """
        pass
