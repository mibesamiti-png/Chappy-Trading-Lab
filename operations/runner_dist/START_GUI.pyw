"""GUI entry point with an immediate, supervisor-mediated update check."""
import sys
import os
import json
import stat
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from desktop import Desktop, ledger_path
from vault import atomic


class UpdateDesktop(Desktop):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_now_btn = ttk.Button(self.link_btn.master, text='今すぐ更新確認', command=self.check_now)
        self.check_now_btn.pack(side='right', padx=3)
        if self.session is None or not (self.session / 'manual-check-supported').is_file():
            self.log('手動更新確認には新しい起動プログラムが必要です。')

    def check_now(self):
        if self.closing:
            return
        if self.session is None or not (self.session / 'manual-check-supported').is_file():
            self.log('起動プログラムを更新してください。')
            return
        if not self.auto_update.get():
            self.log('自動更新をONにしてから更新確認を押してください。')
            return
        try:
            atomic(self.session / 'check-now', b'1')
        except OSError:
            self.log('更新確認を要求できません。')
            return
        self.log('今すぐ更新確認を要求しました。処理中の場合、適用は完了後です。')


# Local metadata only. Never import a market reader or publish these settings.
ROLES = ('market', 'research')
FORMATS = ('.parquet', '.zip', '.csv', '.sqlite', '.sqlite3', '.db', '.json')
LIMIT = 512


def local_folder(value):
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts or str(p).startswith(('\\\\', '//')):
        raise ValueError('LOCAL_FOLDER_REQUIRED')
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(p.anchor)) != 3:
            raise ValueError('FIXED_DRIVE_REQUIRED')
    for part in p.parts:
        if re.search(r'(^2026$|^2026[_-](?:holdout|test)|holdout|封印)', part, re.I):
            raise ValueError('HOLDOUT_FOLDER_REFUSED')
    for ancestor in reversed((p, *p.parents)):
        info = ancestor.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('DIRECTORY_OR_REPARSE_REFUSED')
    return p


def inventory(value):
    p = local_folder(value)
    counts = {ext: 0 for ext in FORMATS}
    seen = 0
    truncated = False
    with os.scandir(p) as entries:
        for entry in entries:
            if seen >= LIMIT:
                truncated = True
                break
            seen += 1
            # Names only: no stat/open of entries, no recursion, no ZIP listing.
            if re.search(r'2026|holdout|封印', entry.name, re.I):
                continue
            suffix = Path(entry.name).suffix.lower()
            if suffix in counts:
                counts[suffix] += 1
    return counts, truncated


def read_folders(path):
    try:
        with path.open('rb') as f:
            raw = f.read(32769)
        if len(raw) > 32768:
            raise ValueError('SETTINGS_LIMIT')
        obj = json.loads(raw)
        if type(obj) is not dict or set(obj) - set(ROLES) or any(type(v) is not str or not v or len(v) > 4096 for v in obj.values()):
            raise ValueError('SETTINGS_SCHEMA')
        return obj
    except FileNotFoundError:
        return {}


class DataDesktop(UpdateDesktop):
    def __init__(self, *args, **kwargs):
        self.folder_dialog = None
        super().__init__(*args, **kwargs)
        self.folder_btn = ttk.Button(self.link_btn.master, text='研究データ設定', command=self.configure_folders)
        self.folder_btn.pack(side='left', padx=3)

    def update_tick(self):
        if self.folder_dialog is not None:
            return False
        return super().update_tick()

    def configure_folders(self):
        if self.closing or self.folder_dialog is not None:
            return
        config = Path(self.path).parent / 'research_folders.local.json'
        try:
            saved = read_folders(config)
        except (OSError, ValueError, UnicodeError, RecursionError):
            self.log('研究フォルダ設定が読めません。既存設定は変更しません。')
            return
        dialog = tk.Toplevel(self.root)
        self.folder_dialog = dialog
        dialog.title('研究データ設定（PC内のみ）')
        dialog.transient(self.root)
        dialog.geometry('720x420')
        panel = ttk.Frame(dialog, padding=12)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='保存場所を登録：実データの読み込み・研究実行はまだ行いません。', wraplength=680).pack(anchor='w')
        values = {role: tk.StringVar(value=saved.get(role, '')) for role in ROLES}
        output = tk.StringVar(value='未確認。直下の名前だけ最大512件を確認します。')
        def choose(role):
            selected = filedialog.askdirectory(parent=dialog, mustexist=True, title='保存場所を選択')
            if selected:
                values[role].set(selected)
        for role, label in zip(ROLES, ('市場データの保存フォルダ', '既存研究成果の保存フォルダ（任意）')):
            ttk.Label(panel, text=label).pack(anchor='w', pady=(12, 0))
            bar = ttk.Frame(panel)
            bar.pack(fill='x')
            ttk.Entry(bar, textvariable=values[role]).pack(side='left', fill='x', expand=True)
            ttk.Button(bar, text='選択', command=lambda r=role: choose(r)).pack(side='left', padx=5)
        def validated():
            result = {}
            for role, var in values.items():
                value = var.get().strip()
                if value:
                    result[role] = str(local_folder(value))
            return result
        def inspect():
            try:
                folders = validated()
                lines = []
                for role, value in folders.items():
                    counts, capped = inventory(value)
                    lines.append(role + ': ' + ' / '.join(k + ' ' + str(v) for k, v in counts.items()) + ('（上限到達）' if capped else ''))
                output.set('\n'.join(lines) or 'フォルダ未指定')
            except (OSError, ValueError):
                output.set('確認できません。ローカルの通常フォルダを選択してください。')
        def close():
            self.folder_dialog = None
            dialog.destroy()
        def save():
            try:
                folders = validated()
                atomic(config, json.dumps(folders, ensure_ascii=False).encode('utf-8'))
            except (OSError, ValueError, UnicodeError):
                output.set('保存できません。通常のローカルフォルダを選択してください。')
                return
            self.log('研究フォルダ設定をPC内に保存しました。実データ未読。')
            close()
        ttk.Label(panel, textvariable=output, wraplength=680).pack(anchor='w', pady=16)
        ttk.Label(panel, text='件数は拡張子名の候補数です。中身・対象年・データ品質は未確認。\nパスと確認結果は公開投稿しません。', wraplength=680).pack(anchor='w')
        bar = ttk.Frame(panel)
        bar.pack(side='bottom', fill='x')
        ttk.Button(bar, text='直下の形式を確認', command=inspect).pack(side='left')
        ttk.Button(bar, text='保存', command=save).pack(side='right')
        ttk.Button(bar, text='キャンセル', command=close).pack(side='right', padx=5)
        dialog.protocol('WM_DELETE_WINDOW', close)
        dialog.grab_set()


def main():
    session = Path(sys.argv[2]) if len(sys.argv) == 3 and sys.argv[1] == '--ctl-session' else None
    root = tk.Tk()
    app = DataDesktop(root, ledger_path(), session=session)
    root.mainloop()
    raise SystemExit(app.exit_code)


if __name__ == '__main__':
    main()
