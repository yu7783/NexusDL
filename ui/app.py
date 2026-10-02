"""
Main Application Window & SpotiFLAC-inspired Slim Icon Sidebar Shell.
Features Pure White / Dark Dual-Theme Support, Theme Quick-Toggle, and Instant View Switching.
Title: Nexus DL
"""

import os
import threading
import customtkinter as ctk

from config.settings import AppSettings
from core.engine import DownloadManager
from core.plugin_loader import PluginManager
from core.speed_tester import NetworkSpeedTester
from ui import styles
from ui.views.home_view import HomeView
from ui.views.plugins_view import PluginsView
from ui.views.settings_view import SettingsView


class App(ctk.CTk):
    """メインアプリケーションウィンドウ (Nexus DL)"""

    def __init__(self, project_root: str):
        super().__init__()

        self.project_root = project_root
        self.plugins_dir = os.path.join(project_root, "plugins")
        self.config_dir = os.path.join(project_root, "config")

        # 1. バックエンド初期化
        self.settings = AppSettings(self.config_dir)
        self.plugin_manager = PluginManager(self.plugins_dir)
        self.plugin_manager.discover_and_load_all()

        self.download_manager = DownloadManager(
            chunk_size_kb=self.settings.get("chunk_size_kb", 256),
            timeout_seconds=self.settings.get("timeout_seconds", 30),
            request_retries=self.settings.get("request_retries", 3),
            proxy_url=self.settings.get("proxy_url"),
            enable_resume=self.settings.get("enable_resume", True),
            user_agent=self.settings.get("user_agent")
        )

        # 2. ウィンドウ設定
        self.title("Nexus DL")
        self.geometry("1040x660")
        self.minsize(880, 560)
        self.configure(fg_color=styles.COLOR_BG)

        # 保存されているカラーモードを適用 (Light / Dark / System)
        appearance = self.settings.get("appearance_mode", "light")
        ctk.set_appearance_mode(appearance)

        # 3. スリムアイコンサイドバー ＆ メインエリア
        self._build_shell()
        self._show_view("home")

        # 4. 起動時速度テスト（遅延キック）
        self.after(500, self._trigger_startup_speed_test)

    def _build_shell(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=68)
        self.grid_columnconfigure(1, weight=1)

        # --- 左側スリムアイコンバー ---
        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=styles.COLOR_SIDEBAR_BG,
            corner_radius=0,
            width=68
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        top_spacer = ctk.CTkFrame(self.sidebar, height=16, fg_color="transparent")
        top_spacer.pack(fill="x")

        self.nav_buttons = {}
        self._create_icon_button("home", "🏠", lambda: self._show_view("home"))
        self._create_icon_button("plugins", "🧩", lambda: self._show_view("plugins"))
        self._create_icon_button("settings", "⚙️", lambda: self._show_view("settings"))

        # 下部ボトムグループ
        bottom_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_box.pack(side="bottom", fill="x", pady=16)

        # 🌙/☀️ テーマ切り替えクイックトグル
        self.theme_btn = ctk.CTkButton(
            bottom_box,
            text="🌓",
            width=42,
            height=42,
            font=("Segoe UI", 16),
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_NAV,
            command=self._on_toggle_theme_quick
        )
        self.theme_btn.pack(anchor="center", pady=(0, 8))

        # 速度テスト状態アイコン
        self.net_icon_badge = ctk.CTkButton(
            bottom_box,
            text="⚡",
            width=42,
            height=42,
            font=("Segoe UI", 16),
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MUTED,
            corner_radius=styles.CORNER_RADIUS_NAV,
            command=lambda: self._show_view("settings")
        )
        self.net_icon_badge.pack(anchor="center")

        # --- 右側メインコンテンツ ---
        self.content_area = ctk.CTkFrame(self, fg_color=styles.COLOR_BG, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

        self.views = {
            "home": HomeView(
                self.content_area,
                plugin_manager=self.plugin_manager,
                download_manager=self.download_manager,
                get_save_dir_func=lambda: self.settings.get("download_directory"),
                set_save_dir_func=lambda p: self.settings.set("download_directory", p)
            ),
            "plugins": PluginsView(
                self.content_area,
                plugin_manager=self.plugin_manager
            ),
            "settings": SettingsView(
                self.content_area,
                settings=self.settings,
                on_settings_change=self._on_settings_updated
            )
        }

    def _create_icon_button(self, key: str, icon: str, command):
        btn = ctk.CTkButton(
            self.sidebar,
            text=icon,
            width=46,
            height=46,
            font=("Segoe UI", 18),
            fg_color="transparent",
            text_color=styles.COLOR_TEXT_MUTED,
            hover_color=styles.COLOR_SURFACE_SUBTLE,
            corner_radius=styles.CORNER_RADIUS_NAV,
            command=command
        )
        btn.pack(anchor="center", pady=6)
        self.nav_buttons[key] = btn

    def _show_view(self, name: str):
        for k, v in self.views.items():
            if k == name:
                v.pack(fill="both", expand=True)
            else:
                v.pack_forget()

        for k, btn in self.nav_buttons.items():
            if k == name:
                btn.configure(
                    fg_color=styles.COLOR_ACCENT_BG,
                    text_color=styles.COLOR_ACCENT_TEXT
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=styles.COLOR_TEXT_MUTED
                )

        if name == "plugins":
            self.views["plugins"].refresh_list()

    def _on_toggle_theme_quick(self):
        """サイドバーの🌓ボタンによるワンクリックテーマ切り替え"""
        current = ctk.get_appearance_mode().lower()
        new_mode = "dark" if current == "light" else "light"
        ctk.set_appearance_mode(new_mode)
        self.settings.set("appearance_mode", new_mode)
        if hasattr(self.views["settings"], "mode_menu"):
            self.views["settings"].mode_menu.set(new_mode.capitalize())

    def _trigger_startup_speed_test(self):
        def _test_worker():
            try:
                res = NetworkSpeedTester.run_benchmark()
                self.settings.set("last_speed_test_mbps", res.bandwidth_mbps)
                self.settings.set("last_speed_test_summary", res.summary_text)

                if self.settings.get("auto_tune_concurrency", True):
                    self.settings.set("max_concurrency", res.recommended_concurrency)
                    self.settings.set("chunk_size_kb", res.recommended_chunk_kb)
                    self._on_settings_updated()

                self.after(0, lambda: self.net_icon_badge.configure(
                    text="⚡",
                    fg_color=styles.COLOR_ACCENT_BG,
                    text_color=styles.COLOR_ACCENT_TEXT
                ))
            except Exception:
                pass

        threading.Thread(target=_test_worker, daemon=True).start()

    def _on_settings_updated(self):
        self.download_manager.update_config(
            chunk_size_kb=self.settings.get("chunk_size_kb", 256),
            timeout_seconds=self.settings.get("timeout_seconds", 30),
            request_retries=self.settings.get("request_retries", 3),
            proxy_url=self.settings.get("proxy_url"),
            enable_resume=self.settings.get("enable_resume", True)
        )
        current_dir = self.settings.get("download_directory")
        if hasattr(self.views["home"], "save_dir_info_lbl"):
            self.views["home"].save_dir_info_lbl.configure(text=f"保存先: {current_dir}")
