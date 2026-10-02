# Nexus DL アドオン開発ガイド (How to Develop Addon)

Nexus DL は、ダウンロード対応サイトの解析ロジックを自由に拡張できるアドオン（プラグイン）システムを備えています。
本ガイドでは、新しいサイトに対応するアドオンを作成・パッケージングし、配布・インストールする手順を詳しく解説します。

---

## 1. 推奨アドオン規格：ZIP パッケージ形式 (`.zip`)

Nexus DL では単体スクリプト（`.py`）も動作しますが、配布の容易さ、メタデータの一元管理、将来的なアセット同梱の観点から、**`.zip` パッケージ形式を公式に強く推奨しています。**

### パッケージ構成
アドオンの `.zip` アーカイブ内には、必ず直下に **`manifest.json`** と **Python スクリプト** を配置します。

```plaintext
my_custom_addon.zip
├── manifest.json       # アドオンの定義ファイル (必須)
└── extractor.py        # URL解析ロジックを記述したスクリプト (必須)
```

---

## 2. `manifest.json` の仕様

`manifest.json` にはアドオンの基本情報、エントリポイント、対応ドメインを記述します。

```json
{
  "id": "my_video_site",
  "name": "MyVideoSite 解析アドオン",
  "version": "1.0.0",
  "author": "YourName",
  "description": "MyVideoSite.com の動画・音声URLを解析し、高品質ストリームを提供します。",
  "entry_point": "extractor.py",
  "supported_domains": [
    "myvideosite.com",
    "sub.myvideosite.com"
  ]
}
```

| フィールド | 型 | 必須 | 説明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ○ | アドオンの一意な識別子（英数字・アンダースコア） |
| `name` | string | ○ | アプリ内に表示されるアドオン名 |
| `version` | string | ○ | バージョン文字列 (例: `"1.0.0"`) |
| `author` | string | ○ | 作者名 |
| `description` | string | ○ | アドオンの簡単な説明文 |
| `entry_point` | string | ○ | 実行起点となるPythonスクリプトファイル名 |
| `supported_domains` | list | ○ | 対応するドメインリスト。汎用フォールバックの場合は `["*"]` |

---

## 3. エクストラクタの実装 (`extractor.py`)

`plugins.base` から基底クラス `BaseSiteExtractor` およびデータモデルをインポートして実装します。

### 基本テンプレート

```python
from urllib.parse import urlparse
from typing import Dict, List, Optional
from plugins.base import BaseSiteExtractor, DownloadTarget, DownloadOption, OptionChoice


class MySiteExtractor(BaseSiteExtractor):
    """サイト固有のURL解析クラス"""

    @property
    def plugin_id(self) -> str:
        return "my_video_site"

    @property
    def plugin_name(self) -> str:
        return "MyVideoSite 解析アドオン"

    @property
    def author(self) -> str:
        return "YourName"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "MyVideoSite.com の動画URLを解析します。"

    @property
    def supported_domains(self) -> list[str]:
        return ["myvideosite.com"]

    def can_handle(self, url: str) -> bool:
        """指定されたURLが本アドオンで処理可能かを判定"""
        if not url:
            return False
        return "myvideosite.com" in url.lower()

    def get_supported_options(self, url: str) -> List[DownloadOption]:
        """
        【動的メニュー指定】
        ユーザーがダウンロード画面で選択できるメニュー項目をアドオン側で自由に定義できます。
        項目名（label）や選択肢（choices）はアドオン側が完全制御します。
        不要な場合は空リスト [] を返します。
        """
        return [
            DownloadOption(
                key="quality",
                label="画質・解像度",
                choices=[
                    OptionChoice(id="1080p", label="1080p Full HD", is_default=True),
                    OptionChoice(id="720p", label="720p HD"),
                    OptionChoice(id="audio_only", label="🎵 音声のみ"),
                ],
                description="出力映像の品質を指定します"
            ),
            DownloadOption(
                key="extension",
                label="保存形式",
                choices=[
                    OptionChoice(id="mp4", label="MP4 (.mp4)", is_default=True),
                    OptionChoice(id="m4a", label="M4A (.m4a)"),
                ]
            )
        ]

    def extract(self, url: str, selected_options: Optional[Dict[str, str]] = None) -> DownloadTarget:
        """
        URLおよびユーザー選択オプションを受け取り、直接ダウンロード可能なURLを返します。
        """
        options = selected_options or {}
        req_quality = options.get("quality", "1080p")
        req_ext = options.get("extension", "mp4")

        # --- サイト固有の解析ロジック ---
        # 例: HTMLスクレイピングやWeb API呼び出しで直リンクを取得
        direct_stream_url = f"https://cdn.myvideosite.com/video_{req_quality}.{req_ext}"
        target_filename = f"video_{req_quality}.{req_ext}"

        # 認証や偽装に必要な追加HTTPヘッダー
        custom_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://myvideosite.com/",
        }

        return DownloadTarget(
            source_url=direct_stream_url,
            filename=target_filename,
            headers=custom_headers,
            expected_size=None,  # 判明している場合はバイト数を指定 (int)
            extra_info={"quality": req_quality, "format": req_ext}
        )
```

---

## 4. 厳格なセキュリティ規約（AST 静的検査）

Nexus DL は安全性を最重要視しています。アドオンの責務は**「URLから直接ダウンロードURLとメタデータを抽出すること」**に厳格限定されています。

本体起動時およびインストール時に **AST（抽象構文木）による静的コード検査** が行われ、以下のコードパターンが含まれている場合は**即座に読み込みが拒絶され、アプリ上で「安全ポリシー違反」として遮断**されます：

### ❌ 禁止されている処理
1. **外部サブプロセス・シェル実行**:
   - `subprocess.run`, `subprocess.Popen`, `os.system`, `os.popen`, `os.exec*`
2. **自己更新・外部インストーラー呼び出し**:
   - プラグイン内で `pip install` や `git pull` 等のコマンドを実行させる行為（アドオン更新は本体インストーラー経由で行う必要があります）。
3. **低レベルソケット通信・危険モジュールのインポート**:
   - `socket`, `ctypes`, `multiprocessing`, `telnetlib`, `ftplib`
4. **危険な動的コード実行**:
   - `eval()`, `exec()` の直接呼び出し

### ⭕ 許可されている処理
- Webページ・APIへのリクエスト（`requests.get`, `requests.post`, `urllib.request` など）
- HTML/JSON のパース（`re`, `json`, `bs4`, `html.parser` など）
- メディア解析ライブラリ（`yt-dlp` など）の安全な利用

---

## 5. アドオンのパッケージングとインストール手順

### 手順 1: ZIP ファイルの作成
作成した `manifest.json` と `extractor.py` を選択し、ZIP形式で圧縮します：
```bash
# PowerShell での圧縮例
Compress-Archive -Path manifest.json, extractor.py -DestinationPath my_video_site.zip
```

### 手順 2: Nexus DL へのインストール
Nexus DL のサイドバーから **「アドオン管理 (🧩)」** 画面を開きます：

1. **ローカルファイルから導入**:
   - 「② ローカルファイル:」の **「ファイルを選択...」** をクリックし、作成した `.zip` を選択します。
   - 安全検査を通過すると、即座にインストールされ「✓ 安全検査 合格」バッジ付きで有効化されます。
2. **GitHubリポジトリから導入**:
   - GitHubリポジトリに push した場合、リポジトリURL（例: `https://github.com/yourname/my-addon`）を貼り付けて **「インストール」** を押すだけで、本体が自動取得・検証して配置します。

---

## 6. 動作確認

インストール後、**「ホーム (🏠)」** 画面に移動し、対応ドメインのURLを入力してください：
1. 右上のバッジが **「⚡ あなたのアドオン名」** に切り替わります。
2. `get_supported_options` で定義したメニュー（画質、保存形式など）が Fetch バーの下部に自動展開されます。
3. **「⚡ Fetch」** を押すと、マルチスレッドで高速ダウンロードが開始されます。
