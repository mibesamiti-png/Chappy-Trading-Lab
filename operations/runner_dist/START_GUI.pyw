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
ZIP_LIMIT = 32
SETTINGS_LIMIT = 32768


def drive_allowed(kind, allow_removable=False):
    return kind == 3 or (allow_removable and kind == 2)


def local_folder(value, allow_removable=False):
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts or str(p).startswith(('\\\\', '//')):
        raise ValueError('LOCAL_FOLDER_REQUIRED')
    if os.name == 'nt':
        import ctypes
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        get_drive_type.argtypes = [ctypes.c_wchar_p]
        get_drive_type.restype = ctypes.c_uint
        if not drive_allowed(get_drive_type(str(p.anchor)), allow_removable):
            raise ValueError('LOCAL_DRIVE_REQUIRED' if allow_removable else 'FIXED_DRIVE_REQUIRED')
    for part in p.parts:
        if re.search(r'(^2026$|^2026[_-](?:holdout|test)|holdout|封印)', part, re.I):
            raise ValueError('HOLDOUT_FOLDER_REFUSED')
    for ancestor in reversed((p, *p.parents)):
        info = ancestor.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('DIRECTORY_OR_REPARSE_REFUSED')
    return p


def local_zip(value):
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError('ZIP_PATH_REQUIRED')
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts or p.suffix.lower() != '.zip':
        raise ValueError('LOCAL_ZIP_REQUIRED')
    if re.search(r'2026|holdout|封印', p.name, re.I):
        raise ValueError('HOLDOUT_ZIP_REFUSED')
    local_folder(str(p.parent), allow_removable=True)
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('REGULAR_ZIP_REQUIRED')
    return p


def registration_error(exc):
    if isinstance(exc, FileNotFoundError):
        return 'ファイルまたは親フォルダが見つかりません。'
    if isinstance(exc, PermissionError):
        return 'ファイルまたは親フォルダの参照権限がありません。'
    if isinstance(exc, OSError):
        return 'ファイル属性を取得できません。ドライブの接続状態を確認してください。'
    messages = {
        'ZIP_PATH_REQUIRED': 'ZIPのパスが空か長すぎます。',
        'LOCAL_ZIP_REQUIRED': '絶対パスの.zipファイルを選択してください。',
        'LOCAL_FOLDER_REQUIRED': 'ネットワークパスや相対パスは登録できません。',
        'LOCAL_DRIVE_REQUIRED': 'ローカルの固定・リムーバブルドライブを選択してください。',
        'FIXED_DRIVE_REQUIRED': 'フォルダはローカルの固定ドライブを選択してください。',
        'HOLDOUT_ZIP_REFUSED': 'ZIP名が封印データの除外条件（2026、holdout、封印）に該当しました。',
        'HOLDOUT_FOLDER_REFUSED': '親フォルダ名が封印データの除外条件に該当しました。',
        'DIRECTORY_OR_REPARSE_REFUSED': '親フォルダにリンク、ジャンクション、クラウド等の再解析ポイントがあります。',
        'REGULAR_ZIP_REQUIRED': '通常のファイルではないか、リンク等の再解析ポイントです。',
        'ZIP_LIMIT': 'ZIPの登録上限は32件です。',
        'ZIP_LIMIT_OR_SCHEMA': 'ZIPの登録上限または設定形式が不正です。',
        'SETTINGS_LIMIT': '設定ファイルのサイズ上限を超えました。',
    }
    return messages.get(str(exc), '登録条件を満たしていません。')


def zip_paths(values):
    if type(values) is not list or len(values) > ZIP_LIMIT:
        raise ValueError('ZIP_LIMIT_OR_SCHEMA')
    result = []
    seen = set()
    for value in values:
        p = str(local_zip(value))
        key = os.path.normcase(p)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


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
            raw = f.read(SETTINGS_LIMIT + 1)
        if len(raw) > SETTINGS_LIMIT:
            raise ValueError('SETTINGS_LIMIT')
        obj = json.loads(raw)
        if type(obj) is not dict or set(obj) - (set(ROLES) | {'market_zips'}):
            raise ValueError('SETTINGS_SCHEMA')
        if any(type(obj[k]) is not str or not obj[k] or len(obj[k]) > 4096 for k in ROLES if k in obj):
            raise ValueError('SETTINGS_SCHEMA')
        zips = obj.get('market_zips', [])
        if type(zips) is not list or len(zips) > ZIP_LIMIT or any(type(v) is not str or not v or len(v) > 4096 for v in zips):
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
        dialog.geometry('760x620')
        dialog.minsize(620, 540)
        panel = ttk.Frame(dialog, padding=12)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='保存場所を登録：実データの読み込み・研究実行はまだ行いません。', wraplength=680).pack(anchor='w')
        values = {role: tk.StringVar(value=saved.get(role, '')) for role in ROLES}
        output = tk.StringVar(value='未確認。フォルダ直下の名前とZIPの登録状態だけを確認します。')
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
        ttk.Label(panel, text='市場データのZIP（複数可・解凍不要）').pack(anchor='w', pady=(12, 0))
        zip_frame = ttk.Frame(panel)
        zip_frame.pack(fill='x')
        zip_list = tk.Listbox(zip_frame, height=5, selectmode='extended', exportselection=False)
        zip_scroll = ttk.Scrollbar(zip_frame, orient='vertical', command=zip_list.yview)
        zip_list.configure(yscrollcommand=zip_scroll.set)
        zip_list.pack(side='left', fill='both', expand=True)
        zip_scroll.pack(side='right', fill='y')
        for value in saved.get('market_zips', []):
            zip_list.insert('end', value)

        def add_zips():
            selected = filedialog.askopenfilenames(parent=dialog, title='市場データのZIPを選択', filetypes=[('ZIP', '*.zip')])
            if not selected:
                return
            try:
                combined = list(zip_list.get(0, 'end'))
                keys = {os.path.normcase(v) for v in combined}
                for value in selected:
                    p = str(local_zip(value))
                    key = os.path.normcase(p)
                    if key not in keys:
                        keys.add(key)
                        combined.append(p)
                if len(combined) > ZIP_LIMIT:
                    raise ValueError('ZIP_LIMIT')
            except (OSError, ValueError) as exc:
                output.set('追加できません：' + registration_error(exc))
                return
            zip_list.delete(0, 'end')
            for value in combined:
                zip_list.insert('end', value)
            output.set('ZIPを選択しました。保存すると登録されます。中身は未読です。')

        def remove_zips():
            for index in reversed(zip_list.curselection()):
                zip_list.delete(index)
            output.set('登録候補から解除しました。元ファイルは削除しません。')

        zip_buttons = ttk.Frame(panel)
        zip_buttons.pack(fill='x', pady=(3, 0))
        ttk.Button(zip_buttons, text='ZIP追加', command=add_zips).pack(side='left')
        ttk.Button(zip_buttons, text='選択したZIPを解除', command=remove_zips).pack(side='left', padx=5)

        def validated():
            result = {}
            for role, var in values.items():
                value = var.get().strip()
                if value:
                    result[role] = str(local_folder(value))
            zips = zip_paths(list(zip_list.get(0, 'end')))
            if zips:
                result['market_zips'] = zips
            return result
        def inspect():
            try:
                folders = validated()
                lines = []
                for role in ROLES:
                    if role not in folders:
                        continue
                    counts, capped = inventory(folders[role])
                    lines.append(role + ': ' + ' / '.join(k + ' ' + str(v) for k, v in counts.items()) + ('（上限到達）' if capped else ''))
                if folders.get('market_zips'):
                    lines.append('登録ZIP: ' + str(len(folders['market_zips'])) + '件（内容未読）')
                output.set('\n'.join(lines) or '保存場所未指定')
            except (OSError, ValueError) as exc:
                output.set('確認できません：' + registration_error(exc))
        def close():
            self.folder_dialog = None
            dialog.destroy()
        def save():
            try:
                folders = validated()
                raw = json.dumps(folders, ensure_ascii=False).encode('utf-8')
                if len(raw) > SETTINGS_LIMIT:
                    raise ValueError('SETTINGS_LIMIT')
                atomic(config, raw)
            except (OSError, ValueError, UnicodeError) as exc:
                output.set('保存できません：' + registration_error(exc))
                return
            self.log('研究データ設定をPC内に保存しました。実データ未読。')
            close()
        ttk.Label(panel, textvariable=output, wraplength=680).pack(anchor='w', pady=16)
        ttk.Label(panel, text='件数は拡張子名の候補数です。中身・対象年・データ品質は未確認。\nパスと確認結果は公開投稿しません。', wraplength=680).pack(anchor='w')
        bar = ttk.Frame(panel)
        bar.pack(side='bottom', fill='x')
        ttk.Button(bar, text='登録状態を確認', command=inspect).pack(side='left')
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
