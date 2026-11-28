"""Real Tk geometry checks with a minimal synthetic base desktop, no market inputs."""
import ast
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'operations/runner_dist/START_GUI.pyw'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_runner_controls')
scope={'ttk':ttk}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),scope)

class LayoutTests(unittest.TestCase):
    def check_layout(self,manager):
        root=tk.Tk()
        self.addCleanup(root.destroy)
        root.geometry('640x480')
        toolbar=ttk.Frame(root)
        log=tk.Text(root,height=12)
        if manager=='pack':
            toolbar.pack(fill='x')
            log.pack(fill='both',expand=True)
        else:
            toolbar.grid(row=0,column=0,sticky='ew')
            log.grid(row=1,column=0,sticky='nsew')
            root.columnconfigure(0,weight=1)
            root.rowconfigure(1,weight=1)
        class Owner:
            pass
        owner=Owner()
        owner.root=root
        calls=[]
        methods=('configure_folders','run_research_probe','run_ohlcv_probe','configure_parquet',
                 'run_market_catalog','open_market_selection','run_synthetic_research','run_footer_probe','run_batch_adapter_probe','run_control_plane','run_dual_guard','open_diagnostics')
        for name in methods:
            setattr(owner,name,lambda n=name:calls.append(n))
        scope['install_runner_controls'](owner)
        names=('folder_btn','probe_btn','ohlcv_btn','parquet_btn','catalog_btn','selection_btn','synthetic_run_btn','footer_probe_btn','batch_adapter_btn','control_plane_btn','dual_guard_btn','diag_btn')
        for geometry in ('640x480','1000x600','640x480'):
            root.geometry(geometry)
            root.update()
            bottom=root.winfo_rooty()+root.winfo_height()
            right=root.winfo_rootx()+root.winfo_width()
            for name in names:
                btn=getattr(owner,name)
                self.assertTrue(btn.winfo_ismapped(),name)
                self.assertGreaterEqual(btn.winfo_rootx(),root.winfo_rootx(),name)
                self.assertLessEqual(btn.winfo_rootx()+btn.winfo_width(),right,name)
                self.assertLessEqual(btn.winfo_rooty()+btn.winfo_height(),bottom,name)
            self.assertGreaterEqual(owner.runner_footer.winfo_rooty(),log.winfo_rooty()+log.winfo_height())
            self.assertLessEqual(right-(owner.diag_btn.winfo_rootx()+owner.diag_btn.winfo_width()),16)
            self.assertLessEqual(bottom-(owner.diag_btn.winfo_rooty()+owner.diag_btn.winfo_height()),16)
        for name in names:
            getattr(owner,name).invoke()
        self.assertEqual(calls,list(methods))
        owner.diag_btn.configure(state='disabled')
        owner.diag_btn.invoke()
        self.assertEqual(calls,list(methods))
    def test_packed_desktop(self):
        self.check_layout('pack')
    def test_gridded_desktop(self):
        self.check_layout('grid')
if __name__=='__main__':
    unittest.main()
