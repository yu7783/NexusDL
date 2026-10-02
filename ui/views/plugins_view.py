"""
Plugins View: SpotiFLAC-inspired Clean Add-on Manager & Dedicated 2-Way Installer.
Supports installation ONLY via:
1. GitHub Repository URL paste
2. Local .py or .zip file picker
Fully responsive to Light and Dark color modes.
"""

from tkinter import filedialog
import threading
import customtkinter as ctk

from core.addon_installer import AddonInstaller
from core.plugin_loader import PluginManager
from ui import styles


class PluginsView(ctk.CTkFrame):
    """アドオン管理＆2系統専用インストーラー画面 (Nexus DL)"""

    def __init__(self, master, plugin_manager: PluginManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.plugin_manager = plugin_manager
        self.installer = AddonInstaller(plugin_manager.plugins_dir)
        self._is_installing = False

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

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Add-on Store & Manager",
            font=styles.FONT_PAGE_TITLE,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="ダウンロード対応サイトを拡張するプラグインの導入と管理を行います",
            font=styles.FONT_SUBTITLE,
            text_color=styles.COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(2, 0))

        reload_btn = ctk.CTkButton(
            header,
            text="🔄 再読み込み",
            width=96,
            height=34,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_SURFACE_SUBTLE,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self.refresh_list
        )
        reload_btn.pack(side="right")

        self._build_installer_card()

        ctk.CTkLabel(
            self.scroll_container,
            text="Installed Add-ons",
            font=styles.FONT_SECTION_TITLE,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(anchor="w", pady=(12, 10))

        self.cards_container = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.cards_container.pack(fill="x")

        self.refresh_list()

    def _build_installer_card(self):
        card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card.pack(fill="x", pady=(0, 14))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)

        ctk.CTkLabel(
            inner,
            text="Install New Add-on",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(anchor="w")

        ctk.CTkLabel(
            inner,
            text="アドオンの追加は「GitHubリポジトリURL」または「ローカルファイル (.zip / .py)」からのみ安全に行えます",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(2, 12))

        # 方式1: GitHub URL
        gh_box = ctk.CTkFrame(inner, fg_color=styles.COLOR_SURFACE_SUBTLE, corner_radius=styles.CORNER_RADIUS_BUTTON)
        gh_box.pack(fill="x", pady=(0, 10))

        gh_inner = ctk.CTkFrame(gh_box, fg_color="transparent")
        gh_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            gh_inner,
            text="① GitHubリポジトリ:",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN,
            width=160,
            anchor="w"
        ).pack(side="left")

        self.gh_entry = ctk.CTkEntry(
            gh_inner,
            placeholder_text="https://github.com/owner/repository",
            font=styles.FONT_BODY,
            height=34,
            border_width=1,
            border_color=styles.COLOR_SURFACE_BORDER,
            fg_color=styles.COLOR_SURFACE_CARD,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_INPUT
        )
        self.gh_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.gh_install_btn = ctk.CTkButton(
            gh_inner,
            text="インストール",
            width=96,
            height=34,
            font=styles.FONT_BODY_BOLD,
            fg_color=styles.COLOR_FETCH_BTN,
            hover_color=styles.COLOR_FETCH_BTN_HOVER,
            text_color=styles.COLOR_FETCH_BTN_TEXT,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_install_github
        )
        self.gh_install_btn.pack(side="left")

        # 方式2: ローカルファイル
        file_box = ctk.CTkFrame(inner, fg_color=styles.COLOR_SURFACE_SUBTLE, corner_radius=styles.CORNER_RADIUS_BUTTON)
        file_box.pack(fill="x", pady=(0, 8))

        file_inner = ctk.CTkFrame(file_box, fg_color="transparent")
        file_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            file_inner,
            text="② ローカルファイル:",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN,
            width=160,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            file_inner,
            text=".zip (推奨: manifest.json同梱) または .py スクリプト",
            font=styles.FONT_BODY,
            text_color=styles.COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(side="left", fill="x", expand=True)

        self.file_pick_btn = ctk.CTkButton(
            file_inner,
            text="ファイルを選択...",
            width=130,
            height=34,
            font=styles.FONT_BODY,
            fg_color=styles.COLOR_SURFACE_CARD,
            hover_color=styles.COLOR_SURFACE_BORDER,
            text_color=styles.COLOR_TEXT_MAIN,
            corner_radius=styles.CORNER_RADIUS_BUTTON,
            command=self._on_pick_local_file
        )
        self.file_pick_btn.pack(side="right")

        self.install_status_lbl = ctk.CTkLabel(
            inner,
            text="",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_ACCENT_TEXT,
            anchor="w"
        )
        self.install_status_lbl.pack(fill="x", pady=(4, 0))

    def _on_install_github(self):
        url = self.gh_entry.get().strip()
        if not url:
            self.install_status_lbl.configure(text="GitHubリポジトリURLを入力してください。", text_color=styles.COLOR_WARNING_TEXT)
            return

        if self._is_installing:
            return
        self._is_installing = True
        self.gh_install_btn.configure(state="disabled", text="取得中...")
        self.install_status_lbl.configure(text="GitHubからダウンロードおよび安全検査を実行中...", text_color=styles.COLOR_ACCENT_TEXT)

        def _worker():
            success, msg = self.installer.install_from_github(url)
            self.after(0, lambda: self._on_install_finished(success, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_pick_local_file(self):
        file_path = filedialog.askopenfilename(
            title="アドオンファイルの選択",
            filetypes=[("Add-on Packages", "*.zip;*.py"), ("ZIP Archive", "*.zip"), ("Python Script", "*.py")]
        )
        if not file_path:
            return

        if self._is_installing:
            return
        self._is_installing = True
        self.file_pick_btn.configure(state="disabled")
        self.install_status_lbl.configure(text="安全検査およびアドオン配置を実行中...", text_color=styles.COLOR_ACCENT_TEXT)

        def _worker():
            success, msg = self.installer.install_from_local_file(file_path)
            self.after(0, lambda: self._on_install_finished(success, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_install_finished(self, success: bool, msg: str):
        self._is_installing = False
        self.gh_install_btn.configure(state="normal", text="インストール")
        self.file_pick_btn.configure(state="normal")

        if success:
            self.install_status_lbl.configure(text=f"✓ {msg}", text_color=styles.COLOR_SUCCESS_TEXT)
            self.gh_entry.delete(0, "end")
            self.refresh_list()
        else:
            self.install_status_lbl.configure(text=f"✕ {msg}", text_color=styles.COLOR_DANGER_TEXT)

    def refresh_list(self):
        for child in self.cards_container.winfo_children():
            child.destroy()

        self.plugin_manager.discover_and_load_all()

        if self.plugin_manager.failed_plugins:
            for fname, err in self.plugin_manager.failed_plugins:
                self._build_failed_card(fname, err)

        if not self.plugin_manager.plugins:
            empty_lbl = ctk.CTkLabel(
                self.cards_container,
                text="有効なプラグインが見つかりません。上記インストーラーから追加してください。",
                font=styles.FONT_BODY,
                text_color=styles.COLOR_TEXT_MUTED
            )
            empty_lbl.pack(pady=30)
            return

        for p in self.plugin_manager.plugins:
            self._build_plugin_card(p)

    def _build_plugin_card(self, p):
        card = ctk.CTkFrame(
            self.cards_container,
            fg_color=styles.COLOR_SURFACE_CARD,
            border_color=styles.COLOR_SURFACE_BORDER,
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            top,
            text=f"{p.plugin_name}",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_TEXT_MAIN
        ).pack(side="left")

        pkg_text = "📄 .py" if p.package_type == "py" else "📦 .zip (推奨)"
        ctk.CTkLabel(
            top,
            text=pkg_text,
            font=styles.FONT_CHIP,
            text_color=styles.COLOR_ACCENT_TEXT,
            fg_color=styles.COLOR_ACCENT_BG,
            corner_radius=6,
            padx=7,
            pady=2
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            top,
            text=f"v{p.version} • by {p.author}",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_TEXT_MUTED
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            top,
            text="✓ 安全検査 合格",
            font=styles.FONT_BADGE,
            text_color=styles.COLOR_SUCCESS_TEXT,
            fg_color=styles.COLOR_SUCCESS_BG,
            corner_radius=styles.CORNER_RADIUS_PILL,
            padx=10,
            pady=2
        ).pack(side="right")

        ctk.CTkLabel(
            inner,
            text=p.description,
            font=styles.FONT_BODY,
            text_color=styles.COLOR_TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=680
        ).pack(fill="x", pady=(4, 10))

        dom_box = ctk.CTkFrame(inner, fg_color=styles.COLOR_SURFACE_SUBTLE, corner_radius=styles.CORNER_RADIUS_BUTTON)
        dom_box.pack(fill="x")

        dom_inner = ctk.CTkFrame(dom_box, fg_color="transparent")
        dom_inner.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(
            dom_inner,
            text="対応ドメイン:",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_TEXT_SUBTLE
        ).pack(side="left", padx=(0, 6))

        for dom in p.supported_domains:
            display_dom = "全ドメイン (Fallback)" if dom == "*" else dom
            ctk.CTkLabel(
                dom_inner,
                text=display_dom,
                font=styles.FONT_STATS_LABEL,
                text_color=styles.COLOR_TEXT_MAIN,
                fg_color=styles.COLOR_SURFACE_CARD,
                corner_radius=6,
                padx=8,
                pady=2
            ).pack(side="left", padx=(0, 4))

    def _build_failed_card(self, fname: str, error_msg: str):
        card = ctk.CTkFrame(
            self.cards_container,
            fg_color=styles.COLOR_DANGER_BG,
            border_color="#FCA5A5",
            border_width=1,
            corner_radius=styles.CORNER_RADIUS_CARD
        )
        card.pack(fill="x", pady=(0, 10))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            top,
            text=f"⚠️ 読み込み拒絶: {fname}",
            font=styles.FONT_BODY_BOLD,
            text_color=styles.COLOR_DANGER_TEXT
        ).pack(side="left")

        ctk.CTkLabel(
            top,
            text="安全ポリシー違反",
            font=styles.FONT_BADGE,
            text_color="#FFFFFF",
            fg_color=styles.COLOR_DANGER,
            corner_radius=styles.CORNER_RADIUS_PILL,
            padx=8,
            pady=2
        ).pack(side="right")

        ctk.CTkLabel(
            inner,
            text=f"理由: {error_msg}\n※ プラグインはURL解析責務に特化する必要があり、不正通信や自己更新等は遮断されます。",
            font=styles.FONT_STATS_LABEL,
            text_color=styles.COLOR_DANGER_TEXT,
            anchor="w",
            justify="left"
        ).pack(fill="x")
