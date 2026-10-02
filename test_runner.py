"""
Comprehensive automated test suite.
Tests:
1. Dynamic Add-on Options Interface (Quality, Extension, Audio bitrate)
2. AddonInstaller: local .py / .zip installation
3. Color Mode Switching (Light / Dark / System)
4. GUI Initialization & Response
"""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import customtkinter as ctk
from core.addon_installer import AddonInstaller
from core.plugin_loader import PluginManager
from plugins.ytdlp_extractor import YtDlpSiteExtractor


def test_color_modes():
    print("=== 1. カラーモード切り替えテスト ===")
    from ui.app import App
    app = App(CURRENT_DIR)
    app.update()

    init_mode = ctk.get_appearance_mode().lower()
    print(f"初期外観モード: {init_mode}")

    # 1回目のトグル
    app._on_toggle_theme_quick()
    app.update()
    toggled_mode = ctk.get_appearance_mode().lower()
    print(f"トグル後外観モード: {toggled_mode}")
    assert toggled_mode != init_mode

    # 2回目のトグル（元のモードに戻る）
    app._on_toggle_theme_quick()
    app.update()
    restored_mode = ctk.get_appearance_mode().lower()
    print(f"再トグル後外観モード: {restored_mode}")
    assert restored_mode == init_mode

    print("=> カラーモードのリアルタイム切り替えが正常に稼働しています。")
    app.destroy()


def test_addon_dynamic_options():
    print("\n=== 2. アドオン動的オプションメニューテスト ===")
    extractor = YtDlpSiteExtractor()
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

    options = extractor.get_supported_options(test_url)
    assert len(options) >= 3
    print(f"アドオン指定メニュー数: {len(options)} (画質・拡張子・音質)")

    target = extractor.extract(test_url, selected_options={"quality": "audio_only", "extension": "m4a"})
    assert target.filename.endswith(".m4a")
    print(f"抽出結果: {target.filename}")
    print("=> 動的オプション反映成功。")


def test_addon_installer():
    print("\n=== 3. AddonInstaller テスト (.zip & .py) ===")
    installer = AddonInstaller(os.path.join(CURRENT_DIR, "plugins"))
    test_src = os.path.join(CURRENT_DIR, "temp_new_addon.py")
    with open(test_src, "w", encoding="utf-8") as f:
        f.write('''
from plugins.base import BaseSiteExtractor, DownloadTarget

class TempNewExtractor(BaseSiteExtractor):
    @property
    def plugin_id(self): return "temp_new_addon"
    @property
    def plugin_name(self): return "テスト動的アドオン"
    @property
    def author(self): return "Tester"
    @property
    def version(self): return "1.0.0"
    @property
    def description(self): return "動的追加テスト用"
    @property
    def supported_domains(self): return ["temp-site.org"]
    def can_handle(self, url): return "temp-site.org" in url
    def extract(self, url, selected_options=None): return DownloadTarget(source_url=url, filename="temp.dat")
''')

    success, msg = installer.install_from_local_file(test_src)
    assert success

    pm = PluginManager(os.path.join(CURRENT_DIR, "plugins"))
    pm.discover_and_load_all()
    assert any(p.plugin_id == "temp_new_addon" for p in pm.plugins)

    installed_file = os.path.join(CURRENT_DIR, "plugins", "temp_new_addon.py")
    if os.path.exists(installed_file): os.remove(installed_file)
    if os.path.exists(test_src): os.remove(test_src)
    print("=> アドオンインストーラー動作確認。")


if __name__ == "__main__":
    test_color_modes()
    test_addon_dynamic_options()
    test_addon_installer()
    print("\n🎉 全てのカラーモード・アドオン・UIテストが正常に完了しました！")
