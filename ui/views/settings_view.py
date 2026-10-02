"""
Settings View: SpotiFLAC-inspired Clean Preferences with Color Mode Selector and Tuning.
"""

from tkinter import filedialog
import customtkinter as ctk

from config.settings import AppSettings
from core.speed_tester import NetworkSpeedTester
from ui import styles


class SettingsView(ctk.CTkFrame):
    """アプリケーション設定画面 (Nexus DL)"""

    def __init__(self, master, settings: AppSettings, on_settings_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.settings = settings
        self.on_settings_change = on_settings_change
        self._is_testing_speed = False

        self._build_ui()

    def _build_ui(self):
        self.scroll_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=("#E2E8F0", "#333338"),
            scrollbar_button_hover_color=("#CBD5E1", "#44444C")
        )
        self.scroll_container.pack(fill="both", expand=True, padx=40, pady=24)

        header = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        header.pack(fill="x", pady=(8, 16))

        ctk.CTkLabel(
            header,
            text="Preferences",
            font=styles.FONT_PAGE_TITLE,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="保存場所、外観カラーモード（Light/Dark）、およびネットワーク並列化パラメータを調整します",
            font=styles.FONT_SUBTITLE,
            text_color=styles.COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(2, 0))

        # 1. 保存先ストレージ
        self._build_storage_card()

        # 2. テーマ・カラーモード設定
        self._build_appearance_card()

        # 3. 詳細設定トグル
        self._build_advanced_toggle()

        # 4. 詳細設定コンテナ
        self.advanced_container = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self._build_advanced_settings_content()

        if self.settings.get("show_advanced_settings", False):
            self.advanced_container.pack(fill="x", pady=(8, 0))

    def _build_storage_card(self):
        card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text="Download Directory", font=styles.FONT_BODY_BOLD, text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(inner, text="ダウンロード完了時の保存先フォルダ", font=styles.FONT_STATS_LABEL, text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", pady=(1, 10))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")

        self.dir_entry = ctk.CTkEntry(
            row,
            height=38,
            corner_radius=styles.CORNER_RADIUS_INPUT,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            font=styles.FONT_BODY
        )
        self.dir_entry.insert(0, self.settings.get("download_directory", ""))
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            row,
            text="参照...",
            width=84,
            height=38,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_browse_dir
        )
        browse_btn.pack(side="left")

    def _build_appearance_card(self):
        card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text="Theme & Color Mode", font=styles.FONT_BODY_BOLD, text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(inner, text="アプリケーションの外観カラーモード（ライト／ダーク／システム同期）を切り替えます", font=styles.FONT_STATS_LABEL, text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", pady=(1, 8))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(row, text="カラーモード:", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MAIN).pack(side="left", padx=(0, 16))

        current_mode = self.settings.get("appearance_mode", "light").capitalize()
        self.mode_menu = ctk.CTkOptionMenu(
            row,
            values=["Light", "Dark", "System"],
            command=self._on_change_mode,
            width=130,
            height=34,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            button_color=styles.COLOR_SURFACE_BORDER,
            button_hover_color=styles.COLOR_ACCENT,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON
        )
        self.mode_menu.set(current_mode)
        self.mode_menu.pack(side="left")

    def _build_advanced_toggle(self):
        toggle_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        toggle_frame.pack(fill="x", pady=(8, 8))

        self.adv_check_var = ctk.BooleanVar(value=self.settings.get("show_advanced_settings", False))
        self.adv_checkbox = ctk.CTkCheckBox(
            toggle_frame,
            text="詳細設定を表示する（回線速度テスト・並列化パラメータ・プロキシ）",
            font=styles.FONT_BODY_BOLD,
            variable=self.adv_check_var,
            command=self._on_toggle_advanced,
            fg_color=styles.COLOR_ACCENT,
            hover_color=styles.COLOR_ACCENT_HOVER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=6
        )
        self.adv_checkbox.pack(side="left")

    def _on_toggle_advanced(self):
        is_shown = self.adv_check_var.get()
        self.settings.set("show_advanced_settings", is_shown)
        if is_shown:
            self.advanced_container.pack(fill="x", pady=(6, 0))
        else:
            self.advanced_container.pack_forget()

    def _build_advanced_settings_content(self):
        # A. 速度テスト
        card_speed = ctk.CTkFrame(
            self.advanced_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_FETCH_BTN,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card_speed.pack(fill="x", pady=(0, 12))

        inner_speed = ctk.CTkFrame(card_speed, fg_color="transparent")
        inner_speed.pack(fill="x", padx=20, pady=16)

        top_speed = ctk.CTkFrame(inner_speed, fg_color="transparent")
        top_speed.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(top_speed, text="🚀 ネットワーク速度テスト & 並列度自動調整", font=styles.FONT_BODY_BOLD, text_color=styles.COLOR_TEXT_MAIN).pack(side="left")

        self.auto_tune_var = ctk.BooleanVar(value=self.settings.get("auto_tune_concurrency", True))
        auto_tune_switch = ctk.CTkSwitch(
            top_speed,
            text="自動最適化を有効化",
            variable=self.auto_tune_var,
            command=lambda: self.settings.set("auto_tune_concurrency", self.auto_tune_var.get()),
            progress_color=styles.COLOR_ACCENT,
            text_color=styles.COLOR_TEXT_MAIN,
            font=styles.FONT_STATS_LABEL
        )
        auto_tune_switch.pack(side="right")

        self.speed_status_lbl = ctk.CTkLabel(
            inner_speed,
            text=f"直近の測定: {self.settings.get('last_speed_test_summary', '未計測')}",
            font=styles.FONT_BODY,
            text_color=styles.COLOR_ACCENT_TEXT,
            anchor="w"
        )
        self.speed_status_lbl.pack(fill="x", pady=(2, 10))

        self.btn_run_speed_test = ctk.CTkButton(
            inner_speed,
            text="回線速度テストを今すぐ実行",
            height=34,
            font=styles.FONT_BODY_BOLD,
            fg_color=styles.COLOR_FETCH_BTN,
            hover_color=styles.COLOR_FETCH_BTN_HOVER,
            text_color=styles.COLOR_FETCH_BTN_TEXT,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_run_speed_test_manual
        )
        self.btn_run_speed_test.pack(anchor="w")

        # B. ネットワーク詳細
        card_net = ctk.CTkFrame(
            self.advanced_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card_net.pack(fill="x", pady=(0, 12))

        inner_net = ctk.CTkFrame(card_net, fg_color="transparent")
        inner_net.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner_net, text="ネットワーク・スレッド詳細設定", font=styles.FONT_BODY_BOLD, text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w")

        row_thread = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_thread.pack(fill="x", pady=(10, 6))
        ctk.CTkLabel(row_thread, text="最大並列接続数 (Threads):", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MUTED, width=190, anchor="w").pack(side="left")
        self.thread_slider = ctk.CTkSlider(
            row_thread,
            from_=1,
            to=16,
            number_of_steps=15,
            progress_color=styles.COLOR_ACCENT,
            command=self._on_thread_slider_change
        )
        curr_threads = self.settings.get("max_concurrency", 4)
        self.thread_slider.set(curr_threads)
        self.thread_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.thread_lbl = ctk.CTkLabel(row_thread, text=f"{curr_threads} Threads", font=styles.FONT_BODY_BOLD, text_color=styles.COLOR_TEXT_MAIN, width=80)
        self.thread_lbl.pack(side="left")

        row_chunk = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_chunk.pack(fill="x", pady=4)
        ctk.CTkLabel(row_chunk, text="ストリーム・バッファ (KB):", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MUTED, width=190, anchor="w").pack(side="left")
        self.chunk_opt = ctk.CTkOptionMenu(
            row_chunk,
            values=["64", "128", "256", "512", "1024", "2048"],
            width=130,
            height=32,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            button_color=styles.COLOR_SURFACE_BORDER,
            button_hover_color=styles.COLOR_ACCENT,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=lambda v: self.settings.set("chunk_size_kb", int(v))
        )
        self.chunk_opt.set(str(self.settings.get("chunk_size_kb", 256)))
        self.chunk_opt.pack(side="left")

        row_timeout = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_timeout.pack(fill="x", pady=4)
        ctk.CTkLabel(row_timeout, text="HTTPタイムアウト (秒):", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MUTED, width=190, anchor="w").pack(side="left")
        self.timeout_entry = ctk.CTkEntry(row_timeout, width=130, height=32, fg_color=styles.COLOR_SURFACE_CARD, border_color=styles.COLOR_SURFACE_BORDER, text_color=styles.COLOR_TEXT_MAIN, corner_radius=styles.CORNER_RADIUS_INPUT)
        self.timeout_entry.insert(0, str(self.settings.get("timeout_seconds", 30)))
        self.timeout_entry.pack(side="left")

        row_retry = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_retry.pack(fill="x", pady=4)
        ctk.CTkLabel(row_retry, text="HTTPリトライ上限回数:", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MUTED, width=190, anchor="w").pack(side="left")
        self.retry_entry = ctk.CTkEntry(row_retry, width=130, height=32, fg_color=styles.COLOR_SURFACE_CARD, border_color=styles.COLOR_SURFACE_BORDER, text_color=styles.COLOR_TEXT_MAIN, corner_radius=styles.CORNER_RADIUS_INPUT)
        self.retry_entry.insert(0, str(self.settings.get("request_retries", 3)))
        self.retry_entry.pack(side="left")

        row_resume = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_resume.pack(fill="x", pady=4)
        self.resume_var = ctk.BooleanVar(value=self.settings.get("enable_resume", True))
        resume_switch = ctk.CTkSwitch(
            row_resume,
            text="レジューム（部分ダウンロード再開）を有効化",
            variable=self.resume_var,
            progress_color=styles.COLOR_ACCENT,
            text_color=styles.COLOR_TEXT_MAIN,
            command=lambda: self.settings.set("enable_resume", self.resume_var.get()),
            font=styles.FONT_BODY
        )
        resume_switch.pack(side="left")

        row_proxy = ctk.CTkFrame(inner_net, fg_color="transparent")
        row_proxy.pack(fill="x", pady=4)
        ctk.CTkLabel(row_proxy, text="HTTP/HTTPS プロキシ:", font=styles.FONT_BODY, text_color=styles.COLOR_TEXT_MUTED, width=190, anchor="w").pack(side="left")
        self.proxy_entry = ctk.CTkEntry(row_proxy, placeholder_text="例: http://127.0.0.1:7890", height=32, fg_color=styles.COLOR_SURFACE_CARD, border_color=styles.COLOR_SURFACE_BORDER, text_color=styles.COLOR_TEXT_MAIN, corner_radius=styles.CORNER_RADIUS_INPUT)
        self.proxy_entry.insert(0, self.settings.get("proxy_url", ""))
        self.proxy_entry.pack(side="left", fill="x", expand=True)

        save_btn = ctk.CTkButton(
            inner_net,
            text="詳細設定を保存",
            width=130,
            height=34,
            font=styles.FONT_BODY_BOLD,
            fg_color=styles.COLOR_FETCH_BTN,
            hover_color=styles.COLOR_FETCH_BTN_HOVER,
            text_color=styles.COLOR_FETCH_BTN_TEXT,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_save_advanced_settings
        )
        save_btn.pack(anchor="e", pady=(12, 0))

    def _on_thread_slider_change(self, val):
        t = int(round(val))
        self.thread_lbl.configure(text=f"{t} Threads")
        self.settings.set("max_concurrency", t)

    def _on_save_advanced_settings(self):
        try:
            timeout_sec = int(self.timeout_entry.get().strip())
            self.settings.set("timeout_seconds", timeout_sec)
        except ValueError:
            pass

        try:
            retries = int(self.retry_entry.get().strip())
            self.settings.set("request_retries", retries)
        except ValueError:
            pass

        proxy = self.proxy_entry.get().strip()
        self.settings.set("proxy_url", proxy)

        if self.on_settings_change:
            self.on_settings_change()

    def _on_browse_dir(self):
        selected = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if selected:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, selected)
            self.settings.set("download_directory", selected)
            if self.on_settings_change:
                self.on_settings_change()

    def _on_change_mode(self, mode: str):
        mode_lower = mode.lower()
        ctk.set_appearance_mode(mode_lower)
        self.settings.set("appearance_mode", mode_lower)

    def _on_run_speed_test_manual(self):
        if self._is_testing_speed:
            return
        self._is_testing_speed = True
        self.btn_run_speed_test.configure(state="disabled", text="テスト計測中...")

        def _worker():
            try:
                res = NetworkSpeedTester.run_benchmark(
                    progress_callback=lambda msg: self.after(0, lambda: self.speed_status_lbl.configure(text=msg))
                )
                self.settings.set("last_speed_test_mbps", res.bandwidth_mbps)
                self.settings.set("last_speed_test_summary", res.summary_text)

                if self.auto_tune_var.get():
                    self.settings.set("max_concurrency", res.recommended_concurrency)
                    self.settings.set("chunk_size_kb", res.recommended_chunk_kb)

                self.after(0, lambda: self._on_speed_test_done(res))
            except Exception as e:
                self.after(0, lambda: self.speed_status_lbl.configure(text=f"計測失敗: {e}"))
            finally:
                self._is_testing_speed = False
                self.after(0, lambda: self.btn_run_speed_test.configure(state="normal", text="回線速度テストを今すぐ実行"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_speed_test_done(self, res):
        self.speed_status_lbl.configure(text=f"測定完了: {res.summary_text}")
        self.thread_slider.set(res.recommended_concurrency)
        self.thread_lbl.configure(text=f"{res.recommended_concurrency} Threads")
        self.chunk_opt.set(str(res.recommended_chunk_kb))
        if self.on_settings_change:
            self.on_settings_change()
