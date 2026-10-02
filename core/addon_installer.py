"""
Add-on Installer Engine.
Supports two installation methods exclusively:
1. GitHub Repository URL (downloads archive, validates, and installs)
2. Local .py or .zip file selection (validates and installs)
Maintains strict extraction-only safety rules through AST static validation.
"""

import ast
import io
import json
import logging
import os
import re
import shutil
import urllib.parse
import zipfile
from typing import Optional, Tuple

import requests
from core.plugin_loader import PluginASTValidator, PluginSecurityError

logger = logging.getLogger(__name__)


class AddonInstaller:
    """アドオンの安全なダウンロード・検証・配置を統括するインストーラー"""

    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir

    def install_from_local_file(self, source_path: str) -> Tuple[bool, str]:
        """
        ローカルの .py または .zip ファイルからアドオンを検証してインストール
        """
        if not os.path.exists(source_path):
            return False, "指定されたファイルが存在しません。"

        ext = os.path.splitext(source_path)[1].lower()
        if ext not in (".py", ".zip"):
            return False, "対応しているファイル形式は .py または .zip のみです。"

        base_name = os.path.basename(source_path)
        dest_path = os.path.join(self.plugins_dir, base_name)

        try:
            # 1. 安全性検証
            if ext == ".py":
                with open(source_path, "r", encoding="utf-8") as f:
                    code = f.read()
                self._validate_code(code, base_name)
            elif ext == ".zip":
                self._validate_zip(source_path)

            # 2. プラグインフォルダへコピー
            os.makedirs(self.plugins_dir, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            return True, f"アドオン '{base_name}' のインストールに成功しました。"

        except Exception as e:
            logger.error(f"Installation failed for {source_path}: {e}")
            return False, f"インストールの失敗 (安全検査違反または不正形式): {e}"

    def install_from_github(self, github_url: str) -> Tuple[bool, str]:
        """
        GitHubリポジトリURLからアーカイブを取得し、検証してインストール
        例: https://github.com/user/my-addon
        """
        parsed = urllib.parse.urlparse(github_url.strip())
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]

        if "github.com" not in parsed.netloc.lower() or len(path_parts) < 2:
            return False, "有効なGitHubリポジトリURLを入力してください (例: https://github.com/owner/repo)"

        owner, repo = path_parts[0], path_parts[1].replace(".git", "")
        archive_urls = [
            f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
            f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
        ]

        zip_data = None
        last_error = "GitHubからのダウンロードに失敗しました。"

        for url in archive_urls:
            try:
                resp = requests.get(url, timeout=20, headers={"User-Agent": "NexusDownloader/Installer"})
                if resp.status_code == 200 and len(resp.content) > 100:
                    zip_data = resp.content
                    break
            except Exception as e:
                last_error = str(e)

        if not zip_data:
            return False, f"リポジトリのアーカイブ取得に失敗しました: {last_error}"

        # メモリ上でZIP構造を検査・再構築
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                # GitHubのzipは先頭に "repo-branch/" のディレクトリが入る
                namelist = zf.namelist()
                root_prefix = namelist[0].split("/")[0] + "/" if namelist else ""

                # manifest.json または extractor.py または plugin_id.py を特定
                manifest_content = None
                py_scripts = {}

                for member in namelist:
                    rel_name = member[len(root_prefix):] if member.startswith(root_prefix) else member
                    if not rel_name or member.endswith("/"):
                        continue

                    # Zip Slip チェック
                    if os.path.isabs(rel_name) or ".." in rel_name:
                        return False, "不正なアーカイブ構造が検出されました (Zip Slip)。"

                    if rel_name == "manifest.json":
                        manifest_content = zf.read(member).decode("utf-8")
                    elif rel_name.endswith(".py"):
                        py_scripts[rel_name] = zf.read(member).decode("utf-8")

                if not py_scripts:
                    return False, "リポジトリ内にPythonスクリプト (.py) が見つかりませんでした。"

                # AST静的検査
                for script_name, code in py_scripts.items():
                    self._validate_code(code, script_name)

                # パッケージ化して plugins/<repo>.zip として保存
                os.makedirs(self.plugins_dir, exist_ok=True)
                dest_zip_path = os.path.join(self.plugins_dir, f"{repo}.zip")

                with zipfile.ZipFile(dest_zip_path, "w", zipfile.ZIP_DEFLATED) as out_zf:
                    if manifest_content:
                        out_zf.writestr("manifest.json", manifest_content)
                    else:
                        # manifest がない場合は自動生成
                        first_py = list(py_scripts.keys())[0]
                        auto_manifest = {
                            "id": repo.lower().replace("-", "_"),
                            "name": repo,
                            "version": "1.0.0",
                            "author": owner,
                            "description": f"Installed from GitHub: {owner}/{repo}",
                            "entry_point": first_py,
                            "supported_domains": ["*"]
                        }
                        out_zf.writestr("manifest.json", json.dumps(auto_manifest, indent=2, ensure_ascii=False))

                    for rel_name, code in py_scripts.items():
                        out_zf.writestr(rel_name, code)

            return True, f"GitHubリポジトリ '{owner}/{repo}' からアドオンをインストールしました。"

        except Exception as e:
            logger.error(f"GitHub addon processing error: {e}")
            return False, f"検証エラー: {e}"

    def _validate_code(self, source_code: str, filename: str):
        try:
            tree = ast.parse(source_code, filename=filename)
        except SyntaxError as se:
            raise PluginSecurityError(f"構文エラー: {se}")

        validator = PluginASTValidator(filename)
        validator.visit(tree)
        if validator.errors:
            raise PluginSecurityError(f"セキュリティ規約違反: {', '.join(validator.errors)}")

    def _validate_zip(self, zip_path: str):
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if os.path.isabs(member) or ".." in member:
                    raise PluginSecurityError(f"不正なZIPパスが検出されました: {member}")
                if member.endswith(".py"):
                    code = zf.read(member).decode("utf-8")
                    self._validate_code(code, member)
