"""
Home View: Ultra-optimized, Production-ready SpotiFLAC-inspired Experience.
Supports Light and Dark mode transitions seamlessly.
"""

import os
import subprocess
import time
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from core.engine import DownloadManager, TaskStatus, TelemetryData, format_bytes
from core.plugin_loader import PluginManager
from plugins.base import BaseSiteExtractor, DownloadOption
from ui import styles


class HomeView(ctk.CTkFrame):
    """メインダウンロード画面 (Nexus DL)"""

    def __init__(
        self,
        master,
        plugin_manager: PluginManager,
        download_manager: DownloadManager,
        get_save_dir_func: Callable[[], str],
        set_save_dir_func: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.plugin_manager = plugin_manager
        self.download_manager = download_manager
        self.get_save_dir = get_save_dir_func
        self.set_save_dir = set_save_dir_func

        self.current_task_id: Optional[str] = None
        self._last_telemetry: Optional[TelemetryData] = None

        self._matched_plugin: Optional[BaseSiteExtractor] = None
        self._active_options_map: Dict[str, str] = {}
        self._option_menu_widgets: Dict[str, ctk.CTkOptionMenu] = {}
        self._option_choice_labels_to_ids: Dict[str, Dict[str, str]] = {}

        self.completed_history: List[Dict[str, str]] = []

        # 差分キャッシュ
        self._cache_status = None
        self._cache_progress = -1.0
        self._cache_speed = ""
        self._cache_eta = ""
        self._cache_size = ""
        self._cache_filename = ""
        self._debounce_after_id = None

        self._build_ui()
        self._setup_debounced_url_listener()

    def _build_ui(self):
        self.scroll_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=("#E2E8F0", "#333338"),
            scrollbar_button_hover_color=("#CBD5E1", "#44444C")
        )
        self.scroll_container.pack(fill="both", expand=True, padx=48, pady=28)

        # 1. ヒーローヘッダー
        hero_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        hero_frame.pack(fill="x", pady=(10, 16))

        title_row = ctk.CTkFrame(hero_frame, fg_color="transparent")
        title_row.pack(anchor="center")

        ctk.CTkLabel(
            title_row,
            text="⚡",
            font=("Segoe UI", 26, "bold"),
            text_color=styles.COLOR_ACCENT
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            title_row,
            text="Nexus DL",
            font=styles.FONT_HERO_TITLE,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            title_row,
            text="v2.3.0",
            font=styles.FONT_BADGE,
            text_color=styles.COLOR_BADGE_GOLD_TEXT,
            fg_color=styles.COLOR_BADGE_GOLD_BG,
            corner_radius=styles.CORNER_RADIUS_PILL,
            padx=10,
            pady=2
        ).pack(side="left")

        ctk.CTkLabel(
            hero_frame,
            text="対応サイトのURLを入力して高速ダウンロードを実行します",
            font=styles.FONT_BODY,
            text_color=styles.COLOR_TEXT_MUTED
        ).pack(anchor="center", pady=(4, 0))

        # 2. 一体型 URL Fetch バー
        self._build_fetch_bar()

        # 3. アドオン動的オプションカード
        self._build_dynamic_options_card()

        # 4. リアルタイム・テレメトリカード
        self._build_telemetry_card()

        # 5. ダウンロード完了履歴セクション
        self.history_section = ctk.CTkFrame(self.scroll_container, fg_color="transparent")

    def _build_fetch_bar(self):
        bar_card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        bar_card.pack(fill="x", pady=(12, 6))

        inner = ctk.CTkFrame(bar_card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)

        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(
            inner,
            textvariable=self.url_var,
            placeholder_text="https:// から始まるURLを入力または貼り付け...",
            font=styles.FONT_BODY,
            height=44,
            corner_radius=styles.CORNER_RADIUS_INPUT,
            border_width=0,
            fg_color="transparent",
            text_color=styles.COLOR_TEXT_MAIN
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))

        paste_btn = ctk.CTkButton(
            inner,
            text="📋 貼付け",
            width=80,
            height=38,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_paste_url
        )
        paste_btn.pack(side="left", padx=(0, 8))

        self.start_btn = ctk.CTkButton(
            inner,
            text="⚡ Fetch",
            width=100,
            height=38,
            font=styles.FONT_BODY_BOLD,
            fg_color=styles.COLOR_FETCH_BTN,
            hover_color=styles.COLOR_FETCH_BTN_HOVER,
            text_color=styles.COLOR_FETCH_BTN_TEXT,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_start_click
        )
        self.start_btn.pack(side="left")

        sub_row = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        sub_row.pack(fill="x", pady=(2, 10))

        self.plugin_badge = ctk.CTkLabel(
            sub_row,
            text="URL待機中",
            font=styles.FONT_BADGE,
            text_color=styles.COLOR_TEXT_SUBTLE,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            corner_radius=styles.CORNER_RADIUS_PILL,
            padx=10,
            pady=2
        )
        self.plugin_badge.pack(side="right")

    def _build_dynamic_options_card(self):
        self.options_card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )

        self.options_inner = ctk.CTkFrame(self.options_card, fg_color="transparent")
        self.options_inner.pack(fill="x", padx=18, pady=16)

        opt_header = ctk.CTkFrame(self.options_inner, fg_color="transparent")
        opt_header.pack(fill="x", pady=(0, 10))

        self.opt_title_lbl = ctk.CTkLabel(
            opt_header,
            text="⚙️ フォーマット・品質指定 (アドオン提供)",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN
        )
        self.opt_title_lbl.pack(side="left")

        self.options_grid = ctk.CTkFrame(self.options_inner, fg_color="transparent")
        self.options_grid.pack(fill="x")

    def _render_addon_options(self, plugin: BaseSiteExtractor, url: str):
        for child in self.options_grid.winfo_children():
            child.destroy()
        self._active_options_map.clear()
        self._option_menu_widgets.clear()
        self._option_choice_labels_to_ids.clear()

        options_list: List[DownloadOption] = plugin.get_supported_options(url)
        if not options_list:
            self.options_card.pack_forget()
            return

        self.opt_title_lbl.configure(text=f"⚙️ {plugin.plugin_name} のダウンロード設定")

        for opt in options_list:
            row = ctk.CTkFrame(self.options_grid, fg_color=styles.COLOR_SURFACE_SUBTLE, corner_radius=styles.CORNER_RADIUS_BUTTON)
            row.pack(fill="x", pady=(0, 6))

            inner_row = ctk.CTkFrame(row, fg_color="transparent")
            inner_row.pack(fill="x", padx=14, pady=8)

            ctk.CTkLabel(
                inner_row,
                text=opt.label,
                font=styles.FONT_BODY_BOLD,
                text_color=styles.COLOR_TEXT_MAIN,
                width=160,
                anchor="w"
            ).pack(side="left")

            label_to_id = {}
            labels_list = []
            default_label = None

            for choice in opt.choices:
                label_to_id[choice.label] = choice.id
                labels_list.append(choice.label)
                if choice.is_default or default_label is None:
                    default_label = choice.label

            self._option_choice_labels_to_ids[opt.key] = label_to_id
            self._active_options_map[opt.key] = label_to_id[default_label]

            menu = ctk.CTkOptionMenu(
                inner_row,
                values=labels_list,
                width=220,
                height=32,
                font=styles.FONT_BODY,
                fg_color=styles.COLOR_SURFACE_CARD,
                button_color=styles.COLOR_SURFACE_BORDER,
                button_hover_color=styles.COLOR_ACCENT,
                text_color=styles.COLOR_TEXT_MAIN,
                corner_radius=styles.CORNER_RADIUS_BUTTON,
                command=lambda chosen_lbl, k=opt.key: self._on_addon_option_changed(k, chosen_lbl)
            )
            menu.set(default_label)
            menu.pack(side="left", padx=(0, 10))
            self._option_menu_widgets[opt.key] = menu

            if opt.description:
                ctk.CTkLabel(
                    inner_row,
                    text=opt.description,
                    font=styles.FONT_STATS_LABEL,
                    text_color=styles.COLOR_TEXT_SUBTLE,
                    anchor="w"
                ).pack(side="left", fill="x", expand=True)

        self.options_card.pack(fill="x", pady=(0, 14), before=self.telemetry_card)

    def _on_addon_option_changed(self, key: str, chosen_label: str):
        label_to_id = self._option_choice_labels_to_ids.get(key, {})
        choice_id = label_to_id.get(chosen_label, chosen_label)
        self._active_options_map[key] = choice_id

    def _build_telemetry_card(self):
        self.telemetry_card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        self.telemetry_card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(self.telemetry_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 10))

        self.task_filename_lbl = ctk.CTkLabel(
            title_row,
            text="待機中 — URLを入力して Fetch を押してください",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN,
            anchor="w"
        )
        self.task_filename_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.status_badge = ctk.CTkLabel(
            title_row,
            text=TaskStatus.IDLE.value,
            font=styles.FONT_BADGE,
            text_color=styles.COLOR_TEXT_SUBTLE,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            corner_radius=styles.CORNER_RADIUS_PILL,
            padx=10,
            pady=3
        )
        self.status_badge.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            inner,
            height=6,
            corner_radius=3,
            progress_color=styles.COLOR_ACCENT,
            fg_color=styles.COLOR_SURFACE_SUBTLE
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 10))

        col1 = ctk.CTkFrame(grid, fg_color="transparent")
        col1.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(col1, text="転送速度", font=styles.FONT_STATS_LABEL, text_color=styles.COLOR_TEXT_SUBTLE).pack(anchor="w")
        self.val_speed = ctk.CTkLabel(col1, text="0 KB/s", font=styles.FONT_STATS_VALUE, text_color=styles.COLOR_TEXT_MAIN)
        self.val_speed.pack(anchor="w")

        col2 = ctk.CTkFrame(grid, fg_color="transparent")
        col2.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(col2, text="残り時間", font=styles.FONT_STATS_LABEL, text_color=styles.COLOR_TEXT_SUBTLE).pack(anchor="w")
        self.val_eta = ctk.CTkLabel(col2, text="--:--", font=styles.FONT_STATS_VALUE, text_color=styles.COLOR_TEXT_MAIN)
        self.val_eta.pack(anchor="w")

        col3 = ctk.CTkFrame(grid, fg_color="transparent")
        col3.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(col3, text="ダウンロード量", font=styles.FONT_STATS_LABEL, text_color=styles.COLOR_TEXT_SUBTLE).pack(anchor="w")
        self.val_size = ctk.CTkLabel(col3, text="0 B / 不明", font=styles.FONT_STATS_VALUE, text_color=styles.COLOR_TEXT_MAIN)
        self.val_size.pack(anchor="w")

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.save_dir_info_lbl = ctk.CTkLabel(
            btn_row,
            text=f"保存先: {self.get_save_dir()}",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_TEXT_SUBTLE,
            anchor="w"
        )
        self.save_dir_info_lbl.pack(side="left", fill="x", expand=True)

        self.cancel_btn = ctk.CTkButton(
            btn_row,
            text="キャンセル",
            width=84,
            height=30,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_DANGER_BG,
            hover_color=styles.COLOR_DANGER_HOVER,
            text_color=styles.COLOR_DANGER_TEXT,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            state="disabled",
            command=self._on_cancel_click
        )
        self.cancel_btn.pack(side="right")

    def _setup_debounced_url_listener(self):
        self.url_var.trace_add("write", self._on_url_input_debounced)

    def _on_url_input_debounced(self, *args):
        if self._debounce_after_id:
            self.after_cancel(self._debounce_after_id)
        self._debounce_after_id = self.after(200, self._do_url_detection)

    def _do_url_detection(self):
        url = self.url_var.get().strip()
        if not url:
            self.plugin_badge.configure(
                text="URL待機中",
                text_color=styles.COLOR_TEXT_SUBTLE,
                fg_color=styles.COLOR_SURFACE_SUBTLE
            )
            self._matched_plugin = None
            self.options_card.pack_forget()
            return

        plugin = self.plugin_manager.match_plugin_for_url(url)
        self._matched_plugin = plugin

        if plugin:
            self.plugin_badge.configure(
                text=f"⚡ {plugin.plugin_name}",
                text_color=styles.COLOR_ACCENT_TEXT,
                fg_color=styles.COLOR_ACCENT_BG
            )
            self._render_addon_options(plugin, url)
        else:
            self.plugin_badge.configure(
                text="⚠️ 未対応URL",
                text_color=styles.COLOR_WARNING_TEXT,
                fg_color=styles.COLOR_WARNING_BG
            )
            self.options_card.pack_forget()

    def _on_paste_url(self):
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.url_var.set(clipboard_text.strip())
        except Exception:
            pass

    def _on_start_click(self):
        url = self.url_var.get().strip()
        if not url:
            return

        plugin = self.plugin_manager.match_plugin_for_url(url)
        if not plugin:
            self.status_badge.configure(
                text="未対応URL",
                fg_color=styles.COLOR_DANGER_BG,
                text_color=styles.COLOR_DANGER_TEXT
            )
            self.task_filename_lbl.configure(text="このURLに対応するアドオンが見つかりませんでした。")
            return

        self.start_btn.configure(state="disabled", text="Fetching...")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self.progress_bar.configure(progress_color=styles.COLOR_ACCENT)

        self._cache_status = None
        self._cache_progress = -1.0
        self._cache_speed = ""
        self._cache_eta = ""
        self._cache_size = ""
        self._cache_filename = ""

        task_id = f"task_{int(time.time() * 1000)}"
        self.current_task_id = task_id

        chosen_options = dict(self._active_options_map)

        self.download_manager.start_download(
            task_id=task_id,
            url=url,
            save_dir=self.get_save_dir(),
            extractor=plugin,
            selected_options=chosen_options,
            telemetry_callback=self._receive_telemetry_from_worker
        )

    def _on_cancel_click(self):
        if self.current_task_id:
            self.download_manager.cancel_task(self.current_task_id)
            self.cancel_btn.configure(state="disabled")

    def _receive_telemetry_from_worker(self, telemetry: TelemetryData):
        self._last_telemetry = telemetry
        self.after(0, self._apply_telemetry_to_ui)

    def _apply_telemetry_to_ui(self):
        t = self._last_telemetry
        if not t or t.task_id != self.current_task_id:
            return

        if self._cache_filename != t.filename:
            self.task_filename_lbl.configure(text=t.filename)
            self._cache_filename = t.filename

        if self._cache_status != t.status:
            self._cache_status = t.status
            self.status_badge.configure(text=t.status.value)

            if t.status == TaskStatus.DOWNLOADING:
                self.status_badge.configure(fg_color=styles.COLOR_ACCENT_BG, text_color=styles.COLOR_ACCENT_TEXT)
            elif t.status == TaskStatus.COMPLETED:
                self.status_badge.configure(fg_color=styles.COLOR_SUCCESS_BG, text_color=styles.COLOR_SUCCESS_TEXT)
                self.progress_bar.set(1.0)
                self.progress_bar.configure(progress_color=styles.COLOR_SUCCESS)
                self.start_btn.configure(state="normal", text="⚡ Fetch")
                self.cancel_btn.configure(state="disabled")
                self._record_completed(t.filename)
            elif t.status == TaskStatus.FAILED:
                self.status_badge.configure(fg_color=styles.COLOR_DANGER_BG, text_color=styles.COLOR_DANGER_TEXT)
                self.progress_bar.configure(progress_color=styles.COLOR_DANGER)
                self.start_btn.configure(state="normal", text="⚡ Fetch")
                self.cancel_btn.configure(state="disabled")
                if t.error_message:
                    self.task_filename_lbl.configure(text=f"エラー: {t.error_message}")
            elif t.status == TaskStatus.CANCELLED:
                self.status_badge.configure(fg_color=styles.COLOR_SURFACE_SUBTLE, text_color=styles.COLOR_TEXT_SUBTLE)
                self.start_btn.configure(state="normal", text="⚡ Fetch")
                self.cancel_btn.configure(state="disabled")

        if t.status == TaskStatus.DOWNLOADING:
            if abs(self._cache_progress - t.progress) > 0.005:
                self.progress_bar.set(t.progress)
                self._cache_progress = t.progress

            if self._cache_speed != t.speed_str:
                self.val_speed.configure(text=t.speed_str)
                self._cache_speed = t.speed_str

            if self._cache_eta != t.eta_str:
                self.val_eta.configure(text=t.eta_str)
                self._cache_eta = t.eta_str

            curr_str = format_bytes(t.downloaded_bytes)
            total_str = format_bytes(t.total_bytes)
            percent_str = f" ({t.progress * 100:.1f}%)" if t.progress >= 0 else ""
            size_display = f"{curr_str} / {total_str}{percent_str}"

            if self._cache_size != size_display:
                self.val_size.configure(text=size_display)
                self._cache_size = size_display

    def _record_completed(self, filename: str):
        ext = os.path.splitext(filename)[1].lstrip(".") or "file"
        item = {
            "title": filename,
            "source": self._matched_plugin.plugin_name if self._matched_plugin else "Direct",
            "type": f"✓ {ext.upper()}",
            "ext": ext
        }
        self.completed_history.insert(0, item)
        if len(self.completed_history) > 4:
            self.completed_history.pop()

        self._render_real_history()

    def _render_real_history(self):
        if not self.completed_history:
            return

        for child in self.history_section.winfo_children():
            child.destroy()

        ctk.CTkLabel(
            self.history_section,
            text="Completed Downloads",
            font=styles.FONT_SECTION_TITLE,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(self.history_section, fg_color="transparent")
        grid.pack(fill="x")

        for item in self.completed_history:
            card = ctk.CTkFrame(
                grid,
                fg_color=styles.COLOR_SURFACE_CARD,
                border_color=styles.COLOR_SURFACE_BORDER,
                border_width=1,
                corner_radius=styles.CORNER_RADIUS_CARD,
                width=180
            )
            card.pack(side="left", padx=(0, 10), fill="y")

            c_inner = ctk.CTkFrame(card, fg_color="transparent")
            c_inner.pack(fill="both", expand=True, padx=12, pady=10)

            ctk.CTkLabel(
                c_inner,
                text=item["title"][:22] + "..." if len(item["title"]) > 22 else item["title"],
                font=styles.FONT_BODY_BOLD,
                text_color=styles.COLOR_TEXT_MAIN,
                anchor="w"
            ).pack(fill="x")

            ctk.CTkLabel(
                c_inner,
                text=f"{item['source']}",
                font=styles.FONT_STATS_LABEL,
                text_color=styles.COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill="x", pady=(1, 4))

            badge = ctk.CTkLabel(
                c_inner,
                text=item["type"],
                font=styles.FONT_CHIP,
                text_color=styles.COLOR_SUCCESS_TEXT,
                fg_color=styles.COLOR_SUCCESS_BG,
                corner_radius=6,
                padx=8,
                pady=2
            )
            badge.pack(anchor="w")

        self.history_section.pack(fill="x", pady=(10, 0))
