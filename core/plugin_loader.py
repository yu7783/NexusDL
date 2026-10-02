"""
Secure Plugin Loader and Registry.
Supports both single .py scripts and .zip plugin packages (containing manifest.json and Python extractor).
Performs strict AST static analysis and ZIP slip prevention.
"""

import ast
import importlib.util
import inspect
import json
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import List, Optional, Type
from urllib.parse import urlparse

from plugins.base import BaseSiteExtractor

logger = logging.getLogger(__name__)

# プラグイン内での使用を禁止する危険モジュール
FORBIDDEN_MODULES = {
    "subprocess",
    "socket",
    "ftplib",
    "telnetlib",
    "ctypes",
    "multiprocessing",
    "pty",
    "commands",
    "posix",
    "nt",
    "pip",
    "git",
}

# プラグイン内での直接呼び出しを禁止する関数・属性
FORBIDDEN_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "spawn"),
    ("os", "exec"),
    ("os", "execl"),
    ("os", "execle"),
    ("os", "execlp"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "execvp"),
    ("builtins", "exec"),
    ("builtins", "eval"),
    ("__builtin__", "exec"),
    ("__builtin__", "eval"),
}


class PluginSecurityError(Exception):
    """プラグインの静的セキュリティ検査に失敗した場合の例外"""
    pass


class PluginASTValidator(ast.NodeVisitor):
    """
    プラグインのAST（抽象構文木）を走査し、
    危険なシステムコールや自己更新・不要機能の混入を検知する。
    """
    def __init__(self, filename: str):
        self.filename = filename
        self.errors: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module in FORBIDDEN_MODULES:
                self.errors.append(f"Forbidden module import: '{alias.name}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in FORBIDDEN_MODULES:
                self.errors.append(f"Forbidden module import: 'from {node.module}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                attr_name = node.func.attr
                if (module_name, attr_name) in FORBIDDEN_CALLS:
                    self.errors.append(f"Forbidden function call: '{module_name}.{attr_name}()' at line {node.lineno}")
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in {"eval", "exec", "compile"}:
                self.errors.append(f"Forbidden built-in function: '{func_name}()' at line {node.lineno}")
        self.generic_visit(node)


@dataclass
class LoadedPluginInfo:
    plugin_id: str
    plugin_name: str
    author: str
    version: str
    description: str
    supported_domains: List[str]
    file_path: str
    package_type: str           # "py" or "zip"
    instance: BaseSiteExtractor
    is_safe: bool = True
    error_message: Optional[str] = None


class PluginManager:
    """プラグインの発見、安全性検査、ロード、およびURLルーティングを管理するクラス"""

    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir
        self.extracted_cache_dir = os.path.join(plugins_dir, ".extracted")
        self.plugins: List[LoadedPluginInfo] = []
        self.failed_plugins: List[tuple[str, str]] = []  # (file_path, error_reason)

    def discover_and_load_all(self) -> None:
        """指定ディレクトリ内の .py および .zip プラグインを走査してロード"""
        self.plugins.clear()
        self.failed_plugins.clear()

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            return

        for filename in sorted(os.listdir(self.plugins_dir)):
            if filename.startswith(".") or filename.startswith("__") or filename == "base.py":
                continue

            file_path = os.path.join(self.plugins_dir, filename)

            # 1. 単体 .py スクリプトの読み込み
            if filename.endswith(".py"):
                try:
                    plugin_info = self._load_py_plugin(file_path)
                    if plugin_info:
                        self.plugins.append(plugin_info)
                except Exception as e:
                    logger.error(f"Failed to load python plugin {filename}: {e}")
                    self.failed_plugins.append((filename, str(e)))

            # 2. .zip プラグインパッケージの読み込み
            elif filename.endswith(".zip"):
                try:
                    plugin_info = self._load_zip_plugin(file_path)
                    if plugin_info:
                        self.plugins.append(plugin_info)
                except Exception as e:
                    logger.error(f"Failed to load zip plugin {filename}: {e}")
                    self.failed_plugins.append((filename, str(e)))

    def _load_py_plugin(self, file_path: str) -> Optional[LoadedPluginInfo]:
        """単一の.pyプラグインファイルをAST検証後に動的ロード"""
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        self._validate_ast(source_code, file_path)

        module_name = f"plugins_dynamic_py_{os.path.splitext(os.path.basename(file_path))[0]}"
        instance = self._instantiate_extractor(module_name, file_path)

        return LoadedPluginInfo(
            plugin_id=instance.plugin_id,
            plugin_name=instance.plugin_name,
            author=instance.author,
            version=instance.version,
            description=instance.description,
            supported_domains=instance.supported_domains,
            file_path=file_path,
            package_type="py",
            instance=instance,
            is_safe=True
        )

    def _load_zip_plugin(self, zip_path: str) -> Optional[LoadedPluginInfo]:
        """
        .zip プラグインパッケージを安全に検証・解凍してロード。
        中身に manifest.json と指定の Python スクリプトを含む必要があります。
        """
        zip_base = os.path.splitext(os.path.basename(zip_path))[0]
        target_extract_dir = os.path.join(self.extracted_cache_dir, zip_base)

        if os.path.exists(target_extract_dir):
            shutil.rmtree(target_extract_dir, ignore_errors=True)
        os.makedirs(target_extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Zip Slip 安全性チェック
            for member in zf.namelist():
                if os.path.isabs(member) or ".." in member:
                    raise PluginSecurityError(f"Insecure zip path detected in {member}")
            zf.extractall(target_extract_dir)

        # manifest.json の読み込み
        manifest_file = os.path.join(target_extract_dir, "manifest.json")
        if not os.path.exists(manifest_file):
            raise PluginSecurityError("manifest.json not found in plugin zip package.")

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            raise PluginSecurityError(f"Invalid manifest.json: {e}")

        entry_point = manifest.get("entry_point", "extractor.py")
        script_path = os.path.join(target_extract_dir, entry_point)

        if not os.path.exists(script_path):
            raise PluginSecurityError(f"Entry point script '{entry_point}' not found in zip.")

        # AST静的検証
        with open(script_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        self._validate_ast(source_code, script_path)

        module_name = f"plugins_dynamic_zip_{zip_base}"
        instance = self._instantiate_extractor(module_name, script_path)

        return LoadedPluginInfo(
            plugin_id=manifest.get("id", instance.plugin_id),
            plugin_name=manifest.get("name", instance.plugin_name),
            author=manifest.get("author", instance.author),
            version=manifest.get("version", instance.version),
            description=manifest.get("description", instance.description),
            supported_domains=manifest.get("supported_domains", instance.supported_domains),
            file_path=zip_path,
            package_type="zip",
            instance=instance,
            is_safe=True
        )

    def _validate_ast(self, source_code: str, file_path: str) -> None:
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as se:
            raise PluginSecurityError(f"Syntax error in plugin: {se}")

        validator = PluginASTValidator(file_path)
        validator.visit(tree)
        if validator.errors:
            raise PluginSecurityError(f"Security validation failed: {', '.join(validator.errors)}")

    def _instantiate_extractor(self, module_name: str, file_path: str) -> BaseSiteExtractor:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Cannot create module spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        extractor_cls: Optional[Type[BaseSiteExtractor]] = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                inspect.isclass(attr)
                and issubclass(attr, BaseSiteExtractor)
                and attr is not BaseSiteExtractor
            ):
                extractor_cls = attr
                break

        if not extractor_cls:
            raise TypeError(f"No valid BaseSiteExtractor subclass found in {file_path}")

        return extractor_cls()

    def match_plugin_for_url(self, url: str) -> Optional[BaseSiteExtractor]:
        """URLに対応する最適なプラグインを返します"""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        fallback_plugin: Optional[BaseSiteExtractor] = None

        for p in self.plugins:
            if "*" in p.supported_domains:
                fallback_plugin = p.instance
                continue

            matches_domain = any(
                domain.lower() in netloc or netloc.endswith(domain.lower())
                for domain in p.supported_domains
            )

            if matches_domain:
                try:
                    if p.instance.can_handle(url):
                        return p.instance
                except Exception as e:
                    logger.warning(f"Error checking can_handle on {p.plugin_name}: {e}")

        for p in self.plugins:
            if "*" in p.supported_domains:
                continue
            try:
                if p.instance.can_handle(url):
                    return p.instance
            except Exception:
                pass

        if fallback_plugin and fallback_plugin.can_handle(url):
            return fallback_plugin

        return None
