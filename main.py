"""
Application Entry Point.
Launches the CustomTkinter Multi-threaded Modular Downloader.
"""

import os
import sys

# プロジェクトルートをPython検索パスに追加
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from ui.app import App


def main():
    app = App(project_root=CURRENT_DIR)
    app.mainloop()


if __name__ == "__main__":
    main()
