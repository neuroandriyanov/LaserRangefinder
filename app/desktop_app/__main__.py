"""Run with python -m desktop_app. No instruments start polling on normal launch."""
import argparse
import os
from pathlib import Path
import sys

from .model import ROOT, SettingsStore


def main():
    parser = argparse.ArgumentParser(description="Панель лазерного дальномера")
    parser.add_argument("--demo", action="store_true", help="Демонстрационные данные без приборов")
    parser.add_argument("--settings", type=Path, help="Отдельный файл настроек")
    parser.add_argument("--capture-dir", type=Path, help="Каталог журналов")
    parser.add_argument("--close-after", type=float, help="Закрыть окно через указанное число секунд (проверка UI)")
    args = parser.parse_args()
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
    import tkinter as tk
    from .ui import App
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    settings = args.settings or (ROOT / ".cache/desktop-demo/settings.json" if args.demo else None)
    root = tk.Tk()
    app = App(root, SettingsStore(settings), args.demo, args.capture_dir)
    if args.close_after:
        root.after(max(1, int(args.close_after * 1000)), app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
