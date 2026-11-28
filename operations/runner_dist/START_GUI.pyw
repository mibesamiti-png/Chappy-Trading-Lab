"""GUI entry point with an immediate, supervisor-mediated update check."""
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
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


def main():
    session = Path(sys.argv[2]) if len(sys.argv) == 3 and sys.argv[1] == '--ctl-session' else None
    root = tk.Tk()
    app = UpdateDesktop(root, ledger_path(), session=session)
    root.mainloop()
    raise SystemExit(app.exit_code)


if __name__ == '__main__':
    main()
