"""GUI entry point with an immediate, supervisor-mediated update check."""
import sys
import os
import json
import stat
import re
import io
import zipfile
import struct
import sqlite3
import csv
from datetime import date, datetime, timezone, timedelta
import base64
import hashlib
import importlib.util
import subprocess
import threading
import queue
import time
import math
import urllib.request
import urllib.error
from app_version import VERSION
from tkinter import messagebox
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from desktop import Desktop, ledger_path
from vault import atomic


UPDATE_INTERVAL_MS=120000
UPDATE_MANIFEST_URL='https://raw.githubusercontent.com/mibesamiti-png/Chappy-Trading-Lab/refs/heads/chat/runner-source-releases-20261128/operations/runner_release.json'
UPDATE_MANIFEST_LIMIT=16384
UPDATE_FILE_NAMES=frozenset(('START_GUI.pyw','api_bridge.py','app_version.py','desktop.py','synthetic_mailbox.py','vault.py'))


def update_version_tuple(value):
    if type(value) is not str or not re.fullmatch(r'(?:0|[1-9][0-9]{0,5})\.(?:0|[1-9][0-9]{0,5})\.(?:0|[1-9][0-9]{0,5})',value):
        raise ValueError('UPDATE_VERSION_INVALID')
    return tuple(map(int,value.split('.')))


def update_manifest_version(raw):
    if len(raw)>UPDATE_MANIFEST_LIMIT:
        raise ValueError('UPDATE_MANIFEST_LIMIT')
    data=json.loads(raw)
    if (type(data) is not dict or data.get('schema')!=1 or data.get('scope')!='SYNTHETIC_ONLY' or
            type(data.get('min_launcher')) is not int or data['min_launcher']<1 or
            type(data.get('files')) is not dict or set(data['files'])!=UPDATE_FILE_NAMES or
            any(type(v) is not str or not re.fullmatch(r'[0-9a-f]{64}',v) for v in data['files'].values())):
        raise ValueError('UPDATE_MANIFEST_INVALID')
    update_version_tuple(data.get('version'))
    return data['version']


def update_probe(local_version,opener=None):
    start=time.monotonic()
    status=None
    remote=None
    code='FAILED_INTERNAL'
    try:
        local=update_version_tuple(local_version)
        url=UPDATE_MANIFEST_URL+'?ctl_check='+str(time.time_ns())
        request=urllib.request.Request(url,headers={'User-Agent':'Chappy-Trading-Lab-Update-Probe',
                                                     'Cache-Control':'no-cache, no-store',
                                                     'Pragma':'no-cache'})
        if opener is None:
            opener=urllib.request.urlopen
        with opener(request,timeout=8) as response:
            status=response.status
            if status!=200 or response.geturl()!=url:
                raise ValueError('UPDATE_RESPONSE_INVALID')
            remote=update_manifest_version(response.read(UPDATE_MANIFEST_LIMIT+1))
        actual=update_version_tuple(remote)
        code='NEWER' if actual>local else 'SAME' if actual==local else 'REMOTE_OLDER'
    except urllib.error.HTTPError as exc:
        status=exc.code
        code='FAILED_HTTP'
    except (urllib.error.URLError,TimeoutError,OSError):
        code='FAILED_CONNECTION'
    except (ValueError,TypeError,KeyError,RecursionError):
        code='FAILED_MANIFEST'
    except Exception:
        code='FAILED_INTERNAL'
    return {'code':code,'http':status,'local':local_version,'remote':remote,
            'ms':max(0,int((time.monotonic()-start)*1000))}


def update_probe_text(result):
    http='未取得' if result['http'] is None else str(result['http'])
    remote=result['remote'] or '未確認'
    labels={'NEWER':'新版の応答あり（署名検証・適用は起動側）',
            'SAME':'配信応答の版は同一（署名・配信先端は未検証）',
            'REMOTE_OLDER':'配信応答が古い・最新状態未確認',
            'FAILED_HTTP':'HTTPエラー・最新状態未確認',
            'FAILED_CONNECTION':'通信失敗・最新状態未確認',
            'FAILED_MANIFEST':'応答検証失敗・最新状態未確認',
            'FAILED_INTERNAL':'確認失敗・最新状態未確認'}
    return f"更新通信：HTTP {http} / 現在 {result['local']} / 応答 {remote} / {result['ms']/1000:.2f}秒 / {labels[result['code']]}"


class UpdateDesktop(Desktop):
    def __init__(self, *args, **kwargs):
        self.update_probe_busy=False
        self.update_probe_results=queue.Queue()
        self.last_update_probe=None
        super().__init__(*args, **kwargs)
        self.check_now_btn=ttk.Button(self.link_btn.master,text='今すぐ更新確認',command=self.check_now)
        self.check_now_btn.pack(side='right',padx=3)
        if self.session is None or not (self.session/'manual-check-supported').is_file():
            self.log('更新の適用要求には対応した起動プログラムが必要です。')
        self.root.after(1000,self.periodic_update_probe)

    def periodic_update_probe(self):
        if self.closing:
            return
        if self.auto_update.get():
            self.begin_update_probe(False)
        self.root.after(UPDATE_INTERVAL_MS,self.periodic_update_probe)

    def check_now(self):
        if self.closing:
            return
        if not self.auto_update.get():
            self.log('自動更新をONにしてから更新確認を押してください。')
            return
        self.begin_update_probe(True)

    def begin_update_probe(self,manual):
        if self.update_probe_busy:
            if manual:
                self.log('更新通信は既に実行中です。')
            return
        self.update_probe_busy=True
        self.check_now_btn.configure(state='disabled')
        self.log(('手動' if manual else '定期')+'更新確認：GitHubへ通信開始。')
        def run():
            self.update_probe_results.put(update_probe(VERSION))
        threading.Thread(target=run,daemon=True).start()
        self.root.after(100,self.poll_update_probe)

    def poll_update_probe(self):
        if self.closing:
            return
        try:
            result=self.update_probe_results.get_nowait()
        except queue.Empty:
            self.root.after(100,self.poll_update_probe)
            return
        self.update_probe_busy=False
        self.last_update_probe=result
        self.check_now_btn.configure(state='normal')
        self.log(update_probe_text(result))
        if result['code']!='NEWER':
            return
        if not self.auto_update.get():
            self.log('自動更新がOFFのため適用要求は送信しません。')
            return
        if self.session is None or not (self.session/'manual-check-supported').is_file():
            self.log('新版を検出しましたが、起動プログラムが適用要求に未対応です。')
            return
        try:
            pending=self.session/'check-now'
            if pending.exists():
                self.log('新版の更新要求は既に送信済みです。')
                return
            atomic(pending,b'1')
        except OSError:
            self.log('新版の更新要求を送信できません。')
            return
        self.log('新版の更新要求を送信しました。署名検証・取得・適用は起動プログラムが担当します。')


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


# Synthetic research pipeline only. No caller-supplied path or real archive is opened.
PROBE_MAX_ARCHIVE = 2 * 1024 * 1024
PROBE_MAX_MEMBER = 512 * 1024
PROBE_MAX_ENTRIES = 128
PROBE_MAX_RATIO = 200
PROBE_PROTOCOL = 'synthetic-zip-period-v1'


def probe_zip_catalog(archive):
    if type(archive) is not bytes or len(archive) > PROBE_MAX_ARCHIVE:
        raise ValueError('PROBE_ARCHIVE_LIMIT')
    with zipfile.ZipFile(io.BytesIO(archive), 'r') as z:
        infos = z.infolist()
        if len(infos) > PROBE_MAX_ENTRIES:
            raise ValueError('PROBE_ENTRY_LIMIT')
        catalog = {}
        total = 0
        for item in infos:
            name = item.filename
            parts = name.rstrip('/').split('/')
            if (not name or '\\' in name or any(not p or p in ('.', '..') or ':' in p for p in parts)
                    or any(ord(c) < 32 for c in name) or item.orig_filename != name):
                raise ValueError('PROBE_UNSAFE_NAME')
            key = name.rstrip('/').casefold()
            if key in catalog:
                raise ValueError('PROBE_DUPLICATE')
            mode = (item.external_attr >> 16) & 0xFFFF
            if (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or item.flag_bits & 1
                    or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError('PROBE_UNSUPPORTED_ENTRY')
            if (item.file_size > PROBE_MAX_MEMBER
                    or item.file_size > PROBE_MAX_RATIO * max(item.compress_size, 1)):
                raise ValueError('PROBE_MEMBER_LIMIT')
            total += item.file_size
            if total > PROBE_MAX_ARCHIVE:
                raise ValueError('PROBE_TOTAL_LIMIT')
            catalog[key] = item
        return catalog


def probe_read_member(archive, name):
    catalog = probe_zip_catalog(archive)
    item = catalog.get(name.casefold())
    if item is None or item.is_dir() or item.filename != name:
        raise ValueError('PROBE_MEMBER_MISSING')
    with zipfile.ZipFile(io.BytesIO(archive), 'r') as z:
        with z.open(item.filename, 'r') as stream:
            result = stream.read(PROBE_MAX_MEMBER + 1)
        if len(result) != item.file_size or len(result) > PROBE_MAX_MEMBER:
            raise ValueError('PROBE_MEMBER_SIZE')
        return result


def probe_period_rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
    if reader.fieldnames != ['date', 'value']:
        raise ValueError('PROBE_SCHEMA')
    values = []
    for row in reader:
        if len(values) >= 4096 or None in row:
            raise ValueError('PROBE_ROW_LIMIT')
        day = date.fromisoformat(row['date'])
        if row['date'] != day.isoformat() or not (date(2000, 1, 1) <= day < date(2026, 1, 1)):
            raise ValueError('PROBE_PERIOD_LOCKED')
        if not re.fullmatch(r'-?[0-9]{1,6}', row['value'] or ''):
            raise ValueError('PROBE_VALUE')
        values.append(int(row['value']))
    if not values:
        raise ValueError('PROBE_EMPTY')
    return {'rows': len(values), 'sum': sum(values)}


def probe_fixture():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('synthetic/selected.csv', b'date,value\n2025-01-02,3\n2025-01-03,-1\n2025-01-06,8\n')
        z.writestr('synthetic/other.csv', b'date,value\n2025-01-02,999\n')
    return buffer.getvalue()


def synthetic_zip_probe():
    archive = probe_fixture()
    catalog = probe_zip_catalog(archive)
    selected = probe_read_member(archive, 'synthetic/selected.csv')
    result = probe_period_rows(selected)
    if len(catalog) != 2 or result != {'rows': 3, 'sum': 10}:
        raise ValueError('PROBE_WRONG_RESULT')
    try:
        probe_period_rows(b'date,value\n2026-01-02,1\n')
    except ValueError as exc:
        if str(exc) != 'PROBE_PERIOD_LOCKED':
            raise
    else:
        raise ValueError('PROBE_PERIOD_GATE_FAILED')
    return {'protocol': PROBE_PROTOCOL, 'scope': 'SYNTHETIC_ONLY',
            'entries': len(catalog), 'rows': result['rows'], 'sum': result['sum'],
            'selected_sha256': hashlib.sha256(selected).hexdigest(),
            'period_gate': 'PASS'}


def synthetic_probe_checkpoint(path):
    # Local synthetic receipt only; never use a registered market archive.
    expected = synthetic_zip_probe()
    payload = json.dumps(expected, sort_keys=True).encode('utf-8')
    atomic(path, payload)
    with path.open('rb') as f:
        actual = f.read(4097)
    if actual != payload:
        raise ValueError('PROBE_CHECKPOINT_MISMATCH')
    return expected


PARQUET_VERSION = '26.0.1'
PARQUET_WORKER = r'''
import io, zipfile, json
from datetime import date
import pyarrow as pa
import pyarrow.parquet as pq

assert pa.__version__ == '26.0.1'

def parquet_bytes(days, values):
    b = io.BytesIO()
    pq.write_table(pa.table({'date': pa.array(days, type=pa.date32()),
                            'value': pa.array(values, type=pa.int64())}), b)
    return b.getvalue()

def select(archive, name):
    with zipfile.ZipFile(io.BytesIO(archive), 'r') as z:
        entries = z.infolist()
        assert len(entries) == 2
        assert len({e.filename for e in entries}) == 2
        entry = z.getinfo(name)
        assert entry.file_size <= 512 * 1024
        assert entry.extract_version >= 45
        with z.open(entry) as stream:
            raw = stream.read(512 * 1024 + 1)
        assert len(raw) == entry.file_size
    # Avoid dataset scanner background threads in this bounded worker.
    with pq.ParquetFile(io.BytesIO(raw), pre_buffer=False) as parquet:
        table = parquet.read(use_threads=False)
    assert table.schema.names == ['date', 'value']
    assert table.schema.field('date').type == pa.date32()
    assert table.schema.field('value').type == pa.int64()
    assert 0 < table.num_rows <= 4096
    days = table['date'].to_pylist()
    if not all(d is not None and date(2000, 1, 1) <= d < date(2026, 1, 1) for d in days):
        raise ValueError('PERIOD_LOCKED')
    values = table['value'].to_pylist()
    assert all(v is not None for v in values)
    return (len(values), sum(values))

def archive(days, values):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', allowZip64=True, compression=zipfile.ZIP_STORED) as z:
        with z.open('synthetic/selected.parquet', 'w', force_zip64=True) as f:
            f.write(parquet_bytes(days, values))
        z.writestr('synthetic/unused.parquet', b'not parquet')
    return b.getvalue()

assert select(archive([date(2025, 1, 2), date(2025, 12, 31)], [3, 7]),
              'synthetic/selected.parquet') == (2, 10)
try:
    select(archive([date(2025, 12, 31), date(2026, 1, 1)], [3, 7]),
           'synthetic/selected.parquet')
except ValueError as e:
    assert str(e) == 'PERIOD_LOCKED'
else:
    raise RuntimeError('PERIOD_GATE_FAILED')
print(json.dumps({'scope': 'SYNTHETIC_ONLY', 'version': pa.__version__,
                  'rows': 2, 'sum': 10, 'zip64_member': True, 'period_gate': 'PASS'}))
'''


def parquet_env():
    # No inherited GitHub credentials, Python injection, or pip index overrides.
    allowed = {'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'COMSPEC', 'TEMP', 'TMP',
               'TMPDIR', 'PATH', 'PATHEXT', 'HOME', 'USERPROFILE', 'LOCALAPPDATA',
               'APPDATA', 'LANG', 'LC_ALL', 'PROGRAMDATA'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env['PIP_CONFIG_FILE'] = os.devnull
    return env


def parquet_command(executable, args, cwd, timeout, capture=False):
    completed = subprocess.run([str(executable), '-I', *args], cwd=str(cwd),
                               env=parquet_env(), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=timeout, check=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return completed.stdout if capture else None


def parquet_runtime(parent, install):
    parent = local_folder(str(parent))
    target = parent / 'ctl_pyarrow_26_0_1'
    marker = target / 'ctl-owned.txt'
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not target.exists():
        if not install:
            raise ValueError('PARQUET_NOT_INSTALLED')
        target.mkdir()
        marker.write_bytes(b'CTL_PYARROW_26_0_1\n')
    local_folder(str(target))
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size != len(b'CTL_PYARROW_26_0_1\n'):
        raise ValueError('PARQUET_UNOWNED_ENV')
    if marker.read_bytes() != b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    if install:
        base = Path(sys.executable)
        if base.name.lower() == 'pythonw.exe':
            base = base.with_name('python.exe')
        if not base.is_file():
            raise ValueError('PARQUET_PYTHON_MISSING')
        if not python.is_file():
            parquet_command(base, ['-m', 'venv', '--copies', str(target)], parent, 120)
        parquet_command(python, ['-m', 'pip', '--isolated', '--disable-pip-version-check',
                        'install', '--index-url', 'https://pypi.org/simple',
                        '--only-binary=:all:', '--no-input', '--no-cache-dir',
                        'pyarrow==' + PARQUET_VERSION], parent, 600)
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    raw = parquet_command(python, ['-c', PARQUET_WORKER], parent, 120, capture=True)
    expected = {'scope': 'SYNTHETIC_ONLY', 'version': PARQUET_VERSION, 'rows': 2,
                'sum': 10, 'zip64_member': True, 'period_gate': 'PASS'}
    if len(raw) > 4096 or json.loads(raw) != expected:
        raise ValueError('PARQUET_BAD_RECEIPT')
    receipt = parent / 'synthetic_parquet_probe.local.json'
    payload = json.dumps(expected, sort_keys=True).encode('utf-8')
    atomic(receipt, payload)
    with receipt.open('rb') as f:
        if f.read(4097) != payload:
            raise ValueError('PARQUET_RECEIPT_MISMATCH')
    return expected


# Real ZIP catalog: metadata only, no member/local-header reads.
CATALOG_MAX_BYTES = 128 * 1024**3
CATALOG_MAX_DIRECTORY = 32 * 1024**2
CATALOG_MAX_ENTRIES = 50000
CATALOG_MAX_TOTAL_ENTRIES = 100000
CATALOG_MAX_RECEIPT = 16 * 1024**2


def catalog_bounds(f):
    f.seek(0, 2)
    size = f.tell()
    if not 22 <= size <= CATALOG_MAX_BYTES:
        raise ValueError('CATALOG_SIZE')
    f.seek(size - 22)
    end = f.read(22)
    sig, disk, cd_disk, n_disk, n, cd_size, cd_offset, comment = struct.unpack('<4s4H2IH', end)
    if sig != b'PK\x05\x06' or comment or disk or cd_disk:
        raise ValueError('CATALOG_END_UNSUPPORTED')
    end_offset = size - 22
    zip64 = n == 0xffff or n_disk == 0xffff or cd_size == 0xffffffff or cd_offset == 0xffffffff
    # In an ordinary ZIP, the declared directory must end exactly at EOCD.
    # In a ZIP64 archive the locator is at a fixed offset before EOCD.
    if zip64 or cd_offset + cd_size != end_offset:
        if size < 98:
            raise ValueError('CATALOG_ZIP64')
        f.seek(end_offset - 20)
        locator = f.read(20)
        sig, disk, record, disks = struct.unpack('<4sIQI', locator)
        if sig != b'PK\x06\x07' or disk or disks != 1 or record != end_offset - 76:
            raise ValueError('CATALOG_ZIP64')
        f.seek(record)
        sig, length, made, needed, disk, cd_disk, nd, count, length_cd, offset_cd = struct.unpack('<4sQ2H2I4Q', f.read(56))
        if sig != b'PK\x06\x06' or length != 44 or disk or cd_disk or nd != count:
            raise ValueError('CATALOG_ZIP64')
        for old, new, sentinel in ((n_disk, nd, 0xffff), (n, count, 0xffff),
                                    (cd_size, length_cd, 0xffffffff), (cd_offset, offset_cd, 0xffffffff)):
            if old != sentinel and old != new:
                raise ValueError('CATALOG_ZIP64')
        n, n_disk, cd_size, cd_offset = count, nd, length_cd, offset_cd
        end_offset = record
        zip64 = True
    if n != n_disk or not 1 <= n <= CATALOG_MAX_ENTRIES or not 46*n <= cd_size <= CATALOG_MAX_DIRECTORY:
        raise ValueError('CATALOG_DIRECTORY_LIMIT')
    if cd_offset + cd_size != end_offset:
        raise ValueError('CATALOG_DIRECTORY_OFFSET')
    return size, cd_offset, n, zip64


class CatalogView:
    """Seekable view of the original file: refuse any read outside the central directory/tail."""
    def __init__(self, file, lower, upper):
        self.file, self.lower, self.upper = file, lower, upper

    def seek(self, offset, whence=0):
        return self.file.seek(offset, whence)

    def tell(self):
        return self.file.tell()

    def read(self, count=-1):
        pos = self.tell()
        if count == -1:
            count = self.upper - pos
        if pos < self.lower or count < 0 or pos + count > self.upper:
            raise ValueError('CATALOG_PAYLOAD_READ_REFUSED')
        return self.file.read(count)

    def seekable(self):
        return True


def catalog_file(value):
    path = local_zip(value)
    before = path.stat()
    with path.open('rb') as f:
        opened = os.fstat(f.fileno())
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if identity(before) != identity(opened):
            raise ValueError('CATALOG_CHANGED')
        size, start, count, is64 = catalog_bounds(f)
        if size != opened.st_size:
            raise ValueError('CATALOG_CHANGED')
        # ZipFile constructor only, never open/read/extract a member.
        with zipfile.ZipFile(CatalogView(f, start, size), 'r') as z:
            if z.start_dir != start or len(z.infolist()) != count:
                raise ValueError('CATALOG_COUNT')
            seen = set()
            candidates = []
            locked = 0
            other = 0
            for item in z.infolist():
                name = item.filename
                parts = name.rstrip('/').split('/')
                if (not name or len(name) > 1024 or '\\' in name or
                        any(not p or p in ('.', '..') or ':' in p for p in parts) or
                        any(ord(c) < 32 for c in name) or item.orig_filename != name):
                    raise ValueError('CATALOG_UNSAFE_NAME')
                key = name.rstrip('/').casefold()
                if key in seen:
                    raise ValueError('CATALOG_DUPLICATE')
                seen.add(key)
                mode = (item.external_attr >> 16) & 0xffff
                if (item.flag_bits & 1 or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or item.header_offset < 0 or item.header_offset >= start
                        or item.compress_size < 0 or item.compress_size > start - item.header_offset):
                    raise ValueError('CATALOG_UNSUPPORTED_ENTRY')
                if re.search(r'2026|holdout|封印', name, re.I):
                    locked += 1
                    continue
                if item.is_dir() or not name.lower().endswith('.parquet'):
                    other += 1
                    continue
                # A filename or size never authorizes research access.
                candidates.append({'member': name, 'size': item.file_size,
                                   'compressed': item.compress_size, 'crc32': item.CRC,
                                   'access': 'LOCKED_UNVERIFIED_PERIOD'})
        if identity(os.fstat(f.fileno())) != identity(opened) or identity(path.stat()) != identity(opened):
            raise ValueError('CATALOG_CHANGED')
    return {'archive': str(path), 'size': size, 'mtime_ns': opened.st_mtime_ns,
            'zip64_directory': is64, 'entries': count, 'locked_names': locked,
            'other': other, 'parquet_candidates': candidates}


def catalog_registered(parent):
    parent = local_folder(str(parent))
    config = read_folders(parent / 'research_folders.local.json')
    paths = zip_paths(config.get('market_zips', []))
    if not paths:
        raise ValueError('CATALOG_NO_ZIP')
    results = []
    total = 0
    for path in paths:
        result = catalog_file(path)
        total += result['entries']
        if total > CATALOG_MAX_TOTAL_ENTRIES:
            raise ValueError('CATALOG_TOTAL_LIMIT')
        results.append(result)
    receipt = {'schema': 1, 'scope': 'LOCAL_METADATA_ONLY', 'member_reads': 0,
               'research_access': 'LOCKED', 'archives': results}
    raw = json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(raw) > CATALOG_MAX_RECEIPT:
        raise ValueError('CATALOG_RECEIPT_LIMIT')
    dest = parent / 'market_zip_catalog.local.json'
    atomic(dest, raw)
    with dest.open('rb') as f:
        if f.read(CATALOG_MAX_RECEIPT + 1) != raw:
            raise ValueError('CATALOG_RECEIPT_MISMATCH')
    return len(results), total, sum(len(a['parquet_candidates']) for a in results)


SELECTION_MAX = 128


def load_market_candidates(parent):
    parent = local_folder(str(parent))
    paths = zip_paths(read_folders(parent / 'research_folders.local.json').get('market_zips', []))
    with (parent / 'market_zip_catalog.local.json').open('rb') as f:
        raw = f.read(CATALOG_MAX_RECEIPT + 1)
    if len(raw) > CATALOG_MAX_RECEIPT:
        raise ValueError('SELECTION_CATALOG_LIMIT')
    catalog = json.loads(raw)
    if (type(catalog) is not dict or catalog.get('schema') != 1 or
            catalog.get('scope') != 'LOCAL_METADATA_ONLY' or catalog.get('member_reads') != 0 or
            catalog.get('research_access') != 'LOCKED' or type(catalog.get('archives')) is not list):
        raise ValueError('SELECTION_CATALOG_INVALID')
    archives = catalog['archives']
    if not paths or [a['archive'] for a in archives] != paths:
        raise ValueError('SELECTION_CATALOG_STALE')
    rows = []
    seen = set()
    for idx, a in enumerate(archives):
        info = local_zip(a['archive']).stat()
        if info.st_size != a['size'] or info.st_mtime_ns != a['mtime_ns']:
            raise ValueError('SELECTION_CATALOG_STALE')
        candidates = a['parquet_candidates']
        if type(candidates) is not list or len(candidates) > CATALOG_MAX_ENTRIES:
            raise ValueError('SELECTION_CATALOG_INVALID')
        for entry in candidates:
            name = entry['member']
            if (type(name) is not str or not name.lower().endswith('.parquet') or len(name) > 1024 or
                    '\\' in name or any(p in ('', '.', '..') or ':' in p for p in name.split('/')) or
                    any(ord(c) < 32 for c in name) or re.search(r'2026|holdout|封印', name, re.I) or
                    entry['access'] != 'LOCKED_UNVERIFIED_PERIOD' or type(entry['size']) is not int or
                    entry['size'] < 0):
                raise ValueError('SELECTION_CATALOG_INVALID')
            key = (idx, name.casefold())
            if key in seen or len(rows) >= CATALOG_MAX_TOTAL_ENTRIES:
                raise ValueError('SELECTION_CATALOG_INVALID')
            seen.add(key)
            rows.append({'archive_index': idx, 'member': name, 'size': entry['size']})
    return hashlib.sha256(raw).hexdigest(), rows


def save_market_selection(parent, catalog_hash, selected):
    current_hash, rows = load_market_candidates(parent)
    if current_hash != catalog_hash:
        raise ValueError('SELECTION_CATALOG_STALE')
    if not 1 <= len(selected) <= SELECTION_MAX:
        raise ValueError('SELECTION_LIMIT')
    keys = [(r['archive_index'], r['member']) for r in selected]
    current = {(r['archive_index'], r['member']): r for r in rows}
    if len(set(keys)) != len(keys) or any(k not in current for k in keys):
        raise ValueError('SELECTION_INVALID')
    receipt = {'schema': 1, 'catalog_sha256': current_hash,
               'scope': 'LOCAL_SELECTION_ONLY', 'research_access': 'LOCKED',
               'member_reads': 0, 'selected': [current[k] for k in keys]}
    raw = json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode('utf-8')
    dest = parent / 'market_selection.local.json'
    atomic(dest, raw)
    with dest.open('rb') as f:
        if f.read(len(raw) + 1) != raw:
            raise ValueError('SELECTION_RECEIPT_MISMATCH')
    return len(keys)


def auto_market_batch(rows, mode, count, seed, batch_index):
    """Metadata-only selection, reproducible across input order and Python versions."""
    if mode not in ('seeded', 'sequential') or type(count) is not int or not 1 <= count <= SELECTION_MAX:
        raise ValueError('AUTO_SELECTION_POLICY')
    if type(seed) is not int or not 0 <= seed < 2**64 or type(batch_index) is not int or batch_index < 0:
        raise ValueError('AUTO_SELECTION_RANGE')
    if not rows or len(rows) > CATALOG_MAX_TOTAL_ENTRIES:
        raise ValueError('AUTO_SELECTION_EMPTY')
    keys = [(r['archive_index'], r['member']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('AUTO_SELECTION_DUPLICATE')
    def key(r):
        return (r['archive_index'], r['member'])
    def rank(r):
        encoded = json.dumps([seed, *key(r)], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return (hashlib.sha256(encoded).digest(), key(r))
    order = sorted(rows, key=rank if mode == 'seeded' else key)
    start = batch_index * count
    if start >= len(order):
        raise ValueError('AUTO_SELECTION_END')
    selected = order[start:start+count]
    plan = {'algorithm': 'sha256-rank-v1' if mode == 'seeded' else 'archive-member-order-v1',
            'mode': mode, 'seed': seed if mode == 'seeded' else 0,
            'batch_size': count, 'batch_index': batch_index,
            'universe_size': len(order), 'selected_count': len(selected),
            'next_batch': batch_index+1 if start+count < len(order) else None,
            'reason': 'PRECOMMITTED_METADATA_SAMPLE' if mode == 'seeded' else 'ORDERED_METADATA_COVERAGE'}
    return selected, plan


def save_auto_market_batch(parent, catalog_hash, mode, count, seed, batch_index):
    current_hash, rows = load_market_candidates(parent)
    if current_hash != catalog_hash:
        raise ValueError('SELECTION_CATALOG_STALE')
    selected, plan = auto_market_batch(rows, mode, count, seed, batch_index)
    receipt = {'schema': 1, 'catalog_sha256': current_hash,
               'scope': 'LOCAL_SELECTION_ONLY', 'research_access': 'LOCKED',
               'member_reads': 0, 'selected': selected, 'selection_plan': plan}
    raw = json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode('utf-8')
    dest = parent / 'market_auto_selection.local.json'
    atomic(dest, raw)
    with dest.open('rb') as f:
        if f.read(len(raw)+1) != raw:
            raise ValueError('SELECTION_RECEIPT_MISMATCH')
    return plan


PLAN_FILE = 'market_research_plan.local.json'
PLAN_LIMIT = 8192


def plan_read(parent):
    digest, rows = load_market_candidates(parent)
    with (parent / PLAN_FILE).open('rb') as f:
        raw = f.read(PLAN_LIMIT+1)
    if len(raw) > PLAN_LIMIT:
        raise ValueError('PLAN_LIMIT')
    p = json.loads(raw)
    if type(p) is not dict or p.get('schema') != 1 or p.get('scope') != 'METADATA_PLANNING_ONLY' or p.get('research_access') != 'LOCKED' or p.get('member_reads') != 0:
        raise ValueError('PLAN_INVALID')
    if p.get('catalog_sha256') != digest or p.get('universe_size') != len(rows):
        raise ValueError('PLAN_STALE')
    mode, count, seed = p['mode'], p['batch_size'], p['seed']
    _, expected = auto_market_batch(rows, mode, count, seed, 0)
    total = (len(rows)+count-1)//count
    next_batch = p['next_batch']
    if type(next_batch) is not int or not 0 <= next_batch <= total or p['total_batches'] != total or p['algorithm'] != expected['algorithm'] or p['reason'] != expected['reason']:
        raise ValueError('PLAN_INVALID')
    if p['prepared_count'] != min(next_batch*count,len(rows)) or p['status'] != ('COMPLETE' if next_batch == total else 'READY'):
        raise ValueError('PLAN_INVALID')
    if p.get('executed_count') != 0:
        raise ValueError('PLAN_INVALID')
    return p


def plan_write(parent, p):
    raw=json.dumps(p, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(raw) > PLAN_LIMIT:
        raise ValueError('PLAN_LIMIT')
    dest=parent / PLAN_FILE
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(PLAN_LIMIT+1) != raw:
            raise ValueError('PLAN_SAVE_FAILED')


def plan_create(parent, digest, mode, count, seed):
    current,rows=load_market_candidates(parent)
    if current != digest:
        raise ValueError('PLAN_STALE')
    if (parent / PLAN_FILE).exists():
        raise ValueError('PLAN_EXISTS')
    _,sel=auto_market_batch(rows,mode,count,seed,0)
    p={'schema':1,'scope':'METADATA_PLANNING_ONLY','research_access':'LOCKED',
       'member_reads':0,'catalog_sha256':current,'universe_size':len(rows),
       'mode':mode,'batch_size':count,'seed':sel['seed'],'algorithm':sel['algorithm'],
       'reason':sel['reason'],'total_batches':(len(rows)+count-1)//count,
       'next_batch':0,'prepared_count':0,'executed_count':0,'status':'READY'}
    plan_write(parent,p)
    return plan_read(parent)


def plan_step(parent):
    p=plan_read(parent)
    if p['status']=='COMPLETE':
        return p
    # Persist candidate receipt first. If interrupted before cursor commit, retrying
    # the same batch recreates identical receipt, not a second execution.
    result=save_auto_market_batch(parent,p['catalog_sha256'],p['mode'],
                                  p['batch_size'],p['seed'],p['next_batch'])
    p['next_batch']+=1
    p['prepared_count']+=result['selected_count']
    p['status']='COMPLETE' if p['next_batch']==p['total_batches'] else 'READY'
    plan_write(parent,p)
    return plan_read(parent)


OHLCV_WORKER = r'''
import io, json, zipfile, time
from datetime import datetime, timezone, timedelta
import pyarrow as pa
import pyarrow.parquet as pq
from collections import Counter

def audit(table):
    assert table.schema.names == ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    assert table.schema.field('timestamp').type == pa.timestamp('us', tz='UTC')
    assert all(table.schema.field(n).type == pa.int64() for n in ('open','high','low','close','volume'))
    assert 0 < table.num_rows <= 4096
    # Convert UTC microseconds explicitly; avoid OS timezone database dependency.
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ticks = table['timestamp'].cast(pa.int64()).to_pylist()
    rows = table.drop(['timestamp']).to_pylist()
    for row, tick in zip(rows, ticks):
        row['timestamp'] = None if tick is None else epoch + timedelta(microseconds=tick)
    # Artificial data only: never inspect a real mixed-period member.
    if any(r['timestamp'] is None or r['timestamp'].year >= 2026 or r['timestamp'].year < 2000 for r in rows):
        raise ValueError('PERIOD_LOCKED')
    counts = Counter()
    seen = set()
    prev = None
    for row in rows:
        t = row['timestamp']
        if t in seen:
            counts['duplicates'] += 1
        seen.add(t)
        if prev is not None and t < prev:
            counts['out_of_order'] += 1
        # Gaps within the same UTC day only; not a trading-session calendar.
        if prev is not None and t.date() == prev.date() and t > prev:
            delta = int((t-prev).total_seconds())
            if delta > 60:
                counts['gap_minutes'] += delta // 60 - 1
        prev = t
        if t.second or t.microsecond:
            counts['off_minute'] += 1
        o,h,l,c,v = (row[k] for k in ('open','high','low','close','volume'))
        if None in (o,h,l,c,v):
            counts['null_rows'] += 1
        elif min(o,h,l,c) <= 0 or h < max(o,l,c) or l > min(o,h,c) or v < 0:
            counts['invalid_ohlcv'] += 1
    return {k: counts[k] for k in ('duplicates','out_of_order','gap_minutes','off_minute','null_rows','invalid_ohlcv')}

def make(times, values):
    table = pa.table({'timestamp':pa.array(times, type=pa.timestamp('us', tz='UTC')),
                      **{k:pa.array([r[i] for r in values], type=pa.int64()) for i,k in enumerate(('open','high','low','close','volume'))}})
    b = io.BytesIO()
    pq.write_table(table,b)
    return b.getvalue()

def fixture(times, values):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:
        z.writestr('synthetic/one.parquet',make(times,values))
        z.writestr('synthetic/unused.parquet',b'not parquet')
    return b.getvalue()

def selected(archive):
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        item=z.getinfo('synthetic/one.parquet')
        assert item.file_size <= 512*1024
        with z.open(item) as f:
            raw=f.read(512*1024+1)
        assert len(raw)==item.file_size
    with pq.ParquetFile(io.BytesIO(raw),pre_buffer=False) as p:
        return audit(p.read(use_threads=False))

def t(m,sec=0):
    return datetime(2025,1,2,14,m,sec,tzinfo=timezone.utc)
valid=(10,12,9,11,3)
start=time.perf_counter_ns()
result=selected(fixture([t(0),t(1),t(1),t(4),t(3),t(5,1)],
                        [valid,valid,valid,(10,8,9,11,3),valid,(10,12,None,11,3)]))
assert result=={'duplicates':1,'out_of_order':1,'gap_minutes':3,'off_minute':1,'null_rows':1,'invalid_ohlcv':1},result
assert selected(fixture([t(0),t(1)],[valid,valid]))==dict.fromkeys(result,0)
try:
    selected(fixture([t(0),datetime(2026,1,1,tzinfo=timezone.utc)],[valid,valid]))
except ValueError as exc:
    assert str(exc)=='PERIOD_LOCKED'
else:
    raise RuntimeError('PERIOD_GATE_FAILED')
print(json.dumps({'scope':'SYNTHETIC_ONLY','audit':result,'period_gate':'PASS',
                  'elapsed_ms':(time.perf_counter_ns()-start)//1000000,
                  'arrow_allocated_bytes_at_end':pa.total_allocated_bytes()}))
'''


def synthetic_ohlcv_checkpoint(parent):
    parent = local_folder(str(parent))
    target = parent / 'ctl_pyarrow_26_0_1'
    local_folder(str(target))
    marker = target / 'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size != len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes() != b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    raw = parquet_command(python, ['-c', OHLCV_WORKER], parent, 120, capture=True)
    if len(raw) > 4096:
        raise ValueError('OHLCV_RECEIPT_LIMIT')
    receipt = json.loads(raw)
    expected = {'duplicates':1,'out_of_order':1,'gap_minutes':3,'off_minute':1,'null_rows':1,'invalid_ohlcv':1}
    if (receipt.get('scope') != 'SYNTHETIC_ONLY' or receipt.get('period_gate') != 'PASS' or receipt.get('audit') != expected):
        raise ValueError('OHLCV_RECEIPT_INVALID')
    dest = parent / 'synthetic_ohlcv_probe.local.json'
    atomic(dest, raw)
    with dest.open('rb') as f:
        if f.read(4097) != raw:
            raise ValueError('OHLCV_RECEIPT_MISMATCH')
    return receipt


SYNTH_RUN_FILE = 'synthetic_research_run.local.json'
SYNTH_RUN_TASKS = ('zip_access', 'ohlcv_audit', 'aggregation')
SYNTH_RUN_PROTOCOL = 'synthetic-research-execution-v1'
SYNTH_RUN_LIMIT = 16384


def synthetic_aggregation():
    # Fixed invented observations: two independent sessions, no imputation.
    sessions = ((1,2,3,4,5,6), (7,8,9,10))
    totals = []
    dropped = 0
    for session in sessions:
        for start in range(0,len(session),3):
            window = session[start:start+3]
            if len(window) != 3:
                dropped += len(window)
                continue
            totals.append(sum(window))
    if totals != [6,15,24] or dropped != 1:
        raise ValueError('SYNTH_AGGREGATION_FAILED')
    return {'window':3,'windows':len(totals),'sum':sum(totals),'discarded_incomplete':dropped}


def synthetic_run_expected():
    return {'zip_access':{'rows':3,'sum':10,'period_gate':'PASS'},
            'ohlcv_audit':{'duplicates':1,'out_of_order':1,'gap_minutes':3,'off_minute':1,'null_rows':1,'invalid_ohlcv':1,'period_gate':'PASS'},
            'aggregation':{'window':3,'windows':3,'sum':45,'discarded_incomplete':1}}


def synthetic_run_read(parent):
    parent=local_folder(str(parent))
    dest=parent / SYNTH_RUN_FILE
    if not dest.exists():
        return {'schema':1,'protocol':SYNTH_RUN_PROTOCOL,'scope':'SYNTHETIC_ONLY',
                'market_member_reads':0,'results':{},'status':'READY'}
    with dest.open('rb') as f:
        raw=f.read(SYNTH_RUN_LIMIT+1)
    if len(raw)>SYNTH_RUN_LIMIT:
        raise ValueError('SYNTH_RUN_LIMIT')
    state=json.loads(raw)
    if (type(state) is not dict or state.get('schema')!=1 or state.get('protocol')!=SYNTH_RUN_PROTOCOL or
            state.get('scope')!='SYNTHETIC_ONLY' or state.get('market_member_reads')!=0 or type(state.get('results')) is not dict):
        raise ValueError('SYNTH_RUN_INVALID')
    results=state['results']
    expected=synthetic_run_expected()
    if set(results)!=set(SYNTH_RUN_TASKS[:len(results)]) or any(results[k]!=expected[k] for k in results):
        raise ValueError('SYNTH_RUN_INVALID')
    if state.get('status')!=('COMPLETE' if len(results)==len(SYNTH_RUN_TASKS) else 'READY'):
        raise ValueError('SYNTH_RUN_INVALID')
    return state


def synthetic_run_write(parent,state):
    raw=json.dumps(state,sort_keys=True).encode('utf-8')
    if len(raw)>SYNTH_RUN_LIMIT:
        raise ValueError('SYNTH_RUN_LIMIT')
    dest=parent / SYNTH_RUN_FILE
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(SYNTH_RUN_LIMIT+1)!=raw:
            raise ValueError('SYNTH_RUN_SAVE_FAILED')


def synthetic_run_execute(parent, notify=lambda *_: None):
    parent=local_folder(str(parent))
    state=synthetic_run_read(parent)
    expected=synthetic_run_expected()
    for name in SYNTH_RUN_TASKS:
        if name in state['results']:
            continue
        if name=='zip_access':
            receipt=synthetic_probe_checkpoint(parent / 'synthetic_zip_probe.local.json')
            result={k:receipt[k] for k in ('rows','sum','period_gate')}
        elif name=='ohlcv_audit':
            receipt=synthetic_ohlcv_checkpoint(parent)
            result={**receipt['audit'],'period_gate':receipt['period_gate']}
        else:
            result=synthetic_aggregation()
        if result!=expected[name]:
            raise ValueError('SYNTH_RUN_RESULT_MISMATCH')
        state['results'][name]=result
        state['status']='COMPLETE' if len(state['results'])==len(SYNTH_RUN_TASKS) else 'READY'
        synthetic_run_write(parent,state)
        state=synthetic_run_read(parent)
        notify(len(state['results']),len(SYNTH_RUN_TASKS))
    return state


# Existing research index schema only. Never query application tables.
INDEX_NAME = 'hf_light_index.sqlite'
INDEX_MAX_BYTES = 64*1024**2
INDEX_MAX_OBJECTS = 64
INDEX_RECEIPT_LIMIT = 32768


def index_file_metadata(value):
    path=Path(value)
    if path.name.lower()!=INDEX_NAME:
        raise ValueError('INDEX_NAME_REQUIRED')
    local_folder(str(path.parent))
    info=path.lstat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
            getattr(info,'st_file_attributes',0)&0x400 or not 100<=info.st_size<=INDEX_MAX_BYTES):
        raise ValueError('INDEX_FILE_REFUSED')
    # An immutable SQLite reader must not silently ignore a live journal/WAL.
    for suffix in ('-wal','-shm','-journal'):
        try:
            Path(str(path)+suffix).lstat()
        except FileNotFoundError:
            continue
        raise ValueError('INDEX_SIDECAR_REFUSED')
    return path,(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)


def index_schema_authorizer(action, arg1, arg2, database, source):
    if action==sqlite3.SQLITE_SELECT and source is None:
        return sqlite3.SQLITE_OK
    if (action==sqlite3.SQLITE_READ and arg1 in ('sqlite_master','sqlite_schema')
            and arg2 in ('name','type') and database=='main' and source is None):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def existing_index_probe(parent,value):
    parent=local_folder(str(parent))
    path,before=index_file_metadata(value)
    connection=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.set_authorizer(index_schema_authorizer)
        rows=connection.execute(
            "SELECT name,type FROM main.sqlite_schema WHERE type IN ('table','view') ORDER BY name LIMIT 65"
        ).fetchall()
    finally:
        connection.close()
    if index_file_metadata(str(path))[1]!=before:
        raise ValueError('INDEX_CHANGED')
    if not 1<=len(rows)<=INDEX_MAX_OBJECTS:
        raise ValueError('INDEX_SCHEMA_LIMIT')
    objects=[]
    for name,kind in rows:
        if (type(name) is not str or not 1<=len(name)<=128 or
                any(ord(c)<32 for c in name) or kind not in ('table','view')):
            raise ValueError('INDEX_SCHEMA_REFUSED')
        # Do not disclose explicitly reserved object names.
        if not re.search(r'2026|holdout|封印',name,re.I):
            objects.append({'name':name,'kind':kind})
    receipt={'schema':1,'scope':'LOCAL_SCHEMA_ONLY','source':str(path),
             'size':before[2],'mtime_ns':before[3],
             'objects':objects,'reserved_objects_omitted':len(rows)-len(objects),
             'application_table_queries':0,'market_member_reads':0,
             'development_period':'UNVERIFIED','research_access':'LOCKED'}
    raw=json.dumps(receipt,ensure_ascii=False,sort_keys=True).encode('utf-8')
    if len(raw)>INDEX_RECEIPT_LIMIT:
        raise ValueError('INDEX_RECEIPT_LIMIT')
    dest=parent/'existing_research_index.local.json'
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(INDEX_RECEIPT_LIMIT+1)!=raw:
            raise ValueError('INDEX_RECEIPT_MISMATCH')
    return receipt


# Schema mapping is advisory, never an authority for data access.
INDEX_MAP_LIMIT=512*1024
INDEX_MAP_TABLES=('symbols','monthly_coverage','calendar','session_quality',
                  'largest_intraday_gaps','shared_gap_candidates','archive_status',
                  'evidence_sources','official_events','outside_session','run_metadata')


def index_column_authorizer(action,arg1,arg2,database,source):
    # Only exact schema operations; no application table reads, virtual table
    # queries, schema SQL text, views, functions, writes or ATTACH.
    if action==sqlite3.SQLITE_PRAGMA and arg1=='table_xinfo' and arg2 in INDEX_MAP_TABLES and database=='main' and source is None:
        return sqlite3.SQLITE_OK
    return index_schema_authorizer(action,arg1,arg2,database,source)


def candidate_filename_symbols(rows):
    # Naming convention observed in the local GUI, not a verified ticker join.
    by_symbol={}
    unrecognized=0
    for row in rows:
        name=row['member']
        match=re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]{0,19})_clean_1min\.parquet',name.rsplit('/',1)[-1])
        if not match:
            unrecognized+=1
            continue
        symbol=match.group(1).upper()
        by_symbol.setdefault(symbol,[]).append({'archive_index':row['archive_index'],'member':name})
    unique={symbol:items[0] for symbol,items in sorted(by_symbol.items()) if len(items)==1}
    ambiguous=sum(len(items) for items in by_symbol.values() if len(items)>1)
    return unique,ambiguous,unrecognized


def index_column_map(parent):
    parent=local_folder(str(parent))
    dest=parent/'existing_research_index.local.json'
    with dest.open('rb') as f:
        raw=f.read(INDEX_RECEIPT_LIMIT+1)
    if len(raw)>INDEX_RECEIPT_LIMIT:
        raise ValueError('INDEX_RECEIPT_LIMIT')
    receipt=json.loads(raw)
    if (type(receipt) is not dict or receipt.get('schema')!=1 or
            receipt.get('scope')!='LOCAL_SCHEMA_ONLY' or receipt.get('research_access')!='LOCKED' or
            receipt.get('application_table_queries')!=0 or receipt.get('market_member_reads')!=0):
        raise ValueError('INDEX_RECEIPT_INVALID')
    path,before=index_file_metadata(receipt['source'])
    if before[2]!=receipt['size'] or before[3]!=receipt['mtime_ns']:
        raise ValueError('INDEX_CHANGED')
    digest,rows=load_market_candidates(parent)
    candidates,ambiguous,unknown=candidate_filename_symbols(rows)
    connection=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
    schemas={}
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.set_authorizer(index_column_authorizer)
        actual=connection.execute("SELECT name,type FROM main.sqlite_schema WHERE type IN ('table','view') ORDER BY name LIMIT 65").fetchall()
        if len(actual)>INDEX_MAX_OBJECTS:
            raise ValueError('INDEX_SCHEMA_LIMIT')
        table_names={name for name,kind in actual if kind=='table'}
        for name in INDEX_MAP_TABLES:
            if name not in table_names:
                continue
            # Names are from the fixed allowlist, not user-controlled SQL.
            columns=connection.execute('PRAGMA main.table_xinfo("'+name+'")').fetchall()
            if not 1<=len(columns)<=128:
                raise ValueError('INDEX_COLUMN_LIMIT')
            safe=[]
            for cid,col,decl,notnull,default,pk,hidden in columns:
                if (type(col) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',col)
                        or type(decl) is not str or len(decl)>80 or any(ord(c)<32 for c in decl)):
                    raise ValueError('INDEX_COLUMN_REFUSED')
                # Never save default expressions or reserved identifiers.
                if re.search(r'2026|holdout|封印',col,re.I):
                    continue
                safe.append({'name':col,'type':decl,'primary_key':int(pk),'hidden':int(hidden)})
            schemas[name]=safe
    finally:
        connection.close()
    if index_file_metadata(str(path))[1]!=before:
        raise ValueError('INDEX_CHANGED')
    current,_=load_market_candidates(parent)
    if current!=digest:
        raise ValueError('SELECTION_CATALOG_STALE')
    # Potential join keys are suggestions only; no SQLite data rows are joined.
    hints={}
    for table,columns in schemas.items():
        names={col['name'].lower():col['name'] for col in columns if col['hidden']==0}
        hints[table]={'symbol':[names[k] for k in ('symbol','ticker') if k in names],
                      'period':[names[k] for k in ('month','date','session','session_date','year','timestamp','ym') if k in names]}
    out={'schema':1,'scope':'LOCAL_COLUMN_MAP_ONLY','index_source':str(path),
         'index_size':before[2],'index_mtime_ns':before[3],'catalog_sha256':digest,
         'columns':schemas,'possible_keys':hints,'filename_candidates':candidates,
         'ambiguous_filename_count':ambiguous,'unrecognized_filename_count':unknown,
         'application_table_queries':0,'market_member_reads':0,
         'matched_index_rows':0,'development_period':'UNVERIFIED','research_access':'LOCKED'}
    payload=json.dumps(out,ensure_ascii=False,sort_keys=True).encode('utf-8')
    if len(payload)>INDEX_MAP_LIMIT:
        raise ValueError('INDEX_MAP_LIMIT')
    dest=parent/'existing_index_column_map.local.json'
    atomic(dest,payload)
    with dest.open('rb') as f:
        if f.read(INDEX_MAP_LIMIT+1)!=payload:
            raise ValueError('INDEX_MAP_SAVE_FAILED')
    return out


# Fixed, retrospective monthly index selection; never opens market members.
QUALITY_MONTHS=tuple(f'{y:04d}-{m:02d}' for y in range(2022,2026) for m in range(1,13) if y!=2022 or m>=3)
QUALITY_COLUMNS={'symbols':('ticker','member','member_bytes','member_crc32'),
                 'monthly_coverage':('ticker','month','observed_regular_minutes','scheduled_minutes_in_observed_span')}
QUALITY_ROW_LIMIT=100000
QUALITY_RECEIPT_LIMIT=1024*1024


def quality_authorizer(action,arg1,arg2,database,source):
    if action==sqlite3.SQLITE_SELECT and source is None:
        return sqlite3.SQLITE_OK
    if action==sqlite3.SQLITE_READ and database=='main' and source is None and arg2 in QUALITY_COLUMNS.get(arg1,()):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def quality_read_index(path):
    # Fixed SQL only; authorizer limits columns, not row predicates.
    # The literal allowlist of month parameters provides the logical boundary.
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        ordinary={r[1] for r in db.execute('PRAGMA main.table_list') if r[0]=='main' and r[2]=='table'}
        if not set(QUALITY_COLUMNS)<=ordinary:
            raise ValueError('QUALITY_SCHEMA')
        for table,needed in QUALITY_COLUMNS.items():
            cols={r[1] for r in db.execute('PRAGMA main.table_xinfo("'+table+'")') if r[6]==0}
            if not set(needed)<=cols:
                raise ValueError('QUALITY_SCHEMA')
        db.set_authorizer(quality_authorizer)
        identities=db.execute('SELECT ticker,member,member_bytes,member_crc32 FROM main.symbols LIMIT 100001').fetchall()
        sql=('SELECT ticker,month,observed_regular_minutes,scheduled_minutes_in_observed_span '
             'FROM main.monthly_coverage WHERE month COLLATE BINARY IN ('+
             ','.join('?' for _ in QUALITY_MONTHS)+') LIMIT 100001')
        monthly=db.execute(sql,QUALITY_MONTHS).fetchall()
        if len(identities)>QUALITY_ROW_LIMIT or len(monthly)>QUALITY_ROW_LIMIT:
            raise ValueError('QUALITY_ROW_LIMIT')
    finally:
        db.close()
    return identities,monthly


def quality_catalog_rows(parent):
    digest,rows=load_market_candidates(parent)
    with (parent/'market_zip_catalog.local.json').open('rb') as f:
        raw=f.read(CATALOG_MAX_RECEIPT+1)
    if len(raw)>CATALOG_MAX_RECEIPT or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('QUALITY_CATALOG_CHANGED')
    catalog=json.loads(raw)
    crcs={}
    for idx,a in enumerate(catalog['archives']):
        for entry in a['parquet_candidates']:
            crc=entry.get('crc32')
            if type(crc) is not int or not 0<=crc<=0xffffffff:
                raise ValueError('QUALITY_CRC')
            crcs[(idx,entry['member'])]=crc
    return digest,[{**row,'crc32':crcs[(row['archive_index'],row['member'])]} for row in rows]


def quality_select(rows,identities,monthly,count,seed,min_months,min_bps):
    if type(min_months) is not int or not 1<=min_months<=len(QUALITY_MONTHS) or type(min_bps) is not int or not 0<=min_bps<=10000:
        raise ValueError('QUALITY_POLICY')
    candidates,ambiguous,unknown=candidate_filename_symbols(rows)
    lookup={(r['archive_index'],r['member']):r for r in rows}
    identity_by={}
    for ticker,member,size,crc in identities:
        if type(ticker) is not str or ticker not in candidates:
            continue
        identity_by.setdefault(ticker,[]).append((member,size,crc))
    verified={}
    for ticker,candidate in candidates.items():
        matches=identity_by.get(ticker,[])
        if len(matches)!=1:
            continue
        member,size,crc=matches[0]
        row=lookup[(candidate['archive_index'],candidate['member'])]
        # CRC representation is explicitly hexadecimal, not guessed decimal.
        if (member==row['member'] and type(size) is int and size==row['size'] and
                type(crc) is str and re.fullmatch(r'(?:0[xX])?[0-9A-Fa-f]{8}',crc) and
                int(crc,16)==row['crc32']):
            verified[ticker]=row
    month_rows={}
    invalid=set()
    for ticker,month,observed,scheduled in monthly:
        if month not in QUALITY_MONTHS:
            raise ValueError('QUALITY_PERIOD_REFUSED')
        if ticker not in verified:
            continue
        key=(ticker,month)
        if (key in month_rows or type(observed) is not int or type(scheduled) is not int or
                not 0<=observed<=scheduled<=100000 or scheduled==0):
            invalid.add(ticker)
            continue
        month_rows[key]=(observed,scheduled)
    totals={}
    for (ticker,month),(observed,scheduled) in month_rows.items():
        x=totals.setdefault(ticker,[0,0,0])
        x[0]+=1
        x[1]+=observed
        x[2]+=scheduled
    eligible=[]
    for ticker,row in verified.items():
        months,observed,scheduled=totals.get(ticker,[0,0,0])
        if ticker not in invalid and months>=min_months and scheduled and observed*10000>=min_bps*scheduled:
            eligible.append({**row,'ticker':ticker,'months':months,'observed':observed,'scheduled':scheduled})
    selected=[]
    plan=None
    if eligible:
        selected,plan=auto_market_batch(eligible,'seeded',count,seed,0)
    elif type(count) is not int or not 1<=count<=SELECTION_MAX or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('QUALITY_POLICY')
    return {'candidate_count':len(candidates),'ambiguous_count':ambiguous,'unrecognized_count':unknown,
            'metadata_matched_count':len(verified),'invalid_monthly_count':len(invalid),
            'eligible_count':len(eligible),'selected':selected,'selection_plan':plan}


def quality_index_run(parent,count,seed,min_months,min_bps,persist=True):
    parent=local_folder(str(parent))
    with (parent/'existing_index_column_map.local.json').open('rb') as f:
        raw=f.read(INDEX_MAP_LIMIT+1)
    if len(raw)>INDEX_MAP_LIMIT:
        raise ValueError('QUALITY_MAP_LIMIT')
    mapping=json.loads(raw)
    if (mapping.get('schema')!=1 or mapping.get('scope')!='LOCAL_COLUMN_MAP_ONLY' or
            mapping.get('research_access')!='LOCKED' or mapping.get('application_table_queries')!=0):
        raise ValueError('QUALITY_MAP_INVALID')
    path,before=index_file_metadata(mapping['index_source'])
    digest,rows=quality_catalog_rows(parent)
    if before[2]!=mapping['index_size'] or before[3]!=mapping['index_mtime_ns'] or digest!=mapping['catalog_sha256']:
        raise ValueError('QUALITY_STALE')
    identities,monthly=quality_read_index(path)
    result=quality_select(rows,identities,monthly,count,seed,min_months,min_bps)
    if index_file_metadata(str(path))[1]!=before or load_market_candidates(parent)[0]!=digest:
        raise ValueError('QUALITY_STALE')
    receipt={'schema':1,'scope':'LOCAL_RETROSPECTIVE_MONTHLY_SELECTION',
             'catalog_sha256':digest,'index_map_sha256':hashlib.sha256(raw).hexdigest(),
             'month_start':QUALITY_MONTHS[0],'month_end':QUALITY_MONTHS[-1],
             'min_months':min_months,'min_coverage_bps':min_bps,'requested_count':count,'seed':seed,
             'market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED',
             'physical_period_isolation':'UNVERIFIED','research_access':'LOCKED',**result}
    payload=json.dumps(receipt,ensure_ascii=False,sort_keys=True).encode('utf-8')
    if len(payload)>QUALITY_RECEIPT_LIMIT:
        raise ValueError('QUALITY_RECEIPT_LIMIT')
    if not persist:
        return receipt
    dest=parent/'market_monthly_quality_selection.local.json'
    atomic(dest,payload)
    with dest.open('rb') as f:
        if f.read(QUALITY_RECEIPT_LIMIT+1)!=payload:
            raise ValueError('QUALITY_RECEIPT_MISMATCH')
    return receipt


# Research-engine building block. Integer artificial OHLCV values, explicit
# session-relative offsets. No file readers, calendar inference or real inputs.
RESEARCH_HORIZONS=(1,5,15,30)
HORIZON_RECEIPT='synthetic_horizon_aggregation.local.json'


def aggregate_session_rows(rows,session_minutes,horizon,*,float_prices=False):
    if type(session_minutes) is not int or not 1<=session_minutes<=1440 or type(horizon) is not int or horizon not in RESEARCH_HORIZONS:
        raise ValueError('SESSION_POLICY')
    if type(rows) not in (list,tuple) or len(rows)>session_minutes:
        raise ValueError('SESSION_ROWS')
    by_minute={}
    previous=-1
    for row in rows:
        if (type(row) not in (list,tuple) or len(row)!=6 or type(row[0]) is not int or type(row[5]) is not int or
                (any(type(v) is not float or not math.isfinite(v) for v in row[1:5]) if float_prices else any(type(v) is not int for v in row[1:5]))):
            raise ValueError('SESSION_ROW_SCHEMA')
        minute,o,h,l,c,v=row
        if not previous<minute<session_minutes or min(o,h,l,c)<=0 or h<max(o,l,c) or l>min(o,h,c) or v<0:
            raise ValueError('SESSION_ROW_INVALID')
        previous=minute
        by_minute[minute]=(o,h,l,c,v)
    bars=[]
    missing=0
    tail=session_minutes%horizon
    for start in range(0,session_minutes-tail,horizon):
        window=[by_minute.get(i) for i in range(start,start+horizon)]
        if any(x is None for x in window):
            missing+=1
            continue
        bars.append((start,window[0][0],max(x[1] for x in window),
                     min(x[2] for x in window),window[-1][3],sum(x[4] for x in window)))
    return {'bars':bars,'missing_windows':missing,'tail_minutes':tail,
            'missing_minutes':session_minutes-len(rows)}


def synthetic_horizon_expected():
    return {'1':{'complete':104,'missing_windows':1,'tail_minutes':0},
            '5':{'complete':20,'missing_windows':1,'tail_minutes':0},
            '15':{'complete':6,'missing_windows':1,'tail_minutes':0},
            '30':{'complete':2,'missing_windows':1,'tail_minutes':15}}


def synthetic_horizon_checkpoint(parent):
    parent=local_folder(str(parent))
    # Two independent invented sessions, one missing minute and one short session.
    sessions=((60,[(i,100+i,102+i,99+i,101+i,3) for i in range(60) if i!=7]),
              (45,[(i,20,21,19,20,2) for i in range(45)]))
    summaries={}
    for horizon in RESEARCH_HORIZONS:
        results=[aggregate_session_rows(rows,length,horizon) for length,rows in sessions]
        summaries[str(horizon)]={'complete':sum(len(r['bars']) for r in results),
                                 'missing_windows':sum(r['missing_windows'] for r in results),
                                 'tail_minutes':sum(r['tail_minutes'] for r in results)}
        if horizon==30 and (results[0]['bars']!=[(30,130,161,129,160,90)] or results[1]['bars']!=[(0,20,21,19,20,60)]):
            raise ValueError('HORIZON_OHLCV_MISMATCH')
    if summaries!=synthetic_horizon_expected():
        raise ValueError('HORIZON_WINDOW_MISMATCH')
    for bad in ([(0,10,12,9,11,1),(0,10,12,9,11,1)],
                [(60,10,12,9,11,1)],[(0,10,8,9,11,1)],
                [(0,10,12,9,11,-1)]):
        try:
            aggregate_session_rows(bad,60,5)
        except ValueError:
            pass
        else:
            raise ValueError('HORIZON_REJECTION_FAILED')
    receipt={'schema':1,'scope':'SYNTHETIC_ONLY','protocol':'session-ohlcv-horizons-v1',
             'market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED','results':summaries}
    raw=json.dumps(receipt,sort_keys=True).encode('utf-8')
    dest=parent/HORIZON_RECEIPT
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(16385)!=raw:
            raise ValueError('HORIZON_SAVE_FAILED')
    return receipt


# Explicit calendar adapter: only caller-provided session dates/UTC offset/
# closing minutes. No inference of holidays, DST rules or actual market data.
SESSION_MAP_RECEIPT='synthetic_session_mapping.local.json'
SESSION_EPOCH=date(1970,1,1)
SESSION_FIRST=(date(2000,1,1)-SESSION_EPOCH).days*1440
SESSION_LIMIT=(date(2026,1,1)-SESSION_EPOCH).days*1440


def session_day_base(day):
    if type(day) is not str:
        raise ValueError('SESSION_DATE')
    d=date.fromisoformat(day)
    if d.isoformat()!=day or not 2000<=d.year<=2025:
        raise ValueError('SESSION_PERIOD')
    return (d-SESSION_EPOCH).days*1440


def map_session_rows(schedule,rows,*,float_prices=False):
    # schedule: (ISO session date, explicit UTC offset in minutes, duration).
    # rows: (UTC epoch minute, integer open, high, low, close, volume).
    if type(schedule) not in (list,tuple) or not 1<=len(schedule)<=366:
        raise ValueError('SESSION_SCHEDULE')
    if type(rows) not in (list,tuple) or len(rows)>366*1440:
        raise ValueError('SESSION_INPUT_LIMIT')
    sessions={}
    previous_day=''
    for item in schedule:
        if type(item) not in (list,tuple) or len(item)!=3:
            raise ValueError('SESSION_SCHEDULE')
        day,offset,duration=item
        base=session_day_base(day)
        if day<=previous_day or type(offset) is not int or offset not in (-300,-240) or type(duration) is not int or not 1<=duration<=390:
            raise ValueError('SESSION_SCHEDULE')
        previous_day=day
        start=base+570-offset
        sessions[base//1440]={'date':day,'start':start,'length':duration,'rows':[]}
    previous=-1
    outside=0
    for row in rows:
        if (type(row) not in (tuple,list) or len(row)!=6 or type(row[0]) is not int or type(row[5]) is not int or
                (any(type(v) is not float or not math.isfinite(v) for v in row[1:5]) if float_prices else any(type(v) is not int for v in row[1:5]))):
            raise ValueError('SESSION_INPUT_SCHEMA')
        minute,o,h,l,c,v=row
        if not SESSION_FIRST<=minute<SESSION_LIMIT:
            raise ValueError('SESSION_PERIOD')
        if minute<=previous or min(o,h,l,c)<=0 or h<max(o,l,c) or l>min(o,h,c) or v<0:
            raise ValueError('SESSION_INPUT_INVALID')
        previous=minute
        session=sessions.get(minute//1440)
        if session is None or not session['start']<=minute<session['start']+session['length']:
            outside+=1
            continue
        session['rows'].append((minute-session['start'],o,h,l,c,v))
    return {'sessions':list(sessions.values()),'outside':outside}


def synthetic_session_mapping_checkpoint(parent):
    parent=local_folder(str(parent))
    schedule=[('2025-01-06',-300,390),('2025-07-07',-240,390),('2025-07-08',-240,210)]
    starts=[session_day_base(day)+570-offset for day,offset,_ in schedule]
    valid=(10,12,9,11,2)
    rows=[]
    for start,(_,_,duration) in zip(starts,schedule):
        rows.extend((start+i,*valid) for i in range(-1,duration+1))
    # An invented closed day: the schedule deliberately contains no session.
    rows.append((session_day_base('2025-07-09')+810,*valid))
    result=map_session_rows(schedule,rows)
    if result['outside']!=7 or [s['length'] for s in result['sessions']]!=[390,390,210]:
        raise ValueError('SESSION_MAPPING_COUNT')
    if [s['start']%1440 for s in result['sessions']]!=[870,810,810]:
        raise ValueError('SESSION_MAPPING_OFFSET')
    counts=[]
    for session in result['sessions']:
        n=session['length']
        if len(session['rows'])!=n or session['rows'][0][0]!=0 or session['rows'][-1][0]!=n-1:
            raise ValueError('SESSION_MAPPING_BOUNDARY')
        aggregated=aggregate_session_rows(session['rows'],n,30)
        if aggregated['missing_windows'] or aggregated['tail_minutes']:
            raise ValueError('SESSION_MAPPING_AGGREGATION')
        counts.append(len(aggregated['bars']))
    if counts!=[13,13,7]:
        raise ValueError('SESSION_MAPPING_AGGREGATION')
    try:
        map_session_rows(schedule,[(SESSION_LIMIT,*valid)])
    except ValueError as exc:
        if str(exc)!='SESSION_PERIOD':
            raise
    else:
        raise ValueError('SESSION_MAPPING_GATE')
    receipt={'schema':1,'scope':'SYNTHETIC_ONLY','protocol':'explicit-session-map-v1',
             'market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED',
             'sessions':3,'outside':7,'bars_30m':counts}
    raw=json.dumps(receipt,sort_keys=True).encode('utf-8')
    dest=parent/SESSION_MAP_RECEIPT
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(16385)!=raw:
            raise ValueError('SESSION_MAPPING_SAVE_FAILED')
    return receipt


# Calendar metadata only. The fixed projection excludes market-derived columns.
CALENDAR_COLUMNS=('date','expected_minutes','open_utc','close_utc','utc_offset_hours')
CALENDAR_FIRST='2022-03-07'
CALENDAR_LAST='2025-12-31'
CALENDAR_MAX=1500
CALENDAR_RECEIPT='development_calendar.local.json'


def calendar_authorizer(action,arg1,arg2,database,source):
    if action==sqlite3.SQLITE_SELECT and source is None:
        return sqlite3.SQLITE_OK
    if action==sqlite3.SQLITE_READ and database=='main' and source is None and arg1=='calendar' and arg2 in CALENDAR_COLUMNS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def calendar_query(db):
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA trusted_schema=OFF')
    ordinary={r[1] for r in db.execute('PRAGMA main.table_list') if r[0]=='main' and r[2]=='table'}
    if 'calendar' not in ordinary:
        raise ValueError('CALENDAR_SCHEMA')
    cols={r[1] for r in db.execute('PRAGMA main.table_xinfo("calendar")') if r[6]==0}
    if not set(CALENDAR_COLUMNS)<=cols:
        raise ValueError('CALENDAR_SCHEMA')
    db.set_authorizer(calendar_authorizer)
    rows=db.execute('SELECT date,expected_minutes,open_utc,close_utc,utc_offset_hours '
                    'FROM main.calendar WHERE date COLLATE BINARY BETWEEN ? AND ? '
                    'ORDER BY date COLLATE BINARY LIMIT 1501',(CALENDAR_FIRST,CALENDAR_LAST)).fetchall()
    if not 1<=len(rows)<=CALENDAR_MAX:
        raise ValueError('CALENDAR_ROW_LIMIT')
    return rows


def calendar_clock(value,day):
    # Columns explicitly declare UTC. Accept exact same-day timestamps or
    # clock-only strings, with optional zero seconds and UTC suffix only.
    if type(value) is not str:
        raise ValueError('CALENDAR_CLOCK')
    match=re.fullmatch(r'(?:(\d{4}-\d{2}-\d{2})[ T])?(\d{2}):(\d{2})(?::00(?:\.0{1,6})?)?(?:Z|\+00:00)?',value)
    if not match or match[1] not in (None,day):
        raise ValueError('CALENDAR_CLOCK')
    h,m=int(match[2]),int(match[3])
    if h>23 or m>59:
        raise ValueError('CALENDAR_CLOCK')
    return h*60+m


def calendar_normalize(rows):
    sessions=[]
    previous=''
    if not 1<=len(rows)<=CALENDAR_MAX:
        raise ValueError('CALENDAR_ROW_LIMIT')
    for day,duration,opened,closed,offset in rows:
        session_day_base(day)
        if not CALENDAR_FIRST<=day<=CALENDAR_LAST or day<=previous:
            raise ValueError('CALENDAR_DATE')
        previous=day
        if type(duration) is not int or not 0<=duration<=390:
            raise ValueError('CALENDAR_DURATION')
        if duration==0:
            if opened not in (None,'') or closed not in (None,''):
                raise ValueError('CALENDAR_CLOSED_CLOCK')
            continue
        if type(offset) not in (int,float) or offset not in (-5,-4):
            raise ValueError('CALENDAR_OFFSET')
        start=calendar_clock(opened,day)
        end=calendar_clock(closed,day)
        minutes=int(offset*60)
        if start!=570-minutes or end-start!=duration:
            raise ValueError('CALENDAR_CLOCK_MISMATCH')
        sessions.append([day,minutes,duration])
    if not sessions:
        raise ValueError('CALENDAR_EMPTY')
    return sessions


def calendar_index_checkpoint(parent):
    parent=local_folder(str(parent))
    with (parent/'existing_index_column_map.local.json').open('rb') as f:
        raw=f.read(INDEX_MAP_LIMIT+1)
    if len(raw)>INDEX_MAP_LIMIT:
        raise ValueError('CALENDAR_MAP_LIMIT')
    mapping=json.loads(raw)
    if (type(mapping) is not dict or mapping.get('schema')!=1 or
            mapping.get('scope')!='LOCAL_COLUMN_MAP_ONLY' or mapping.get('research_access')!='LOCKED' or
            mapping.get('market_member_reads')!=0 or mapping.get('application_table_queries')!=0):
        raise ValueError('CALENDAR_MAP_INVALID')
    path,before=index_file_metadata(mapping['index_source'])
    if before[2]!=mapping['index_size'] or before[3]!=mapping['index_mtime_ns']:
        raise ValueError('CALENDAR_STALE')
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=1)
    try:
        sessions=calendar_normalize(calendar_query(db))
    finally:
        db.close()
    if index_file_metadata(str(path))[1]!=before:
        raise ValueError('CALENDAR_STALE')
    receipt={'schema':1,'scope':'LOCAL_CALENDAR_METADATA','protocol':'indexed-session-calendar-v1',
             'index_map_sha256':hashlib.sha256(raw).hexdigest(),'date_start':CALENDAR_FIRST,
             'date_end':CALENDAR_LAST,'sessions':sessions,'market_member_reads':0,
             'calendar_completeness':'UNVERIFIED','physical_period_isolation':'UNVERIFIED',
             'holdout_evaluation':'NOT_PERFORMED','research_access':'LOCKED'}
    payload=json.dumps(receipt,sort_keys=True).encode('utf-8')
    dest=parent/CALENDAR_RECEIPT
    atomic(dest,payload)
    with dest.open('rb') as f:
        if f.read(131073)!=payload:
            raise ValueError('CALENDAR_SAVE_FAILED')
    return receipt


def synthetic_calendar_probe():
    # No external calendar or files. Reserved rows and other columns are
    # deliberately invalid and must not reach the result.
    db=sqlite3.connect(':memory:')
    try:
        db.execute('CREATE TABLE calendar(date TEXT,expected_minutes INTEGER,open_utc TEXT,close_utc TEXT,utc_offset_hours REAL,observed_tickers INTEGER)')
        db.executemany('INSERT INTO calendar VALUES(?,?,?,?,?,?)',[
            ('2025-01-06',390,'2025-01-06T14:30:00+00:00','21:00',-5,999),
            ('2025-07-07',0,None,None,None,999),
            ('2025-07-08',210,'13:30:00Z','2025-07-08 17:00:00',-4,999),
            ('2026-01-01',-999,'INVALID','INVALID',0,999)])
        sessions=calendar_normalize(calendar_query(db))
        if sessions!=[['2025-01-06',-300,390],['2025-07-08',-240,210]]:
            raise ValueError('CALENDAR_SYNTHETIC_MISMATCH')
        try:
            db.execute('SELECT observed_tickers FROM calendar').fetchall()
        except sqlite3.DatabaseError:
            pass
        else:
            raise ValueError('CALENDAR_AUTHORIZER_FAILED')
    finally:
        db.close()
    rows=[(session_day_base('2025-07-08')+810,10,12,9,11,2)]
    mapped=map_session_rows(sessions,rows)
    if mapped['outside']!=0 or mapped['sessions'][1]['rows']!=[(0,10,12,9,11,2)]:
        raise ValueError('CALENDAR_MAPPING_FAILED')


# Pure descriptive statistics, no market reader, prediction or trade signals.
STATS_RECEIPT='synthetic_descriptive_statistics.local.json'


def describe_session_horizon(sessions,horizon,*,float_prices=False):
    # Input sessions are independent (length, rows) pairs in normalized
    # integer price units. Weight complete bars/pairs equally, not dates.
    if type(sessions) not in (list,tuple) or not 1<=len(sessions)<=366:
        raise ValueError('STATS_SESSION_LIMIT')
    returns=[]
    bars_count=0
    volume_sum=0
    missing_windows=0
    tail_minutes=0
    possible_pairs=0
    positive=negative=zero=0
    for length,rows in sessions:
        result=aggregate_session_rows(rows,length,horizon,float_prices=float_prices)
        bars=result['bars']
        bars_count+=len(bars)
        missing_windows+=result['missing_windows']
        tail_minutes+=result['tail_minutes']
        possible_pairs+=max(0,length//horizon-1)
        previous=None
        for bar in bars:
            if any(v>10**18 for v in bar[1:]):
                raise ValueError('STATS_VALUE_LIMIT')
            volume_sum+=bar[5]
            if previous is not None and bar[0]-previous[0]==horizon:
                delta=bar[4]-previous[4]
                returns.append(delta/previous[4])
                positive+=delta>0
                negative+=delta<0
                zero+=delta==0
            previous=bar
    n=len(returns)
    mean=math.fsum(returns)/n if n else None
    return {'complete_bars':bars_count,'missing_windows':missing_windows,
            'tail_minutes':tail_minutes,'possible_pairs':possible_pairs,
            'observed_pairs':n,'unobserved_pairs':possible_pairs-n,
            'positive':positive,'negative':negative,'zero':zero,
            'mean_return':mean,
            'mean_absolute_return':math.fsum(abs(x) for x in returns)/n if n else None,
            'sample_return_sd':math.sqrt(math.fsum((x-mean)**2 for x in returns)/(n-1)) if n>1 else None,
            'volume_sum':volume_sum,'mean_volume':volume_sum/bars_count if bars_count else None}


def synthetic_statistics_checkpoint(parent):
    parent=local_folder(str(parent))
    def row(i,c):
        return (i,c,c,c,c,2)
    sessions=[(6,[row(i,c) for i,c in ((0,100),(1,110),(2,121),(4,80),(5,80))]),
              (2,[row(0,200),row(1,180)])]
    result=describe_session_horizon(sessions,1)
    expected={'complete_bars':7,'missing_windows':1,'tail_minutes':0,
              'possible_pairs':6,'observed_pairs':4,'unobserved_pairs':2,
              'positive':2,'negative':1,'zero':1,'volume_sum':14,'mean_volume':2.0}
    if any(result[k]!=v for k,v in expected.items()):
        raise ValueError('STATS_COUNT_MISMATCH')
    for key,value in [('mean_return',.025),('mean_absolute_return',.075),
                      ('sample_return_sd',math.sqrt(.0275/3))]:
        if not math.isclose(result[key],value,rel_tol=1e-12,abs_tol=1e-15):
            raise ValueError('STATS_VALUE_MISMATCH')
    full=[(60,[row(i,100) for i in range(60)])]
    counts={}
    for horizon in RESEARCH_HORIZONS:
        flat=describe_session_horizon(full,horizon)
        counts[str(horizon)]=flat['observed_pairs']
        if flat['mean_return']!=0 or flat['mean_absolute_return']!=0 or flat['zero']!=flat['observed_pairs']:
            raise ValueError('STATS_NULL_MISMATCH')
    if counts!={'1':59,'5':11,'15':3,'30':1}:
        raise ValueError('STATS_HORIZON_MISMATCH')
    empty=describe_session_horizon([(5,[])],5)
    if empty['observed_pairs'] or empty['mean_return'] is not None or empty['mean_volume'] is not None or empty['sample_return_sd'] is not None:
        raise ValueError('STATS_EMPTY_MISMATCH')
    receipt={'schema':1,'scope':'SYNTHETIC_ONLY','protocol':'descriptive-adjacent-close-v1',
             'market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED',
             'known_fixture':result,'flat_pair_counts':counts}
    raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode('utf-8')
    dest=parent/STATS_RECEIPT
    atomic(dest,raw)
    with dest.open('rb') as f:
        if f.read(16385)!=raw:
            raise ValueError('STATS_SAVE_FAILED')
    return receipt


# Fixed end-to-end synthetic fixture. No path, member or date arguments.
PIPELINE_RECEIPT='synthetic_integrated_pipeline.local.json'
PIPELINE_WORKER=r'''
import io,json,zipfile
from datetime import datetime,timezone,timedelta
import pyarrow as pa
import pyarrow.parquet as pq
if pa.__version__!='26.0.1':
    raise ValueError('PIPELINE_ARROW_VERSION')
epoch=datetime(1970,1,1,tzinfo=timezone.utc)
def build(rows):
    table=pa.table({'timestamp':pa.array([r[0] for r in rows],type=pa.timestamp('us',tz='UTC')),
                    **{k:pa.array([r[i+1] for r in rows],type=pa.int64()) for i,k in enumerate(('open','high','low','close','volume'))}})
    buffer=io.BytesIO()
    pq.write_table(table,buffer)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('synthetic/selected.parquet',buffer.getvalue())
        z.writestr('synthetic/unused.parquet',b'not parquet')
    return archive.getvalue()
def read(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        item=z.getinfo('synthetic/selected.parquet')
        if item.file_size>512*1024:
            raise ValueError('PIPELINE_MEMBER_LIMIT')
        with z.open(item) as f:
            member=f.read(512*1024+1)
        if len(member)!=item.file_size:
            raise ValueError('PIPELINE_MEMBER_LENGTH')
    with pq.ParquetFile(io.BytesIO(member),pre_buffer=False) as p:
        if p.metadata.num_rows>512 or p.schema_arrow.names!=['timestamp','open','high','low','close','volume']:
            raise ValueError('PIPELINE_SCHEMA')
        table=p.read(use_threads=False)
    if table.schema.field('timestamp').type!=pa.timestamp('us',tz='UTC') or any(table.schema.field(k).type!=pa.int64() for k in ('open','high','low','close','volume')):
        raise ValueError('PIPELINE_SCHEMA')
    # Same integer UTC conversion as the previously validated OHLCV worker.
    # Avoid Arrow's platform-dependent timezone-object conversion.
    ticks=table['timestamp'].cast(pa.int64()).to_pylist()
    columns=[table[name].to_pylist() for name in ('open','high','low','close','volume')]
    first=(datetime(2000,1,1,tzinfo=timezone.utc)-epoch).days*86400000000
    limit=(datetime(2026,1,1,tzinfo=timezone.utc)-epoch).days*86400000000
    result=[]
    for tick,*prices in zip(ticks,*columns):
        if type(tick) is not int or not first<=tick<limit:
            raise ValueError('PIPELINE_PERIOD')
        if tick%60000000 or any(type(v) is not int for v in prices):
            raise ValueError('PIPELINE_ROW')
        result.append([tick//60000000,*prices])
    return result
rows=[]
for start,length,price in [(datetime(2025,1,6,14,30,tzinfo=timezone.utc),60,100),
                           (datetime(2025,7,7,13,30,tzinfo=timezone.utc),45,200)]:
    for i in range(-1,length+1):
        if price==100 and i==7:
            continue
        rows.append((start+timedelta(minutes=i),price,price,price,price,2))
out=read(build(rows))
try:
    read(build([(datetime(2026,1,1,tzinfo=timezone.utc),1,1,1,1,1)]))
except ValueError as exc:
    if str(exc)!='PIPELINE_PERIOD':
        raise
else:
    raise ValueError('PIPELINE_GATE_FAILED')
print(json.dumps({'scope':'SYNTHETIC_ONLY','period_gate':'PASS','rows':out},allow_nan=False))
'''


def integrated_pipeline_expected():
    # All prices are constant inside each session, but different across
    # sessions. Missing minute 7 and outside rows are never bridged.
    return {'1':(104,1,0,103,101,208),'5':(20,1,0,19,17,200),
            '15':(6,1,0,5,4,180),'30':(2,1,15,1,0,120)}


def integrated_pipeline_analyze(raw):
    if len(raw)>65536:
        raise ValueError('PIPELINE_OUTPUT_LIMIT')
    data=json.loads(raw)
    if type(data) is not dict or set(data)!={'scope','period_gate','rows'} or data['scope']!='SYNTHETIC_ONLY' or data['period_gate']!='PASS':
        raise ValueError('PIPELINE_WORKER_RECEIPT')
    rows=data['rows']
    if type(rows) is not list or len(rows)!=108:
        raise ValueError('PIPELINE_ROW_COUNT')
    mapped=map_session_rows([('2025-01-06',-300,60),('2025-07-07',-240,45)],rows)
    if mapped['outside']!=4 or [len(s['rows']) for s in mapped['sessions']]!=[59,45]:
        raise ValueError('PIPELINE_SESSION_COUNT')
    sessions=[(s['length'],s['rows']) for s in mapped['sessions']]
    results={}
    keys=('complete_bars','missing_windows','tail_minutes','possible_pairs','observed_pairs','volume_sum')
    for horizon in RESEARCH_HORIZONS:
        report=describe_session_horizon(sessions,horizon)
        if tuple(report[k] for k in keys)!=integrated_pipeline_expected()[str(horizon)]:
            raise ValueError('PIPELINE_RESULT_COUNT')
        n=report['observed_pairs']
        if (report['positive'] or report['negative'] or report['zero']!=n or
                report['mean_return']!=(0.0 if n else None) or
                report['mean_absolute_return']!=(0.0 if n else None) or
                report['sample_return_sd']!=(0.0 if n>1 else None)):
            raise ValueError('PIPELINE_RESULT_VALUE')
        results[str(horizon)]=report
    return {'schema':1,'scope':'SYNTHETIC_ONLY','protocol':'zip-parquet-session-statistics-v1',
            'market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED',
            'rows':len(rows),'outside':mapped['outside'],'results':results}


def synthetic_integrated_checkpoint(parent):
    parent=local_folder(str(parent))
    target=parent/'ctl_pyarrow_26_0_1'
    local_folder(str(target))
    marker=target/'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes()!=b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    raw=parquet_command(python,['-c',PIPELINE_WORKER],parent,120,capture=True)
    result=integrated_pipeline_analyze(raw)
    payload=json.dumps(result,sort_keys=True,allow_nan=False).encode('utf-8')
    dest=parent/PIPELINE_RECEIPT
    atomic(dest,payload)
    with dest.open('rb') as f:
        if f.read(65537)!=payload:
            raise ValueError('PIPELINE_SAVE_FAILED')
    return result


# Admission evidence only. This version has no real market reader.
SOURCE_GATE_RECEIPT='market_source_admission.local.json'


def source_gate_receipt(parent):
    parent=local_folder(str(parent))
    def read_receipt(name,limit):
        with (parent/name).open('rb') as f:
            raw=f.read(limit+1)
        if len(raw)>limit:
            raise ValueError('SOURCE_GATE_LIMIT')
        obj=json.loads(raw)
        if type(obj) is not dict or obj.get('schema')!=1 or obj.get('research_access')!='LOCKED' or obj.get('market_member_reads')!=0:
            raise ValueError('SOURCE_GATE_SCHEMA')
        return obj,hashlib.sha256(raw).hexdigest()
    mapping,map_hash=read_receipt('existing_index_column_map.local.json',INDEX_MAP_LIMIT)
    selection,selection_hash=read_receipt('market_monthly_quality_selection.local.json',QUALITY_RECEIPT_LIMIT)
    calendar,calendar_hash=read_receipt(CALENDAR_RECEIPT,131072)
    digest,rows=quality_catalog_rows(parent)
    if (mapping.get('scope')!='LOCAL_COLUMN_MAP_ONLY' or mapping.get('application_table_queries')!=0 or
            mapping.get('catalog_sha256')!=digest or
            selection.get('scope')!='LOCAL_RETROSPECTIVE_MONTHLY_SELECTION' or selection.get('catalog_sha256')!=digest or
            selection.get('index_map_sha256')!=map_hash or selection.get('month_start')!=QUALITY_MONTHS[0] or
            selection.get('month_end')!=QUALITY_MONTHS[-1] or
            calendar.get('scope')!='LOCAL_CALENDAR_METADATA' or calendar.get('index_map_sha256')!=map_hash or
            calendar.get('date_start')!=CALENDAR_FIRST or calendar.get('date_end')!=CALENDAR_LAST):
        raise ValueError('SOURCE_GATE_STALE')
    for receipt in (selection,calendar):
        if receipt.get('holdout_evaluation')!='NOT_PERFORMED' or receipt.get('physical_period_isolation')!='UNVERIFIED':
            raise ValueError('SOURCE_GATE_SCOPE')
    path,before=index_file_metadata(mapping['index_source'])
    if before[2]!=mapping['index_size'] or before[3]!=mapping['index_mtime_ns']:
        raise ValueError('SOURCE_GATE_STALE')
    lookup={(row['archive_index'],row['member']):(row['size'],row['crc32']) for row in rows}
    selected=selection.get('selected')
    if type(selected) is not list or len(selected)>128:
        raise ValueError('SOURCE_GATE_SELECTION')
    seen=set()
    for row in selected:
        key=(row['archive_index'],row['member'])
        if (key in seen or type(row['archive_index']) is not int or type(row['size']) is not int or
                type(row['crc32']) is not int or lookup.get(key)!=(row['size'],row['crc32'])):
            raise ValueError('SOURCE_GATE_IDENTITY')
        seen.add(key)
    sessions=calendar.get('sessions')
    if type(sessions) is not list or not 1<=len(sessions)<=CALENDAR_MAX:
        raise ValueError('SOURCE_GATE_CALENDAR')
    previous=''
    for day,offset,duration in sessions:
        session_day_base(day)
        if (not CALENDAR_FIRST<=day<=CALENDAR_LAST or day<=previous or type(offset) is not int or
                offset not in (-300,-240) or type(duration) is not int or not 1<=duration<=390):
            raise ValueError('SOURCE_GATE_CALENDAR')
        previous=day
    if index_file_metadata(str(path))[1]!=before or load_market_candidates(parent)[0]!=digest:
        raise ValueError('SOURCE_GATE_STALE')
    # No filename, user-edited flag, checksum, quality threshold or prior
    # logical-prefix study is treated as proof of physical period isolation.
    # There is intentionally no allowed/execute branch.
    report={'schema':1,'scope':'LOCAL_ADMISSION_METADATA_ONLY','protocol':'source-admission-v1',
            'catalog_sha256':digest,'index_map_sha256':map_hash,'selection_sha256':selection_hash,
            'calendar_sha256':calendar_hash,'candidate_count':len(selected),
            'metadata_consistency':'PASS','physical_period_isolation':'UNVERIFIED',
            'reader_schema':'UNVERIFIED','calendar_completeness':'UNVERIFIED',
            'scientific_execution':'LOCKED','market_member_reads':0,'holdout_evaluation':'NOT_PERFORMED',
            'research_access':'LOCKED','reason':'NO_PERIOD_ISOLATED_SOURCE_OR_APPROVED_READER'}
    payload=json.dumps(report,sort_keys=True).encode('utf-8')
    dest=parent/SOURCE_GATE_RECEIPT
    atomic(dest,payload)
    with dest.open('rb') as f:
        if f.read(16385)!=payload:
            raise ValueError('SOURCE_GATE_SAVE_FAILED')
    return report


# Candidate logical group exclusion on generated Parquet only.
# No file path input or real reader. Footer metadata and compressed bytes
# are not physically isolated even if selected data groups are.
PREFIX_WORKER=r'''
import io,json
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
if pa.__version__!='26.0.1':
    raise ValueError('PREFIX_ARROW_VERSION')
epoch=datetime(1970,1,1)
first=(datetime(2022,3,7)-epoch).days*86400000000
cutoff=(datetime(2026,1,1)-epoch).days*86400000000
schema=pa.schema([('datetime',pa.timestamp('us')),('Open',pa.float64()),
                  ('High',pa.float64()),('Low',pa.float64()),('Close',pa.float64()),
                  ('Volume',pa.int64()),('source',pa.string())])
def build(groups,stats=True):
    out=io.BytesIO()
    with pq.ParquetWriter(out,schema,write_statistics=stats) as writer:
        for dates,price in groups:
            values={'datetime':dates,'Open':[price]*len(dates),'High':[price]*len(dates),
                    'Low':[price]*len(dates),'Close':[price]*len(dates),'Volume':[1]*len(dates),
                    'source':['invented']*len(dates)}
            writer.write_table(pa.Table.from_pydict(values,schema=schema))
    return out.getvalue()
def check(raw):
    # Fixed invented fixture. All groups are classified before any projected
    # data read. Reject unknown metadata instead of guessing.
    with pq.ParquetFile(io.BytesIO(raw),pre_buffer=False) as p:
        if p.schema_arrow!=schema or not 1<=p.num_row_groups<=32:
            raise ValueError('PREFIX_SCHEMA')
        selected=[]
        excluded_boundary=0
        excluded_reserved=0
        prev=None
        for i in range(p.num_row_groups):
            group=p.metadata.row_group(i)
            stats=group.column(0).statistics
            if (not 1<=group.num_rows<=512 or stats is None or not stats.has_min_max or
                    not stats.has_null_count or stats.null_count!=0 or
                    type(stats.min_raw) is not int or type(stats.max_raw) is not int):
                raise ValueError('PREFIX_METADATA')
            lo,hi=stats.min_raw,stats.max_raw
            if lo<first or lo>hi or (prev is not None and lo<=prev):
                raise ValueError('PREFIX_ORDER')
            prev=hi
            if hi<cutoff:
                selected.append((i,lo,hi,group.num_rows))
            elif lo<cutoff:
                excluded_boundary+=1
            else:
                excluded_reserved+=1
        rows=[]
        for i,lo,hi,n in selected:
            # Validate date projection before reading any price column.
            ticks=p.read_row_group(i,columns=['datetime'],use_threads=False)['datetime'].cast(pa.int64()).to_pylist()
            if (len(ticks)!=n or any(type(t) is not int or not first<=t<cutoff or t%60000000 for t in ticks)
                    or any(a>=b for a,b in zip(ticks,ticks[1:])) or ticks[0]!=lo or ticks[-1]!=hi):
                raise ValueError('PREFIX_TIMESTAMP')
            prices=p.read_row_group(i,columns=['Open','High','Low','Close','Volume'],use_threads=False)
            if prices.num_rows!=n:
                raise ValueError('PREFIX_ROW_COUNT')
            rows.extend(zip(ticks,prices['Close'].to_pylist()))
        return {'groups_read':[i for i,*_ in selected],'boundary_groups_excluded':excluded_boundary,
                'reserved_groups_excluded':excluded_reserved,'retained_rows':len(rows),
                'retained_close_sum':sum(c for _,c in rows)}
groups=[([datetime(2025,12,30,9,30),datetime(2025,12,30,9,31)],100.0),
        ([datetime(2025,12,31,9,30),datetime(2026,1,1,9,30)],999.0),
        ([datetime(2026,1,2,9,30)],888.0)]
report=check(build(groups))
assert report=={'groups_read':[0],'boundary_groups_excluded':1,
                'reserved_groups_excluded':1,'retained_rows':2,'retained_close_sum':200.0}
for bad,stats,expected in [(groups,False,'PREFIX_METADATA'),
                           ([groups[1],groups[0]],True,'PREFIX_ORDER'),
                           ([([datetime(2025,12,30,9,30,1)],100.0)],True,'PREFIX_TIMESTAMP')]:
    try:
        check(build(bad,stats))
    except ValueError as exc:
        if str(exc)!=expected:
            raise
    else:
        raise ValueError('PREFIX_REJECTION_FAILED')
print(json.dumps({'scope':'SYNTHETIC_ONLY','report':report,'physical_isolation':'UNVERIFIED'},allow_nan=False))
'''


def synthetic_prefix_checkpoint(parent):
    parent=local_folder(str(parent))
    target=parent/'ctl_pyarrow_26_0_1'
    local_folder(str(target))
    marker=target/'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes()!=b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    raw=parquet_command(python,['-c',PREFIX_WORKER],parent,120,capture=True)
    if len(raw)>4096:
        raise ValueError('PREFIX_RECEIPT_LIMIT')
    out=json.loads(raw)
    expected={'scope':'SYNTHETIC_ONLY','report':{'groups_read':[0],
              'boundary_groups_excluded':1,'reserved_groups_excluded':1,
              'retained_rows':2,'retained_close_sum':200.0},'physical_isolation':'UNVERIFIED'}
    if out!=expected:
        raise ValueError('PREFIX_RECEIPT_INVALID')
    return out


# Owner-approved single-member metadata inspection, explicit manual action only.
# No row decoding, no scientific execution, no automatic scan.
FOOTER_LIMIT=32*1024*1024
FOOTER_REPORT='market_footer_probe.local.json'
FOOTER_ATTEMPT='market_footer_probe_attempt.local.json'
FOOTER_WORKER=r'''
import io,sys,json
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
if pa.__version__!='26.0.1':
    raise ValueError('FOOTER_VERSION')
limit=32*1024*1024
def inspect(raw):
    if not 12<=len(raw)<=limit or raw[:4]!=b'PAR1' or raw[-4:]!=b'PAR1':
        raise ValueError('FOOTER_FORMAT')
    footer_size=int.from_bytes(raw[-8:-4],'little')
    if not 0<footer_size<=min(len(raw)-12,4*1024*1024):
        raise ValueError('FOOTER_LIMIT')
    with pq.ParquetFile(io.BytesIO(raw),pre_buffer=False,thrift_string_size_limit=1048576,
                        thrift_container_size_limit=100000) as p:
        schema=p.schema_arrow
        if not 1<=len(schema)<=32 or not 1<=p.num_row_groups<=4096:
            raise ValueError('FOOTER_SCHEMA_LIMIT')
        # Never return arbitrary file-supplied field names or metadata strings.
        known={'datetime','timestamp','open','high','low','close','volume','source','date','time'}
        fields=[]
        for f in schema:
            name=f.name if f.name.lower() in known and len(f.name)<=16 else 'OTHER'
            t=f.type
            if pa.types.is_timestamp(t):
                kind='timestamp['+t.unit+']'
                zone='NAIVE' if t.tz is None else 'UTC' if t.tz=='UTC' else 'EASTERN' if t.tz in ('America/New_York','US/Eastern') else 'OTHER'
            else:
                kind=str(t) if str(t) in ('double','float','int64','int32','uint64','uint32','string','large_string','date32[day]','date64[ms]','bool') else 'OTHER'
                zone='NA'
            fields.append({'name':name,'type':kind,'zone':zone})
        counts=dict(before=0,crossing=0,reserved=0,unverified=0)
        candidates=[i for i,f in enumerate(schema) if f.name.lower() in ('datetime','timestamp') and pa.types.is_timestamp(f.type)]
        col=None
        cutoff=None
        if len(candidates)==1 and p.metadata.num_columns==len(schema):
            j=candidates[0]
            t=schema[j].type
            if t.tz in (None,'UTC','America/New_York','US/Eastern'):
                # UTC cutoff deliberately conservative; naive Eastern basis
                # is provider documentation, not independently verified.
                cutoff=(datetime(2026,1,1)-datetime(1970,1,1)).days*86400*{'s':1,'ms':1000,'us':1000000,'ns':1000000000}[t.unit]
                col=j
        for i in range(p.num_row_groups):
            label='unverified'
            g=p.metadata.row_group(i)
            if col is not None:
                chunk=g.column(col)
                st=chunk.statistics
                if (chunk.path_in_schema==schema[col].name and g.num_rows>0 and st is not None and
                        st.has_min_max and st.has_null_count and st.null_count==0 and
                        type(st.min_raw) is int and type(st.max_raw) is int and st.min_raw<=st.max_raw):
                    label='before' if st.max_raw<cutoff else 'reserved' if st.min_raw>=cutoff else 'crossing'
            counts[label]+=1
        return {'fields':fields,'groups':counts,'row_decodes':0,'physical_isolation':'UNVERIFIED'}
if sys.argv[1:]==['--fixture']:
    out=io.BytesIO()
    schema=pa.schema([('datetime',pa.timestamp('us')),('Close',pa.float64()),('secret_fixture_field',pa.string())])
    with pq.ParquetWriter(out,schema) as w:
        for days in ([datetime(2025,12,30)],[datetime(2025,12,31),datetime(2026,1,1)],[datetime(2026,1,2)]):
            w.write_table(pa.Table.from_pydict({'datetime':days,'Close':[100.0]*len(days),'secret_fixture_field':['invented']*len(days)},schema=schema))
    print(json.dumps(inspect(out.getvalue())))
elif not sys.argv[1:]:
    raw=sys.stdin.buffer.read(limit+1)
    print(json.dumps(inspect(raw)))
else:
    raise ValueError('FOOTER_ARGS')
'''


def footer_result(raw):
    if len(raw)>8192:
        raise ValueError('FOOTER_RESULT_LIMIT')
    out=json.loads(raw)
    if (type(out) is not dict or set(out)!={'fields','groups','row_decodes','physical_isolation'} or
            out['row_decodes']!=0 or out['physical_isolation']!='UNVERIFIED'):
        raise ValueError('FOOTER_RESULT')
    fields=out['fields']
    if type(fields) is not list or not 1<=len(fields)<=32:
        raise ValueError('FOOTER_RESULT')
    for field in fields:
        if (type(field) is not dict or set(field)!={'name','type','zone'} or
                field['name'].lower() not in ('datetime','timestamp','open','high','low','close','volume','source','date','time','other') or
                field['type'] not in ('timestamp[s]','timestamp[ms]','timestamp[us]','timestamp[ns]','double','float','int64','int32','uint64','uint32','string','large_string','date32[day]','date64[ms]','bool','OTHER') or
                field['zone'] not in ('NAIVE','UTC','EASTERN','OTHER','NA')):
            raise ValueError('FOOTER_RESULT')
    groups=out['groups']
    if (type(groups) is not dict or set(groups)!={'before','crossing','reserved','unverified'} or
            any(type(v) is not int or v<0 for v in groups.values()) or not 1<=sum(groups.values())<=4096):
        raise ValueError('FOOTER_RESULT')
    return out


def footer_member_bytes(archive,member,size,crc):
    if type(size) is not int or not 12<=size<=FOOTER_LIMIT or type(crc) is not int or not 0<=crc<=0xffffffff:
        raise ValueError('FOOTER_MEMBER_LIMIT')
    # Exact one central-directory entry, no filesystem extraction.
    with archive.open('rb') as source:
        before=os.fstat(source.fileno())
        with zipfile.ZipFile(source) as z:
            matches=[i for i in z.infolist() if i.filename==member]
            if len(matches)!=1:
                raise ValueError('FOOTER_MEMBER_IDENTITY')
            item=matches[0]
            if (item.file_size!=size or item.CRC!=crc or item.flag_bits&1 or
                    item.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or
                    not 0<item.compress_size<=FOOTER_LIMIT):
                raise ValueError('FOOTER_MEMBER_IDENTITY')
            with z.open(item) as stream:
                raw=stream.read(size+1)
            if len(raw)!=size:
                raise ValueError('FOOTER_MEMBER_LENGTH')
        after=os.fstat(source.fileno())
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('FOOTER_SOURCE_CHANGED')
    return raw


def market_footer_probe(parent):
    parent=local_folder(str(parent))
    receipt=parent/FOOTER_REPORT
    if receipt.is_file():
        with receipt.open('rb') as f:
            return footer_result(f.read(8193))
    # An interrupted attempt is not silently repeated on another member.
    if (parent/FOOTER_ATTEMPT).exists():
        raise ValueError('FOOTER_ATTEMPT_EXISTS')
    gate=source_gate_receipt(parent)
    with (parent/'market_monthly_quality_selection.local.json').open('rb') as f:
        selected_raw=f.read(QUALITY_RECEIPT_LIMIT+1)
    if hashlib.sha256(selected_raw).hexdigest()!=gate['selection_sha256']:
        raise ValueError('FOOTER_SELECTION_CHANGED')
    selected=json.loads(selected_raw)['selected']
    row=next((r for r in selected if 12<=r['size']<=FOOTER_LIMIT),None)
    if row is None:
        raise ValueError('FOOTER_NO_BOUNDED_CANDIDATE')
    paths=zip_paths(read_folders(parent/'research_folders.local.json').get('market_zips',[]))
    archive=local_zip(paths[row['archive_index']])
    target=local_folder(str(parent/'ctl_pyarrow_26_0_1'))
    marker=target/'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes()!=b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    # Exclusive create before any actual member access, once per installation.
    with (parent/FOOTER_ATTEMPT).open('xb') as f:
        f.write(b'ONE_MEMBER_METADATA_ONLY\n')
        f.flush()
        os.fsync(f.fileno())
    if load_market_candidates(parent)[0]!=gate['catalog_sha256']:
        raise ValueError('FOOTER_SOURCE_CHANGED')
    raw=footer_member_bytes(archive,row['member'],row['size'],row['crc32'])
    if load_market_candidates(parent)[0]!=gate['catalog_sha256']:
        raise ValueError('FOOTER_SOURCE_CHANGED')
    done=subprocess.run([str(python),'-I','-c',FOOTER_WORKER],input=raw,cwd=str(parent),
                        env=parquet_env(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                        timeout=120,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    report=footer_result(done.stdout)
    payload=json.dumps(report,sort_keys=True).encode('utf-8')
    atomic(receipt,payload)
    with receipt.open('rb') as f:
        if f.read(8193)!=payload:
            raise ValueError('FOOTER_SAVE_FAILED')
    return report


def footer_report_text(report):
    lines=['実Parquet構造確認（1候補・メタデータのみ）','データ行復号 0 / 2026年評価なし / 研究実行ロック中',
           '物理的期間隔離：未検証','列構造：']
    lines.extend(f"  {f['name']}: {f['type']} / {f['zone']}" for f in report['fields'])
    g=report['groups']
    lines.append(f"行グループ分類（メタデータ上）：2025年以前 {g['before']} / 境界混在 {g['crossing']} / 封印期間 {g['reserved']} / 判定不能 {g['unverified']}")
    return '\n'.join(lines)


# Logical prefix adapter. Real mode validates only, no scientific metrics.
# Immutable memory buffer; full timestamp column is decoded for order checks.
# Arrow may internally decode pages containing reserved price rows.
BATCH_ADAPTER_REPORT='market_batch_adapter.local.json'
BATCH_ADAPTER_ATTEMPT='market_batch_adapter_attempt.local.json'
SESSION_CONNECTION_REPORT='market_session_connection.local.json'
SESSION_CONNECTION_ATTEMPT='market_session_connection_attempt.local.json'
BATCH_ADAPTER_WORKER=r'''
import io,sys,json,math,hashlib
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
if pa.__version__!='26.0.1':
    raise ValueError('BATCH_VERSION')
LIMIT=32*1024*1024
STEP=60000000000
EPOCH=datetime(1970,1,1)
FIRST=(datetime(2022,3,7)-EPOCH).days*86400*1000000000
CUTOFF=(datetime(2026,1,1)-EPOCH).days*86400*1000000000
NAMES=['datetime','Open','High','Low','Close','Volume']
SCHEMA=pa.schema([('datetime',pa.timestamp('ns')),
                  *[(k,pa.float64()) for k in NAMES[1:5]],
                  ('Volume',pa.int64()),('source',pa.large_string())])
def prefix_rows(raw,batch_size=8192):
    if not 12<=len(raw)<=LIMIT or raw[:4]!=b'PAR1' or raw[-4:]!=b'PAR1':
        raise ValueError('BATCH_FORMAT')
    if not 0<int.from_bytes(raw[-8:-4],'little')<=min(len(raw)-12,4*1024*1024):
        raise ValueError('BATCH_FOOTER')
    with pq.ParquetFile(io.BytesIO(raw),pre_buffer=False,thrift_string_size_limit=1048576,
                        thrift_container_size_limit=100000) as p:
        if p.schema_arrow!=SCHEMA or not 1<=p.metadata.num_rows<=2000000 or not 1<=p.num_row_groups<=4096:
            raise ValueError('BATCH_SCHEMA')
        if type(batch_size) is not int or not 1<=batch_size<=8192:
            raise ValueError('BATCH_SIZE')
        # Do not assume chronology based on footer extrema. Inspect only
        # timestamps in this pass, including reserved dates for ordering.
        prior=-1
        count=0
        total=0
        before_hash=hashlib.sha256()
        for batch in p.iter_batches(batch_size=batch_size,columns=['datetime'],use_threads=False):
            ticks=batch.column(0).cast(pa.int64()).to_pylist()
            for t in ticks:
                if type(t) is not int or t<=prior:
                    raise ValueError('BATCH_ORDER')
                prior=t
                total+=1
                if t<CUTOFF:
                    if t<FIRST or t%STEP:
                        raise ValueError('BATCH_TIME')
                    count+=1
                    before_hash.update(t.to_bytes(8,'little',signed=True))
        if total!=p.metadata.num_rows or count==0:
            raise ValueError('BATCH_EMPTY_OR_COUNT')
        remaining=count
        after_hash=hashlib.sha256()
        for batch in p.iter_batches(batch_size=batch_size,columns=NAMES,use_threads=False):
            # Slice before converting any price values to Python. Never
            # inspect or emit reserved prices, even within a crossing batch.
            take=min(remaining,batch.num_rows)
            part=batch.slice(0,take)
            columns=[part.column(0).cast(pa.int64()).to_pylist()]
            columns.extend(part.column(i).to_pylist() for i in range(1,6))
            for tick,o,h,l,c,v in zip(*columns):
                if type(tick) is not int or not FIRST<=tick<CUTOFF or tick%STEP:
                    raise ValueError('BATCH_PERIOD')
                if (any(type(x) is not float or not math.isfinite(x) or not 0<x<=10**18 for x in (o,h,l,c)) or
                        h<max(o,l,c) or l>min(o,h,c) or type(v) is not int or v<0):
                    raise ValueError('BATCH_OHLCV')
                after_hash.update(tick.to_bytes(8,'little',signed=True))
                yield [tick//STEP,o,h,l,c,v]
            remaining-=take
            if remaining==0:
                break
        if remaining or before_hash.digest()!=after_hash.digest():
            raise ValueError('BATCH_PREFIX_MISMATCH')
def session_sample(raw,schedule):
    # Fixed engineering selection: first observed scheduled regular session.
    # No selection based on price, return, volume or aggregation outcome.
    if type(schedule) is not list or not 1<=len(schedule)<=1500:
        raise ValueError('SAMPLE_CALENDAR')
    days={}
    previous=''
    for day,offset,length in schedule:
        parsed=datetime.strptime(day,'%Y-%m-%d')
        base=(parsed-EPOCH).days*1440
        if parsed.strftime('%Y-%m-%d')!=day or day<=previous or not FIRST//STEP<=base<CUTOFF//STEP or type(offset) is not int or offset not in (-300,-240) or type(length) is not int or not 1<=length<=390:
            raise ValueError('SAMPLE_CALENDAR')
        previous=day
        days[base//1440]=(day,offset,length)
    chosen=None
    rows=[]
    for row in prefix_rows(raw):
        minute=row[0]
        item=days.get(minute//1440)
        if item is None or not 570<=minute%1440<570+item[2]:
            continue
        if chosen is None:
            chosen=item
        if item==chosen:
            rows.append(row)
    if chosen is None:
        return {'status':'NO_REGULAR_SAMPLE'}
    if not 1<=len(rows)<=390:
        raise ValueError('SAMPLE_LIMIT')
    return {'status':'PASS','session':chosen,'rows':rows}
def make(dates,values,volumes):
    out=io.BytesIO()
    data={'datetime':dates,**{k:values for k in NAMES[1:5]},'Volume':volumes,'source':['invented']*len(dates)}
    pq.write_table(pa.Table.from_pydict(data,schema=SCHEMA),out,row_group_size=len(dates))
    return out.getvalue()
if sys.argv[1:]==['--fixture']:
    dates=[datetime(2025,7,7,9,30+i) for i in range(3)]+[datetime(2026,1,1,9,30),datetime(2026,1,2,9,30)]
    prices=[100.125,100.375,100.625,float('nan'),-1.0]
    volumes=[1,2,3,-1,-1]
    raw=make(dates,prices,volumes)
    rows=list(prefix_rows(raw,2))
    if rows!=list(prefix_rows(raw,3)) or [r[4] for r in rows]!=prices[:3] or len(rows)!=3:
        raise ValueError('BATCH_FIXTURE')
    bad=[(make([dates[0],dates[3],dates[1]],[1.0]*3,[1]*3),'BATCH_ORDER'),
         (make([dates[0],dates[0]],[1.0]*2,[1]*2),'BATCH_ORDER'),
         (make([dates[3]],[1.0],[1]),'BATCH_EMPTY_OR_COUNT'),
         (make([dates[0]],[float('nan')],[1]),'BATCH_OHLCV'),
         (make([datetime(2025,7,7,9,30,1)],[1.0],[1]),'BATCH_TIME')]
    for data,expected in bad:
        try:
            list(prefix_rows(data,2))
        except ValueError as exc:
            if str(exc)!=expected:
                raise
        else:
            raise ValueError('BATCH_REJECTION')
    sample=session_sample(raw,[['2025-07-07',-240,3]])
    if sample!={'status':'PASS','session':('2025-07-07',-240,3),'rows':rows} or session_sample(raw,[['2025-07-08',-240,390]])!={'status':'NO_REGULAR_SAMPLE'}:
        raise ValueError('SAMPLE_FIXTURE')
    print(json.dumps({'scope':'SYNTHETIC_ONLY','rows':rows},allow_nan=False))
elif sys.argv[1:]==['--session-sample']:
    header=sys.stdin.buffer.read(4)
    size=int.from_bytes(header,'little')
    if len(header)!=4 or not 1<=size<=65536:
        raise ValueError('SAMPLE_HEADER')
    calendar=sys.stdin.buffer.read(size)
    if len(calendar)!=size:
        raise ValueError('SAMPLE_HEADER')
    raw=sys.stdin.buffer.read(LIMIT+1)
    print(json.dumps(session_sample(raw,json.loads(calendar)),allow_nan=False))
elif not sys.argv[1:]:
    raw=sys.stdin.buffer.read(LIMIT+1)
    result='PASS'
    try:
        for _ in prefix_rows(raw):
            pass
    except ValueError as exc:
        code=str(exc)
        result=code if code in ('BATCH_FORMAT','BATCH_FOOTER','BATCH_SCHEMA','BATCH_ORDER','BATCH_TIME','BATCH_EMPTY_OR_COUNT','BATCH_PERIOD','BATCH_OHLCV','BATCH_PREFIX_MISMATCH') else 'BATCH_VALIDATION'
    except Exception:
        result='BATCH_READER'
    print(json.dumps({'scope':'LOCAL_ADAPTER_VALIDATION_ONLY','status':result,
                      'scientific_execution':'LOCKED','holdout_evaluation':'NOT_PERFORMED',
                      'physical_isolation':'UNVERIFIED'}))
else:
    raise ValueError('BATCH_ARGS')
'''


def synthetic_batch_adapter_checkpoint(parent):
    parent=local_folder(str(parent))
    target=local_folder(str(parent/'ctl_pyarrow_26_0_1'))
    marker=target/'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes()!=b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    raw=parquet_command(python,['-c',BATCH_ADAPTER_WORKER,'--fixture'],parent,120,capture=True)
    if len(raw)>4096:
        raise ValueError('BATCH_FIXTURE_LIMIT')
    out=json.loads(raw)
    start=session_day_base('2025-07-07')+570
    rows=[[start+i,*([price]*4),i+1] for i,price in enumerate((100.125,100.375,100.625))]
    if out!={'scope':'SYNTHETIC_ONLY','rows':rows}:
        raise ValueError('BATCH_FIXTURE_RESULT')
    # Naive Eastern wall clock mapped using explicit calendar offset.
    mapped=map_session_rows([('2025-07-07',-240,3)],[[r[0]+240,*r[1:]] for r in rows],float_prices=True)
    session=mapped['sessions'][0]
    bars=aggregate_session_rows(session['rows'],3,1,float_prices=True)['bars']
    stats=describe_session_horizon([(3,session['rows'])],1,float_prices=True)
    expected=(0.25/100.125+0.25/100.375)/2
    if mapped['outside']!=0 or [r[4] for r in bars]!=[100.125,100.375,100.625] or stats['observed_pairs']!=2 or not math.isclose(stats['mean_return'],expected,rel_tol=1e-12):
        raise ValueError('BATCH_FIXTURE_INTEGRATION')
    return {'scope':'SYNTHETIC_ONLY','status':'PASS'}


def batch_adapter_result(raw):
    if len(raw)>4096:
        raise ValueError('BATCH_RESULT_LIMIT')
    out=json.loads(raw)
    if (type(out) is not dict or set(out)!={'scope','status','scientific_execution','holdout_evaluation','physical_isolation'} or
            out['scope']!='LOCAL_ADAPTER_VALIDATION_ONLY' or out['scientific_execution']!='LOCKED' or
            out['holdout_evaluation']!='NOT_PERFORMED' or out['physical_isolation']!='UNVERIFIED' or
            out['status'] not in ('PASS','BATCH_FORMAT','BATCH_FOOTER','BATCH_SCHEMA','BATCH_ORDER','BATCH_TIME','BATCH_EMPTY_OR_COUNT','BATCH_PERIOD','BATCH_OHLCV','BATCH_PREFIX_MISMATCH','BATCH_VALIDATION','BATCH_READER')):
        raise ValueError('BATCH_RESULT')
    return out


def session_connection_result(raw):
    if len(raw)>4096:
        raise ValueError('SESSION_CONNECTION_RESULT')
    obj=json.loads(raw)
    if (type(obj) is not dict or set(obj)!={'scope','status','horizons','research_access','physical_isolation'} or
            obj['scope']!='LOCAL_SESSION_CONNECTION_ONLY' or obj['research_access']!='LOCKED' or obj['physical_isolation']!='UNVERIFIED' or
            obj['status'] not in ('PASS','NO_REGULAR_SAMPLE','INCOMPLETE_WINDOWS') or
            obj['horizons']!=([1,5,15,30] if obj['status']=='PASS' else [])):
        raise ValueError('SESSION_CONNECTION_RESULT')
    return obj


def session_connection_check(sample,schedule):
    report={'scope':'LOCAL_SESSION_CONNECTION_ONLY','status':'NO_REGULAR_SAMPLE','horizons':[],
            'research_access':'LOCKED','physical_isolation':'UNVERIFIED'}
    if sample=={'status':'NO_REGULAR_SAMPLE'}:
        return report
    if type(sample) is not dict or set(sample)!={'status','session','rows'} or sample['status']!='PASS' or sample['session'] not in schedule:
        raise ValueError('SESSION_SAMPLE_INVALID')
    day,offset,length=sample['session']
    start=session_day_base(day)+570
    rows=sample['rows']
    if type(rows) is not list or not 1<=len(rows)<=length or any(type(r) is not list or len(r)!=6 or type(r[0]) is not int or not start<=r[0]<start+length for r in rows):
        raise ValueError('SESSION_SAMPLE_INVALID')
    mapped=map_session_rows([sample['session']],[[r[0]-offset,*r[1:]] for r in rows],float_prices=True)
    if mapped['outside'] or len(mapped['sessions'])!=1 or len(mapped['sessions'][0]['rows'])!=len(rows):
        raise ValueError('SESSION_SAMPLE_MAPPING')
    relative=mapped['sessions'][0]['rows']
    by_minute={r[0]:r[1:] for r in relative}
    all_nonempty=True
    for h in RESEARCH_HORIZONS:
        result=aggregate_session_rows(relative,length,h,float_prices=True)
        expected=[]
        for begin in range(0,length-length%h,h):
            window=[by_minute.get(i) for i in range(begin,begin+h)]
            if None not in window:
                expected.append((begin,window[0][0],max(r[1] for r in window),min(r[2] for r in window),window[-1][3],sum(r[4] for r in window)))
        if (result['bars']!=expected or result['missing_windows']+len(expected)!=length//h or
                result['tail_minutes']!=length%h or result['missing_minutes']!=length-len(relative)):
            raise ValueError('SESSION_AGGREGATION_MISMATCH')
        all_nonempty=all_nonempty and bool(expected)
    report['status']='PASS' if all_nonempty else 'INCOMPLETE_WINDOWS'
    report['horizons']=[1,5,15,30] if all_nonempty else []
    return report


def market_batch_adapter_probe(parent,*,integration=False):
    parent=local_folder(str(parent))
    receipt=parent/(SESSION_CONNECTION_REPORT if integration else BATCH_ADAPTER_REPORT)
    attempt=parent/(SESSION_CONNECTION_ATTEMPT if integration else BATCH_ADAPTER_ATTEMPT)
    validate=session_connection_result if integration else batch_adapter_result
    if receipt.is_file():
        with receipt.open('rb') as f:
            return validate(f.read(4097))
    if attempt.exists():
        raise ValueError('BATCH_ATTEMPT_EXISTS')
    # Require completed structural probe; its legacy receipt does not bind
    # identity. Recheck current selection, do not assert it is the same member.
    with (parent/FOOTER_REPORT).open('rb') as f:
        footer_result(f.read(8193))
    if integration:
        with (parent/BATCH_ADAPTER_REPORT).open('rb') as f:
            if batch_adapter_result(f.read(4097))['status']!='PASS':
                raise ValueError('BATCH_PREREQUISITE')
    gate=source_gate_receipt(parent)
    schedule=None
    if integration:
        with (parent/CALENDAR_RECEIPT).open('rb') as f:
            calendar_raw=f.read(131073)
        if len(calendar_raw)>131072 or hashlib.sha256(calendar_raw).hexdigest()!=gate['calendar_sha256']:
            raise ValueError('SESSION_CALENDAR_CHANGED')
        schedule=json.loads(calendar_raw)['sessions']
    with (parent/'market_monthly_quality_selection.local.json').open('rb') as f:
        selected_raw=f.read(QUALITY_RECEIPT_LIMIT+1)
    if hashlib.sha256(selected_raw).hexdigest()!=gate['selection_sha256']:
        raise ValueError('BATCH_SELECTION_CHANGED')
    selected=json.loads(selected_raw)['selected']
    row=next((r for r in selected if 12<=r['size']<=FOOTER_LIMIT),None)
    if row is None:
        raise ValueError('BATCH_NO_CANDIDATE')
    paths=zip_paths(read_folders(parent/'research_folders.local.json').get('market_zips',[]))
    archive=local_zip(paths[row['archive_index']])
    target=local_folder(str(parent/'ctl_pyarrow_26_0_1'))
    marker=target/'ctl-owned.txt'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size!=len(b'CTL_PYARROW_26_0_1\n') or marker.read_bytes()!=b'CTL_PYARROW_26_0_1\n':
        raise ValueError('PARQUET_UNOWNED_ENV')
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('PARQUET_NOT_INSTALLED')
    with attempt.open('xb') as f:
        f.write(b'ONE_MEMBER_SESSION_CONNECTION\n' if integration else b'ONE_MEMBER_LOGICAL_PREFIX_VALIDATION\n')
        f.flush()
        os.fsync(f.fileno())
    if load_market_candidates(parent)[0]!=gate['catalog_sha256']:
        raise ValueError('BATCH_SOURCE_CHANGED')
    raw=footer_member_bytes(archive,row['member'],row['size'],row['crc32'])
    if load_market_candidates(parent)[0]!=gate['catalog_sha256']:
        raise ValueError('BATCH_SOURCE_CHANGED')
    args=[str(python),'-I','-c',BATCH_ADAPTER_WORKER]
    if integration:
        calendar=json.dumps(schedule,separators=(',',':')).encode('utf-8')
        if len(calendar)>65536:
            raise ValueError('SESSION_CALENDAR_LIMIT')
        raw=len(calendar).to_bytes(4,'little')+calendar+raw
        args.append('--session-sample')
    done=subprocess.run(args,input=raw,cwd=str(parent),
                        env=parquet_env(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                        timeout=120,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if integration:
        if len(done.stdout)>131072:
            raise ValueError('SESSION_SAMPLE_LIMIT')
        report=session_connection_check(json.loads(done.stdout),schedule)
    else:
        report=batch_adapter_result(done.stdout)
    payload=json.dumps(report,sort_keys=True).encode('utf-8')
    atomic(receipt,payload)
    with receipt.open('rb') as f:
        if f.read(4097)!=payload:
            raise ValueError('BATCH_SAVE')
    return report


def batch_adapter_text(report):
    status=report['status']
    return ('実Parquet接続検査（1候補・論理期間制限）\n'
            '結果：'+status+'\n'
            '日時順序・2025年以前OHLCV形式の検査のみ / 研究実行ロック中\n'
            '2026年価格の研究・評価なし / 内部復号・物理隔離は未保証\n'
            '実データ値・銘柄・行数の出力なし')


# Operational control plane. This is not the shared scientific RunGuard.
# No market member read, no task execution, no remote lease mutation.
CONTROL_DB='runner_control_plane.local.sqlite'
CONTROL_LAUNCH=os.urandom(16).hex()
CONTROL_QUEUE_URL='https://raw.githubusercontent.com/mibesamiti-png/Chappy-Trading-Lab/refs/heads/main/TASK_QUEUE.json'
CONTROL_LEASE_URL='https://raw.githubusercontent.com/mibesamiti-png/Chappy-Trading-Lab/refs/heads/coordination/lease/coordination/lease.json'
CONTROL_IDS=tuple('CTL-%03d'%i for i in range(1,7))


def control_remote_read(url,opener=None):
    if url not in (CONTROL_QUEUE_URL,CONTROL_LEASE_URL):
        raise ValueError('CONTROL_ENDPOINT')
    if opener is None:
        opener=urllib.request.urlopen
    requested=url+'?ctl_check='+str(time.time_ns())
    req=urllib.request.Request(requested,headers={'User-Agent':'Chappy-Trading-Lab-Control-ReadOnly','Cache-Control':'no-cache, no-store'})
    with opener(req,timeout=8) as response:
        if response.status!=200 or response.geturl()!=requested:
            raise ValueError('CONTROL_RESPONSE')
        raw=response.read(65537)
    if len(raw)>65536:
        raise ValueError('CONTROL_LIMIT')
    return json.loads(raw)


def control_queue_summary(q,lease):
    if (type(q) is not dict or q.get('schema_version')!=1 or type(q.get('revision')) is not int or
            type(q.get('holdout')) is not dict or q['holdout'].get('year')!=2026 or q['holdout'].get('status')!='locked'):
        raise ValueError('CONTROL_QUEUE')
    tasks=q.get('tasks')
    if type(tasks) is not list or not 1<=len(tasks)<=64:
        raise ValueError('CONTROL_QUEUE')
    by={}
    for item in tasks:
        if (type(item) is not dict or item.get('id') not in CONTROL_IDS or item['id'] in by or
                type(item.get('priority')) is not int or item['priority']<=0 or
                item.get('status') not in ('blocked','completed','approval_required','ready','pending')):
            raise ValueError('CONTROL_QUEUE')
        deps=item.get('depends_on',[])
        if type(deps) is not list or len(deps)>6 or any(type(x) is not str or x not in CONTROL_IDS or x==item['id'] for x in deps) or len(set(deps))!=len(deps):
            raise ValueError('CONTROL_QUEUE')
        by[item['id']]=item
    if set(by)!=set(CONTROL_IDS) or by['CTL-006']['status']!='approval_required':
        raise ValueError('CONTROL_QUEUE')
    if any(by[x]['status']!='completed' for x in CONTROL_IDS[1:5]) or by['CTL-005'].get('decision')!='no_go_for_new_predictive_models_on_this_branch':
        raise ValueError('CONTROL_SCOPE_CHANGED')
    for item in tasks:
        if item['status']=='completed' and any(by[d]['status']!='completed' for d in item.get('depends_on',[])):
            raise ValueError('CONTROL_DEPENDENCY')
    ready=[item for item in tasks if item['status']=='ready' and all(by[d]['status']=='completed' for d in item.get('depends_on',[]))]
    ready.sort(key=lambda item:(item['priority'],item['id']))
    if type(lease) is not dict or lease.get('schema_version')!=1:
        raise ValueError('CONTROL_LEASE')
    if lease.get('status')=='idle' and lease.get('owner') is None and lease.get('task_ids')==[] and lease.get('expires_utc') is None:
        remote='OBSERVED_IDLE_NOT_ACQUIRED'
    elif lease.get('status')=='active' and type(lease.get('owner')) is str and bool(lease['owner']) and type(lease.get('task_ids')) is list and bool(lease['task_ids']) and type(lease.get('expires_utc')) is str:
        remote='OBSERVED_ACTIVE_STOP'
    else:
        raise ValueError('CONTROL_LEASE')
    return {'revision':q['revision'],'completed':4,'next_task':ready[0]['id'] if ready else ('CTL-001' if by['CTL-001']['status']=='blocked' else 'NONE'),
            'task_status':by['CTL-001']['status'],'remote':remote,'research_access':'LOCKED'}


def control_evidence(parent):
    # Existing receipt validation, not a reread of market members.
    gate=source_gate_receipt(parent)
    evidence={'catalog_sha256':gate['catalog_sha256'],'selection_sha256':gate['selection_sha256'],
              'calendar_sha256':gate['calendar_sha256'],'index_map_sha256':gate['index_map_sha256']}
    for name,validator in ((BATCH_ADAPTER_REPORT,batch_adapter_result),(SESSION_CONNECTION_REPORT,session_connection_result)):
        with (parent/name).open('rb') as f:
            raw=f.read(4097)
        if validator(raw)['status']!='PASS':
            raise ValueError('CONTROL_PREREQUISITE')
        evidence[name]=hashlib.sha256(raw).hexdigest()
    return hashlib.sha256(json.dumps(evidence,sort_keys=True).encode('utf-8')).hexdigest()


def control_checkpoint(parent,launch,evidence,queue_summary):
    # Local engineering ledger only. Transactions serialize this ledger,
    # not other research writers. No implicit recovery of a research lease.
    parent=local_folder(str(parent))
    if not re.fullmatch(r'[0-9a-f]{32}',launch) or not re.fullmatch(r'[0-9a-f]{64}',evidence):
        raise ValueError('CONTROL_ID')
    fingerprint=hashlib.sha256(json.dumps({'evidence':evidence,'revision':queue_summary['revision'],
                                           'task_status':queue_summary['task_status']},sort_keys=True).encode('utf-8')).hexdigest()
    path=parent/CONTROL_DB
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('CONTROL_PATH')
    db=sqlite3.connect(path,timeout=1,isolation_level=None)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS continuity (id INTEGER PRIMARY KEY CHECK(id=1), fingerprint TEXT NOT NULL, first_launch TEXT NOT NULL, second_launch TEXT, CHECK(second_launch IS NULL OR second_launch<>first_launch))')
        row=db.execute('SELECT fingerprint,first_launch,second_launch FROM continuity WHERE id=1').fetchone()
        if row is None:
            db.execute('INSERT INTO continuity VALUES(1,?,?,NULL)',(fingerprint,launch))
            state='RESTART_REQUIRED'
        elif row[0]!=fingerprint:
            state='EVIDENCE_CHANGED_STOP'
        elif row[2] is not None:
            state='REOPENED'
        elif row[1]==launch:
            state='RESTART_REQUIRED'
        else:
            db.execute('UPDATE continuity SET second_launch=? WHERE id=1',(launch,))
            state='REOPENED'
        db.commit()
    finally:
        db.close()
    return state


def control_plane_run(parent,launch=CONTROL_LAUNCH):
    q=control_remote_read(CONTROL_QUEUE_URL)
    lease=control_remote_read(CONTROL_LEASE_URL)
    summary=control_queue_summary(q,lease)
    if summary['remote']!='OBSERVED_IDLE_NOT_ACQUIRED':
        return {**summary,'continuity':'REMOTE_ACTIVE_STOP'}
    evidence=control_evidence(parent)
    return {**summary,'continuity':control_checkpoint(parent,launch,evidence,summary)}


def control_plane_text(summary):
    states={'RESTART_REQUIRED':'保存完了・アプリ再起動後に再確認','REOPENED':'別起動IDで保存状態再読込成功',
            'EVIDENCE_CHANGED_STOP':'証拠または研究キュー変更・停止','REMOTE_ACTIVE_STOP':'共有実行権が使用中・停止'}
    return ('研究実行管理（準備・読取専用）\n'
            '完了済み研究：CTL-002〜005（GitHub記録） / 再実行なし\n'
            '次の候補：'+summary['next_task']+' / CTL-001状態：'+summary['task_status']+'\n'
            '共有実行権：'+('空き応答を確認・未取得' if summary['remote']=='OBSERVED_IDLE_NOT_ACQUIRED' else '使用中応答・停止')+'\n'
            'ローカル継続性：'+states[summary['continuity']]+'\n'
            '研究実行ロック中 / 新規研究・市場本体読取・2026年評価なし\n'
            '実際の別AIセッション・共通研究DB・共有実行権取得は未検証')


# CTL-001 operational pilot only, no scientific computation.
DUAL_PR=41
RESUME_PR=43
RESUME_HEAD='67dc316a9a58556f8a98a2e4a6bc99a2cac59acb'
RESUME_PROTOCOL='guarded-artificial-two-stage-v1'
DUAL_HEAD='649c92eb2cb89dc3c0396c714f6bfd46cc9f7a1f'
DUAL_BASE='/repos/mibesamiti-png/Chappy-Trading-Lab'
DUAL_LEASE=DUAL_BASE+'/contents/coordination/lease.json'
DUAL_LEASE_GET=DUAL_LEASE+'?ref=coordination%2Flease'
DUAL_QUEUE=DUAL_BASE+'/contents/TASK_QUEUE.json?ref=main'
DUAL_JOURNAL='dual_guard_pilot.local.json'
DUAL_STATUS_TEXT='CTL-001 operational pilot: local guard acquired; prior checkpoint preserved; no market reads or research. Release follows. This is not CTL-001 completion.'


class DualNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def dual_api(endpoint,method='GET',body=None,token=None):
    allowed={('GET',x) for x in (DUAL_QUEUE,DUAL_LEASE_GET,DUAL_BASE+'/pulls/41',DUAL_BASE+'/pulls/43',DUAL_BASE+'/pulls?state=open&per_page=100')}
    allowed|={('PUT',DUAL_LEASE),('POST',DUAL_BASE+'/issues/41/comments'),('POST',DUAL_BASE+'/issues/43/comments')}
    if (method,endpoint) not in allowed:
        raise ValueError('DUAL_ENDPOINT')
    data=json.dumps(body,separators=(',',':')).encode('utf-8') if body is not None else None
    if type(token) is not str or not re.fullmatch(r'[A-Za-z0-9_]{20,255}',token):
        raise ValueError('DUAL_AUTH')
    req=urllib.request.Request('https://api.github.com'+endpoint,data=data,method=method,
                               headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                                        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'Chappy-Trading-Lab',
                                        'Cache-Control':'no-cache, no-store','Content-Type':'application/json'})
    with urllib.request.build_opener(DualNoRedirect()).open(req,timeout=15) as response:
        if response.geturl()!=req.full_url:
            raise ValueError('DUAL_REDIRECT')
        raw=response.read(1048577)
    if len(raw)>1048576:
        raise ValueError('DUAL_RESPONSE_LIMIT')
    return json.loads(raw)


def dual_contents(obj):
    if type(obj) is not dict or obj.get('type')!='file' or obj.get('encoding')!='base64' or not re.fullmatch(r'[0-9a-f]{40}',obj.get('sha','')):
        raise ValueError('DUAL_CONTENTS')
    raw=base64.b64decode(''.join(obj['content'].split()),validate=True)
    if len(raw)>65536:
        raise ValueError('DUAL_CONTENTS')
    return obj['sha'],json.loads(raw)


def dual_local_guard(path,owner,deadline,action):
    path=Path(path)
    if path.name.lower()!='run_guard.sqlite' or path.is_symlink() or not path.is_file():
        raise ValueError('DUAL_DB_PATH')
    local_folder(str(path.parent))
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=rw',uri=True,timeout=2,isolation_level=None)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        for table,columns in [('guard',['id','owner','status','deadline','checkpoint']),('completed',['task','revision','owner','finished'])]:
            if db.execute('SELECT type FROM sqlite_master WHERE name=?',(table,)).fetchone()!=('table',) or [r[1] for r in db.execute('PRAGMA table_info('+table+')')]!=columns:
                raise ValueError('DUAL_DB_SCHEMA')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('guard','completed')").fetchone():
            raise ValueError('DUAL_DB_TRIGGER')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT owner,status,deadline FROM guard WHERE id=1').fetchone()
        if action in ('idle','acquire'):
            if row is not None and row[1]!='released':
                raise ValueError('DUAL_LOCAL_BUSY')
            if action=='acquire':
                if row is None:
                    db.execute("INSERT INTO guard VALUES(1,?,'active',?,?)",(owner,deadline,'{}'))
                else:
                    # Preserve prior scientific checkpoint and completed table.
                    db.execute("UPDATE guard SET owner=?,status='active',deadline=? WHERE id=1",(owner,deadline))
        elif action=='live':
            if row!=(owner,'active',deadline) or datetime.fromisoformat(deadline)<=datetime.now(timezone.utc):
                raise ValueError('DUAL_LOCAL_LOST')
        elif action=='release':
            if row!=(owner,'active',deadline):
                raise ValueError('DUAL_LOCAL_LOST')
            db.execute("UPDATE guard SET status='released' WHERE id=1")
        elif action=='not_owned':
            if row is not None and row[:2]==(owner,'active'):
                raise ValueError('DUAL_LOCAL_ACTIVE')
        else:
            raise ValueError('DUAL_ACTION')
        db.commit()
    finally:
        db.close()


def dual_auth_check(api):
    # Authenticated read only. Never rerun a completed job to test login.
    _,q=dual_contents(api(DUAL_QUEUE))
    _,lease=dual_remote_lease(api)
    control_queue_summary(q,lease)
    return 'PASS'


def dual_remote_lease(api):
    return dual_contents(api(DUAL_LEASE_GET))


def dual_remote_write(api,sha,obj):
    data=base64.b64encode(json.dumps(obj,sort_keys=True,indent=2).encode('utf-8')+b'\n').decode('ascii')
    result=api(DUAL_LEASE,'PUT',{'message':'CTL-001 bounded operational lease pilot','branch':'coordination/lease','sha':sha,'content':data})
    if type(result) is not dict or not re.fullmatch(r'[0-9a-f]{40}',result.get('content',{}).get('sha','')):
        raise ValueError('DUAL_WRITE_RESPONSE')


def dual_owned(obj,owner,deadline,claim_pr=DUAL_PR):
    return (obj.get('schema_version')==1 and obj.get('status')=='active' and obj.get('owner')==owner and
            obj.get('claim_pr')==claim_pr and obj.get('task_ids')==['CTL-001'] and obj.get('expires_utc')==deadline)


def resume_file(parent,stage,kind):
    if type(stage) is not int or stage not in (1,2) or kind not in ('checkpoint','journal'):
        raise ValueError('RESUME_STAGE')
    return parent/('guarded_resume_%d_%s.local.json'%(stage,kind))


def resume_read(path):
    if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400 or not path.is_file():
        raise ValueError('RESUME_PATH')
    with path.open('rb') as f:
        raw=f.read(8193)
    if len(raw)>8192:
        raise ValueError('RESUME_LIMIT')
    value=json.loads(raw)
    if type(value) is not dict:
        raise ValueError('RESUME_SCHEMA')
    return value


def resume_db_identity(path):
    p=Path(path)
    local_folder(str(p.parent))
    st=p.lstat()
    if p.name.lower()!='run_guard.sqlite' or not stat.S_ISREG(st.st_mode) or p.is_symlink() or getattr(st,'st_file_attributes',0)&0x400:
        raise ValueError('RESUME_DB')
    return {'path':str(p.resolve()),'device':st.st_dev,'inode':st.st_ino}


def resume_expected_bars():
    # Independent formula for fixed invented one-minute rows. Minute 7
    # is absent, therefore the 5..9 window must not be fabricated.
    return [[i,100+i,106+i,99+i,105+i,15] for i in range(0,30,5) if i!=5]


def resume_checkpoint_read(parent,stage):
    obj=resume_read(resume_file(parent,stage,'checkpoint'))
    fields={'schema','protocol','scope','stage','db','bars'} if stage==1 else {'schema','protocol','scope','stage','db','previous_sha','pairs','sum'}
    if (set(obj)!=fields or obj['schema']!=1 or obj['protocol']!=RESUME_PROTOCOL or obj['scope']!='SYNTHETIC_ONLY' or
            obj['stage']!=stage or type(obj['db']) is not dict or set(obj['db'])!={'path','device','inode'}):
        raise ValueError('RESUME_CHECKPOINT')
    if stage==1 and obj['bars']!=resume_expected_bars():
        raise ValueError('RESUME_CHECKPOINT')
    if stage==2:
        previous=resume_checkpoint_read(parent,1)
        digest=hashlib.sha256(json.dumps(previous,sort_keys=True).encode('utf-8')).hexdigest()
        if obj['db']!=previous['db'] or obj['previous_sha']!=digest or obj['pairs']!=3 or obj['sum']!=15:
            raise ValueError('RESUME_CHECKPOINT')
    return obj


def resume_next(parent):
    prior=resume_read(parent/DUAL_JOURNAL)
    if prior.get('phase')!='RELEASED' or prior.get('status')!='PASS':
        raise ValueError('RESUME_PREREQUISITE')
    for stage in (1,2):
        journal=resume_file(parent,stage,'journal')
        checkpoint=resume_file(parent,stage,'checkpoint')
        if not journal.exists() and not checkpoint.exists():
            if stage==1 and (resume_file(parent,2,'journal').exists() or resume_file(parent,2,'checkpoint').exists()):
                raise ValueError('RESUME_ORDER')
            return stage
        if not journal.exists() or not checkpoint.exists():
            raise ValueError('RESUME_RECONCILE_REQUIRED')
        obj=resume_read(journal)
        if obj.get('phase')!='RELEASED' or obj.get('status')!='PASS' or obj.get('stage')!=stage:
            raise ValueError('RESUME_RECONCILE_REQUIRED')
        resume_checkpoint_read(parent,stage)
    return 0


def handoff_guard_read(identity,journal):
    # Read only the ownership metadata, not the private checkpoint or
    # completed research payloads. Never create a DB or acquire a lock.
    path=Path(identity['path'])
    if resume_db_identity(path)!=identity:
        raise ValueError('HANDOFF_DB_CHANGED')
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2,isolation_level=None)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA query_only=ON')
        if db.execute("SELECT type FROM sqlite_master WHERE name='guard'").fetchone()!=('table',):
            raise ValueError('HANDOFF_DB_SCHEMA')
        if [row[1] for row in db.execute('PRAGMA table_info(guard)')]!=['id','owner','status','deadline','checkpoint']:
            raise ValueError('HANDOFF_DB_SCHEMA')
        row=db.execute('SELECT owner,status,deadline FROM guard WHERE id=1').fetchone()
        if row!=(journal['owner'],'released',journal['deadline']):
            raise ValueError('HANDOFF_LOCAL_STATE')
    finally:
        db.close()


def handoff_summary(parent,api):
    parent=local_folder(str(parent))
    _,q=dual_contents(api(DUAL_QUEUE))
    sha,lease=dual_remote_lease(api)
    summary=control_queue_summary(q,lease)
    if summary['remote']!='OBSERVED_IDLE_NOT_ACQUIRED' or summary['task_status']!='blocked':
        raise ValueError('HANDOFF_REMOTE_OR_QUEUE')
    stage=resume_next(parent)
    if stage!=0:
        return {'status':'PENDING_SYNTHETIC','revision':summary['revision'],'finished_stages':stage-1}
    last=resume_read(resume_file(parent,2,'journal'))
    checkpoint=resume_checkpoint_read(parent,2)
    if (type(last.get('owner')) is not str or not re.fullmatch(r'ctl-runner-pilot-[0-9a-f]{32}',last['owner'])
            or type(last.get('deadline')) is not str):
        raise ValueError('HANDOFF_JOURNAL')
    # A newer release by another writer is not the same evidence.
    if (lease.get('last_owner')!=last['owner'] or lease.get('last_claim_pr')!=RESUME_PR or
            lease.get('last_result_commit')!=RESUME_HEAD):
        raise ValueError('HANDOFF_REMOTE_RELEASE')
    handoff_guard_read(checkpoint['db'],last)
    # Second observation bounds this report; not an atomic cross-store lock.
    _,now=dual_contents(api(DUAL_QUEUE))
    now_sha,now_lease=dual_remote_lease(api)
    if now!=q or now_sha!=sha or now_lease!=lease:
        raise ValueError('HANDOFF_STATE_CHANGED')
    handoff_guard_read(checkpoint['db'],last)
    return {'status':'READY_FOR_FRESH_AGENT_PROBE','revision':summary['revision'],'finished_stages':2}


def handoff_text(summary):
    if summary['status']=='PENDING_SYNTHETIC':
        return '引き継ぎ準備：人工工程 %d/2 / 未完了 / 研究実行ロック中'%summary['finished_stages']
    if summary['status']!='READY_FOR_FRESH_AGENT_PROBE':
        raise ValueError('HANDOFF_STATUS')
    return ('CTL-001 引き継ぎ報告（読取専用）\n'
            'リポジトリ：mibesamiti-png/Chappy-Trading-Lab / キュー revision '+str(summary['revision'])+'\n'
            '人工2/2工程：保存済み・再実行なし / PR #43\n'
            'メイン画面認証：読取成功 / 同一の選択済みDB・解放記録照合成功\n'
            '共有リース：空き応答・最終解放記録一致（未取得）\n'
            'CTL-002〜005：GitHub上で完了 / CTL-006：承認待ち / CTL-001：blocked\n'
            '次：別AIセッションから既存の状態・環境を確認する。完了済み工程を再実行しない。\n'
            '元Workの私有成果・共通DB同一性・別AI実行環境は未検証。\n'
            '研究実行ロック中 / 市場本体未読 / 2026年評価なし / スケジュールなし')


def resume_do_stage(parent,db_path,stage,live):
    live()
    identity=resume_db_identity(db_path)
    result={'schema':1,'protocol':RESUME_PROTOCOL,'scope':'SYNTHETIC_ONLY','stage':stage,'db':identity}
    if stage==1:
        rows=[(i,100+i,102+i,99+i,101+i,3) for i in range(30) if i!=7]
        aggregate=aggregate_session_rows(rows,30,5)
        result['bars']=[list(x) for x in aggregate['bars']]
        if result['bars']!=resume_expected_bars() or aggregate['missing_windows']!=1:
            raise ValueError('RESUME_AGGREGATION')
    elif stage==2:
        previous=resume_checkpoint_read(parent,1)
        if previous['db']!=identity:
            raise ValueError('RESUME_DB_CHANGED')
        bars=previous['bars']
        differences=[b[4]-a[4] for a,b in zip(bars,bars[1:]) if b[0]-a[0]==5]
        result.update(previous_sha=hashlib.sha256(json.dumps(previous,sort_keys=True).encode('utf-8')).hexdigest(),
                      pairs=len(differences),sum=sum(differences))
        if result['pairs']!=3 or result['sum']!=15:
            raise ValueError('RESUME_STATISTICS')
    else:
        raise ValueError('RESUME_STAGE')
    live()
    with resume_file(parent,stage,'checkpoint').open('xb') as f:
        f.write(json.dumps(result,sort_keys=True).encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    if resume_checkpoint_read(parent,stage)!=result:
        raise ValueError('RESUME_SAVE')
    live()


def dual_run(parent,db_path,api,notify=lambda *_:None,*,resume_stage=None):
    parent=local_folder(str(parent))
    if resume_stage is not None:
        if resume_next(parent)!=resume_stage:
            raise ValueError('RESUME_ORDER')
        if resume_stage==2 and resume_checkpoint_read(parent,1)['db']!=resume_db_identity(db_path):
            raise ValueError('RESUME_DB_CHANGED')
        claim_pr,claim_head=RESUME_PR,RESUME_HEAD
        dest=resume_file(parent,resume_stage,'journal')
    else:
        claim_pr,claim_head=DUAL_PR,DUAL_HEAD
        dest=parent/DUAL_JOURNAL
    if dest.exists():
        with dest.open('rb') as f:
            raw=f.read(4097)
        prior=json.loads(raw)
        if len(raw)>4096 or prior.get('status')!='PASS' or prior.get('phase')!='RELEASED':
            raise ValueError('DUAL_RECONCILE_REQUIRED')
        return 'PASS'
    _,q=dual_contents(api(DUAL_QUEUE))
    _,lease=dual_remote_lease(api)
    summary=control_queue_summary(q,lease)
    if summary['remote']!='OBSERVED_IDLE_NOT_ACQUIRED' or summary['task_status']!='blocked':
        raise ValueError('DUAL_QUEUE_OR_BUSY')
    pr=api(DUAL_BASE+'/pulls/'+str(claim_pr))
    if (pr.get('state')!='open' or pr.get('draft') is not True or pr.get('head',{}).get('sha')!=claim_head or
            pr.get('base',{}).get('ref')!='main' or pr.get('head',{}).get('repo',{}).get('full_name')!='mibesamiti-png/Chappy-Trading-Lab'):
        raise ValueError('DUAL_PR')
    claims=api(DUAL_BASE+'/pulls?state=open&per_page=100')
    if type(claims) is not list or len(claims)>=100 or any('CTL-001' in str(x.get('title','')).upper() and x.get('number') not in (4,5,6,7,41,43) for x in claims):
        raise ValueError('DUAL_OTHER_CLAIM')
    if control_checkpoint(parent,CONTROL_LAUNCH,control_evidence(parent),summary)!='REOPENED':
        raise ValueError('DUAL_RESTART_REQUIRED')
    owner='ctl-runner-pilot-'+os.urandom(16).hex()
    deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    dual_local_guard(db_path,owner,deadline,'idle')
    record={'schema':1,'owner':owner,'deadline':deadline,'phase':'PREPARED','status':'INCOMPLETE'}
    if resume_stage is not None:
        record['stage']=resume_stage
    with dest.open('xb') as f:
        f.write(json.dumps(record,sort_keys=True).encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    def save(phase,status='INCOMPLETE'):
        record.update(phase=phase,status=status)
        atomic(dest,json.dumps(record,sort_keys=True).encode('utf-8'))
        notify(phase)
    remote=False
    local=False
    reported=False
    try:
        sha,lease=dual_remote_lease(api)
        if control_queue_summary(q,lease)['remote']!='OBSERVED_IDLE_NOT_ACQUIRED':
            raise ValueError('DUAL_REMOTE_BUSY')
        claim=dict(lease)
        claim.update(status='active',owner=owner,claim_pr=claim_pr,task_ids=['CTL-001'],expires_utc=deadline)
        save('REMOTE_REQUEST')
        dual_remote_write(api,sha,claim)
        _,actual=dual_remote_lease(api)
        if not dual_owned(actual,owner,deadline,claim_pr):
            raise ValueError('DUAL_REMOTE_LOST')
        remote=True
        save('REMOTE_ACQUIRED')
        dual_local_guard(db_path,owner,deadline,'acquire')
        local=True
        save('LOCAL_ACQUIRED')
        def live():
            _,actual=dual_remote_lease(api)
            _,current_q=dual_contents(api(DUAL_QUEUE))
            if not dual_owned(actual,owner,deadline,claim_pr) or current_q!=q or datetime.fromisoformat(deadline)<=datetime.now(timezone.utc):
                raise ValueError('DUAL_REMOTE_LOST')
            dual_local_guard(db_path,owner,deadline,'live')
        live()
        if resume_stage is not None:
            resume_do_stage(parent,db_path,resume_stage,live)
        save('CHECKPOINT_SAVED')
        live()
        body=DUAL_STATUS_TEXT if resume_stage is None else ('CTL-001 synthetic guarded resume pilot: stage %d/2 checkpoint verified; release follows. No market research or holdout access.'%resume_stage)
        comment=api(DUAL_BASE+'/issues/'+str(claim_pr)+'/comments','POST',{'body':body})
        if type(comment) is not dict or type(comment.get('id')) is not int:
            raise ValueError('DUAL_REPORT')
        reported=True
    finally:
        # Ambiguous mutations stop; never release another owner's guard.
        if local:
            dual_local_guard(db_path,owner,deadline,'release')
            save('LOCAL_RELEASED')
        if remote:
            dual_local_guard(db_path,owner,deadline,'not_owned')
            sha,actual=dual_remote_lease(api)
            if not dual_owned(actual,owner,deadline,claim_pr):
                raise ValueError('DUAL_REMOTE_LOST')
            idle=dict(actual)
            idle.update(status='idle',owner=None,task_ids=[],expires_utc=None,last_owner=owner,
                        last_claim_pr=claim_pr,last_result_commit=claim_head,released_utc=datetime.now(timezone.utc).isoformat(),
                        last_run_status='Operational dual-guard pilot; no research or holdout access')
            idle.pop('claim_pr',None)
            dual_remote_write(api,sha,idle)
            _,verified=dual_remote_lease(api)
            if control_queue_summary(q,verified)['remote']!='OBSERVED_IDLE_NOT_ACQUIRED' or verified.get('last_owner')!=owner:
                raise ValueError('DUAL_RELEASE_UNVERIFIED')
            save('RELEASED','PASS' if local and reported else 'INCOMPLETE')
    if not (local and remote and reported):
        raise ValueError('DUAL_INCOMPLETE')
    return 'PASS'


# A fixed, local acceptance suite once per installed release.
DIAG_FILE='runner_diagnostics.local.json'
DIAG_LIMIT=16384
DIAG_STEPS=(('zip','人工ZIP・期間制限'),('parquet','既存Parquet環境'),
            ('ohlcv','人工OHLCV'),('aggregation','人工集計'),
            ('checkpoint','人工研究チェックポイント'),
            ('catalog','保存済みZIP目録・現行ファイル属性'),
            ('horizons','人工1・5・15・30分足集計'),
            ('session_map','人工取引セッション・UTC時刻対応'),
            ('calendar_fixture','人工カレンダー・限定SQL検査'),
            ('calendar_index','既存索引の2025年以前カレンダー'),
            ('statistics','人工記述統計・欠損境界検査'),
            ('pipeline','人工ZIP・Parquet・統計の統合検査'),
            ('source_gate','市場接続ロック・候補整合性検査'),
            ('prefix','人工Parquet行グループ・期間境界検査'),
            ('batch_adapter','人工Parquetバッチ・小数価格接続検査'),
            ('quality','保存済み月別選択の再現確認'))
DIAG_CODES=('PASS','SKIP_NOT_CONFIGURED','FAIL_TIMEOUT','FAIL_IO','FAIL_VALIDATION','FAIL_REPRODUCIBILITY','FAIL_INTERNAL')


def diagnostic_quality(parent):
    with (parent/'market_monthly_quality_selection.local.json').open('rb') as f:
        raw=f.read(QUALITY_RECEIPT_LIMIT+1)
    if len(raw)>QUALITY_RECEIPT_LIMIT:
        raise ValueError('DIAG_QUALITY_LIMIT')
    saved=json.loads(raw)
    if (type(saved) is not dict or saved.get('schema')!=1 or
            saved.get('scope')!='LOCAL_RETROSPECTIVE_MONTHLY_SELECTION' or
            saved.get('research_access')!='LOCKED' or saved.get('market_member_reads')!=0):
        raise ValueError('DIAG_QUALITY_RECEIPT')
    actual=quality_index_run(parent,saved['requested_count'],saved['seed'],saved['min_months'],saved['min_coverage_bps'],persist=False)
    if actual!=saved:
        raise ValueError('DIAG_REPRODUCIBILITY')


def diagnostic_read(parent,version):
    try:
        with (parent/DIAG_FILE).open('rb') as f:
            raw=f.read(DIAG_LIMIT+1)
    except FileNotFoundError:
        return None
    if len(raw)>DIAG_LIMIT:
        raise ValueError('DIAG_LIMIT')
    report=json.loads(raw)
    if (type(report) is not dict or report.get('schema')!=1 or
            report.get('scope')!='LOCAL_DEBUG_ONLY' or report.get('market_member_reads')!=0 or
            report.get('research_access')!='LOCKED'):
        raise ValueError('DIAG_SCHEMA')
    if report.get('version')!=version:
        return None
    rows=report.get('steps')
    if type(rows) is not list or len(rows)!=len(DIAG_STEPS):
        raise ValueError('DIAG_SCHEMA')
    for row,(key,_) in zip(rows,DIAG_STEPS):
        if (type(row) is not dict or set(row)!={'key','status','ms'} or row['key']!=key or
                row['status'] not in DIAG_CODES or type(row['ms']) is not int or not 0<=row['ms']<=86400000):
            raise ValueError('DIAG_SCHEMA')
    return report


def diagnostic_text(report):
    # Render only fixed labels, enumerated codes and numeric timings.
    lines=['Chappy Trading Lab '+report['version']+' 自動デバッグ報告',
           'この自動検査で市場ZIP本体未読 / 2026年評価なし / 研究実行ロック中']
    for row,(_,label) in zip(report['steps'],DIAG_STEPS):
        lines.append(f"{label}: {row['status']} ({row['ms']/1000:.2f}秒)")
    lines.append(f"成功 {sum(r['status']=='PASS' for r in report['steps'])}/{len(DIAG_STEPS)} / 未設定 {sum(r['status']=='SKIP_NOT_CONFIGURED' for r in report['steps'])}")
    return '\n'.join(lines)


def diagnostic_run(parent,version,notify=lambda *_:None):
    parent=local_folder(str(parent))
    def check_checkpoint():
        if not (parent/SYNTH_RUN_FILE).is_file():
            raise FileNotFoundError()
        if synthetic_run_read(parent)['status']!='COMPLETE':
            raise ValueError('DIAG_CHECKPOINT_INCOMPLETE')
    actions={
        'zip':lambda:synthetic_probe_checkpoint(parent/'synthetic_zip_probe.local.json'),
        'parquet':lambda:parquet_runtime(parent,False),
        'ohlcv':lambda:synthetic_ohlcv_checkpoint(parent),
        'aggregation':synthetic_aggregation,
        'checkpoint':check_checkpoint,
        'catalog':lambda:load_market_candidates(parent),
        'horizons':lambda:synthetic_horizon_checkpoint(parent),
        'session_map':lambda:synthetic_session_mapping_checkpoint(parent),
        'calendar_fixture':synthetic_calendar_probe,
        'calendar_index':lambda:calendar_index_checkpoint(parent),
        'statistics':lambda:synthetic_statistics_checkpoint(parent),
        'pipeline':lambda:synthetic_integrated_checkpoint(parent),
        'source_gate':lambda:source_gate_receipt(parent),
        'prefix':lambda:synthetic_prefix_checkpoint(parent),
        'batch_adapter':lambda:synthetic_batch_adapter_checkpoint(parent),
        'quality':lambda:diagnostic_quality(parent),
    }
    rows=[]
    for key,label in DIAG_STEPS:
        notify(label)
        start=time.monotonic()
        status='PASS'
        try:
            # Missing optional artifacts are not counted as success.
            if key in ('parquet','ohlcv','pipeline','prefix','batch_adapter') and not (parent/'ctl_pyarrow_26_0_1').is_dir():
                raise FileNotFoundError()
            if key=='catalog' and not (parent/'market_zip_catalog.local.json').is_file():
                raise FileNotFoundError()
            if key=='calendar_index' and not (parent/'existing_index_column_map.local.json').is_file():
                raise FileNotFoundError()
            if key=='source_gate' and not all((parent/name).is_file() for name in ('existing_index_column_map.local.json','market_monthly_quality_selection.local.json',CALENDAR_RECEIPT)):
                raise FileNotFoundError()
            if key=='quality' and not (parent/'market_monthly_quality_selection.local.json').is_file():
                raise FileNotFoundError()
            actions[key]()
        except FileNotFoundError:
            status='SKIP_NOT_CONFIGURED' if key in ('parquet','ohlcv','checkpoint','catalog','quality','calendar_index','pipeline','source_gate','prefix','batch_adapter') else 'FAIL_IO'
        except subprocess.TimeoutExpired:
            status='FAIL_TIMEOUT'
        except (OSError,subprocess.CalledProcessError):
            status='FAIL_IO'
        except (ValueError,sqlite3.Error,TypeError,KeyError,AttributeError,RecursionError) as exc:
            status='FAIL_REPRODUCIBILITY' if str(exc)=='DIAG_REPRODUCIBILITY' else 'FAIL_VALIDATION'
        except Exception:
            status='FAIL_INTERNAL'
        rows.append({'key':key,'status':status,'ms':max(0,int((time.monotonic()-start)*1000))})
    report={'schema':1,'scope':'LOCAL_DEBUG_ONLY','version':version,
            'market_member_reads':0,'research_access':'LOCKED','steps':rows}
    raw=json.dumps(report,sort_keys=True).encode('utf-8')
    atomic(parent/DIAG_FILE,raw)
    if diagnostic_read(parent,version)!=report:
        raise ValueError('DIAG_SAVE_FAILED')
    return report


def install_runner_controls(owner):
    # Reserve the bottom strip before the expanding log/body receives space.
    # Keep the base desktop's geometry manager, and never put research buttons
    # in its already crowded link/update toolbar.
    root=owner.root
    packed=root.pack_slaves()
    gridded=root.grid_slaves()
    footer=ttk.Frame(root,padding=(8,4,8,6))
    if gridded:
        columns,rows=root.grid_size()
        footer.grid(row=rows,column=0,columnspan=max(1,columns),sticky='ew')
    elif packed:
        footer.pack(side='bottom',fill='x',before=packed[0])
    else:
        footer.pack(side='bottom',fill='x')
    controls=ttk.Frame(footer)
    controls.pack(fill='x')
    items=(
        ('folder_btn','研究データ設定',owner.configure_folders),
        ('probe_btn','研究基盤テスト',owner.run_research_probe),
        ('ohlcv_btn','OHLCV人工検査',owner.run_ohlcv_probe),
        ('parquet_btn','Parquet環境',owner.configure_parquet),
        ('catalog_btn','市場ZIP目録',owner.run_market_catalog),
        ('selection_btn','銘柄候補',owner.open_market_selection),
        ('synthetic_run_btn','人工研究実行',owner.run_synthetic_research),
        ('footer_probe_btn','実Parquet構造',owner.run_footer_probe),
    )
    for i,(attr,label,command) in enumerate(items):
        btn=ttk.Button(controls,text=label,command=command)
        btn.grid(row=i//4,column=i%4,sticky='ew',padx=2,pady=2)
        setattr(owner,attr,btn)
    for column in range(4):
        controls.columnconfigure(column,weight=1,uniform='research')
    # A separate full-width row guarantees the report is right-aligned and
    # does not compete with any of the research or update controls.
    report_row=ttk.Frame(footer)
    report_row.pack(fill='x',pady=(4,0))
    owner.batch_adapter_btn=ttk.Button(report_row,text='実データ集計接続',command=owner.run_batch_adapter_probe)
    owner.batch_adapter_btn.pack(side='left',padx=2)
    owner.control_plane_btn=ttk.Button(report_row,text='研究実行管理',command=owner.run_control_plane)
    owner.control_plane_btn.pack(side='left',padx=2)
    owner.dual_guard_btn=ttk.Button(report_row,text='排他・再開テスト',command=owner.run_dual_guard)
    owner.dual_guard_btn.pack(side='left',padx=2)
    owner.diag_btn=ttk.Button(report_row,text='デバッグ報告',command=owner.open_diagnostics)
    owner.diag_btn.pack(side='right',padx=2)
    owner.runner_footer=footer


class DataDesktop(UpdateDesktop):
    def __init__(self, *args, **kwargs):
        self.folder_dialog = None
        self.parquet_busy = False
        self.parquet_results = queue.Queue()
        self.catalog_busy = False
        self.catalog_results = queue.Queue()
        super().__init__(*args, **kwargs)
        self.diag_results=queue.Queue()
        install_runner_controls(self)
        self.root.after(800,self.auto_diagnostics)

    def run_footer_probe(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        parent=Path(self.path).parent
        if not (parent/FOOTER_REPORT).is_file():
            if not messagebox.askyesno('実Parquet構造','保存済み候補の1銘柄だけ（32MiB以下）をメモリ展開し、構造情報を確認します。2026年の圧縮バイト・フッターに触れる場合がありますが、データ行の復号、研究・評価、展開ファイル保存は行いません。実行しますか？',parent=self.root):
                return
        self.parquet_busy=True
        self.footer_probe_btn.configure(state='disabled')
        results=queue.Queue()
        def run():
            try:
                results.put((True,footer_report_text(market_footer_probe(parent))))
            except Exception:
                results.put((False,'構造確認停止：未設定・不一致・容量超過・既試行・読み取り失敗のいずれか。再試行は自動実行しません。研究実行ロック中。'))
        def poll():
            try:
                ok,result=results.get_nowait()
            except queue.Empty:
                self.root.after(150,poll)
                return
            self.parquet_busy=False
            self.footer_probe_btn.configure(state='normal')
            self.log(result)
            if ok:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(result)
                    self.log('構造確認報告をクリップボードにコピーしました。')
                except tk.TclError:
                    self.log('構造確認報告のコピーに失敗しました。')
        self.log('実Parquet構造確認：1候補・行復号なし。')
        threading.Thread(target=run,daemon=False).start()
        self.root.after(150,poll)

    def run_batch_adapter_probe(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        parent=Path(self.path).parent
        integration=(parent/BATCH_ADAPTER_REPORT).is_file()
        dest=parent/(SESSION_CONNECTION_REPORT if integration else BATCH_ADAPTER_REPORT)
        if not dest.is_file() and not messagebox.askyesno('実データ接続検査',
                '既存候補1銘柄の最初の観測済み取引日だけを1・5・15・30分足へ接続します。集計の整合性確認のみ。2026年の価格分析・科学研究・結果値の外部出力は行いません。' if integration else
                '既存候補1銘柄だけをメモリ展開し、日時順序と2025年以前のOHLCV形式を確認します。2026年日時列や境界の圧縮ページは内部復号される場合があります。2026年価格の分析・評価や科学研究は実行しません。',parent=self.root):
            return
        self.parquet_busy=True
        self.batch_adapter_btn.configure(state='disabled')
        results=queue.Queue()
        def run():
            try:
                report=market_batch_adapter_probe(parent,integration=integration)
                if integration:
                    results.put('実データ集計接続（1候補・1取引日）\n結果：'+report['status']+'\n1・5・15・30分足の整合性検査 / 研究実行ロック中\n2026年評価なし / 物理隔離未保証 / カレンダー完全性未検証\n価格・銘柄・日時・集計値の出力なし')
                else:
                    results.put(batch_adapter_text(report))
            except Exception:
                results.put('実データ接続検査：停止（設定・既試行・整合性・読み取りを確認）。研究実行ロック中。')
        def poll():
            try:
                result=results.get_nowait()
            except queue.Empty:
                self.root.after(150,poll)
                return
            self.parquet_busy=False
            self.batch_adapter_btn.configure(state='normal')
            self.log(result)
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(result)
                self.log('接続検査報告をクリップボードにコピーしました。')
            except tk.TclError:
                self.log('接続検査報告のコピーに失敗しました。')
        threading.Thread(target=run,daemon=False).start()
        self.root.after(150,poll)

    def run_control_plane(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        if self.busy or self.resident:
            self.log('常駐または既存ジョブを停止してから研究実行管理を確認してください。')
            return
        parent=Path(self.path).parent
        handoff=(parent/DUAL_JOURNAL).exists()
        token=self.get_token() if handoff else None
        if handoff and not token:
            return
        self.parquet_busy=True
        self.busy=True
        self.buttons()
        self.control_plane_btn.configure(state='disabled')
        results=queue.Queue()
        def run():
            try:
                if handoff:
                    results.put(handoff_text(handoff_summary(parent,lambda endpoint:dual_api(endpoint,token=token))))
                else:
                    results.put(control_plane_text(control_plane_run(parent)))
            except Exception:
                results.put('研究実行管理：停止（GitHub応答・保存済み証拠・ローカル状態の確認が必要）。研究実行ロック中。')
        def poll():
            try:
                result=results.get_nowait()
            except queue.Empty:
                self.root.after(150,poll)
                return
            self.parquet_busy=False
            self.busy=False
            self.buttons()
            self.control_plane_btn.configure(state='normal')
            self.log(result)
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(result)
            except tk.TclError:
                self.log('研究実行管理報告のコピーに失敗しました。')
        threading.Thread(target=run,daemon=False).start()
        self.root.after(150,poll)

    def run_dual_guard(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        if self.busy or self.resident:
            self.log('常駐または既存ジョブを停止してから排他・再開テストを実行してください。')
            return
        parent=Path(self.path).parent
        stage=None
        selected=None
        if (parent/DUAL_JOURNAL).exists():
            try:
                stage=resume_next(parent)
                if stage==2:
                    selected=resume_checkpoint_read(parent,1)['db']['path']
            except Exception:
                self.log('排他・再開テスト：中断または不整合。自動再取得・解放しません。')
                return
        if stage!=0:
            detail=('人工ジョブ第%d工程だけを実行し保存・解放します。市場データ研究は行いません。'%stage if stage else
                    '既存の共通研究DB run_guard.sqlite とGitHub共有リースを使用し、取得・保存・解放の試験を1回行います。')
            if not messagebox.askyesno('排他・再開テスト',detail,parent=self.root):
                return
            if selected is None:
                selected=filedialog.askopenfilename(parent=self.root,title='既存の共通研究DBを選択',filetypes=[('共通研究DB','run_guard.sqlite')])
            if not selected:
                return
        # Use the exact existing desktop credential API, on the Tk thread.
        # DPAPI retention, edits and clear remain controlled by the main UI.
        token=self.get_token()
        if not token:
            return
        self.parquet_busy=True
        self.busy=True
        self.buttons()
        self.dual_guard_btn.configure(state='disabled')
        results=queue.Queue()
        def run():
            try:
                api=lambda endpoint,method='GET',body=None:dual_api(endpoint,method,body,token=token)
                if stage==0:
                    dual_auth_check(api)
                    result='メイン画面の認証再利用：PASS（読取専用） / 人工2/2工程完了・再実行なし'
                else:
                    dual_run(parent,selected,api,lambda phase:results.put(('progress',phase)),resume_stage=stage)
                    if stage is None:
                        result='排他実行権テスト：PASS / 共有CAS・ローカル取得・保存・解放確認'
                    else:
                        result='排他・再開テスト：PASS / 人工%d/2工程保存・実行権解放 / '%stage+('次回は第2工程のみ' if stage==1 else '第1工程再実行なし・完了')
                results.put(('done',result+' / 研究実行ロック中 / 2026年評価なし'))
            except Exception:
                results.put(('done','排他実行権テスト：停止（認証・DB・共有実行権・中断記録を確認）。研究実行ロック中。'))
        def poll():
            try:
                kind,result=results.get_nowait()
            except queue.Empty:
                self.root.after(150,poll)
                return
            self.log(result)
            if kind=='progress':
                self.root.after(150,poll)
                return
            self.parquet_busy=False
            self.busy=False
            self.buttons()
            self.dual_guard_btn.configure(state='normal')
            self.root.clipboard_clear()
            self.root.clipboard_append(result)
        threading.Thread(target=run,daemon=False).start()
        self.root.after(150,poll)

    def auto_diagnostics(self):
        if self.closing:
            return
        if self.folder_dialog is not None or self.parquet_busy or self.catalog_busy:
            self.root.after(1000,self.auto_diagnostics)
            return
        try:
            if diagnostic_read(Path(self.path).parent,VERSION) is not None:
                return
        except (OSError,ValueError,TypeError,KeyError,RecursionError):
            self.log('旧デバッグ報告を検証できません。今回の検査を実施します。')
        self.start_diagnostics()

    def start_diagnostics(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        self.parquet_busy=True
        self.diag_btn.configure(state='disabled')
        parent=Path(self.path).parent
        self.log('バージョン '+VERSION+' の自動デバッグ開始。')
        def run():
            try:
                result=diagnostic_run(parent,VERSION,lambda label:self.diag_results.put(('progress',label)))
                self.diag_results.put(('done',result))
            except Exception:
                self.diag_results.put(('failed',None))
        threading.Thread(target=run,daemon=False).start()
        self.root.after(200,self.poll_diagnostics)

    def copy_diagnostics(self,report):
        self.root.clipboard_clear()
        status=update_probe_text(self.last_update_probe) if self.last_update_probe is not None else '更新通信：今回の起動では未確認'
        self.root.clipboard_append(diagnostic_text(report)+'\n'+status)

    def poll_diagnostics(self):
        while True:
            try:
                kind,result=self.diag_results.get_nowait()
            except queue.Empty:
                self.root.after(200,self.poll_diagnostics)
                return
            if kind=='progress':
                self.log('自動デバッグ：'+result)
                continue
            self.parquet_busy=False
            self.diag_btn.configure(state='normal')
            if kind=='done':
                self.log('自動デバッグ終了。報告をPC内に保存しました。')
                try:
                    self.copy_diagnostics(result)
                    self.log('報告をクリップボードにコピーしました。チャットへ貼り付けできます。')
                except tk.TclError:
                    self.log('自動コピーできませんでした。デバッグ報告からコピーできます。')
            else:
                self.log('自動デバッグ報告の保存に失敗しました。')
            return

    def open_diagnostics(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        try:
            report=diagnostic_read(Path(self.path).parent,VERSION)
        except (OSError,ValueError,TypeError,KeyError,RecursionError):
            report=None
        if report is None:
            self.start_diagnostics()
            return
        win=tk.Toplevel(self.root)
        self.folder_dialog=win
        win.title('自動デバッグ報告')
        win.transient(self.root)
        pane=ttk.Frame(win,padding=12)
        pane.pack(fill='both',expand=True)
        ttk.Label(pane,text=diagnostic_text(report),justify='left').pack(anchor='w',pady=8)
        def close():
            self.folder_dialog=None
            win.destroy()
        def rerun():
            close()
            self.start_diagnostics()
        ttk.Button(pane,text='コピー',command=lambda:self.copy_diagnostics(report)).pack(side='left')
        ttk.Button(pane,text='再検査',command=rerun).pack(side='left',padx=5)
        ttk.Button(pane,text='閉じる',command=close).pack(side='right')
        win.protocol('WM_DELETE_WINDOW',close)
        win.grab_set()

    def open_market_selection(self):
        if self.closing or self.catalog_busy or self.parquet_busy or self.folder_dialog is not None:
            return
        parent = Path(self.path).parent
        try:
            digest, rows = load_market_candidates(parent)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            self.log('目録が未作成・変更済み、または不正です。市場ZIP目録を再作成してください。')
            return
        dialog = tk.Toplevel(self.root)
        self.folder_dialog = dialog
        dialog.title('銘柄候補（ローカル目録のみ）')
        dialog.geometry('800x570')
        dialog.transient(self.root)
        panel = ttk.Frame(dialog, padding=12)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Parquet候補名を検索・選択できます。期間未検証のため実データ読み取りは禁止。').pack(anchor='w')
        query = tk.StringVar()
        ttk.Entry(panel, textvariable=query).pack(fill='x', pady=6)
        table = ttk.Treeview(panel, columns=('archive','member','size'), show='headings', selectmode='extended')
        for col, title, width in [('archive','ZIP',55),('member','候補ファイル名',500),('size','バイト数',130)]:
            table.heading(col, text=title)
            table.column(col, width=width)
        scroll = ttk.Scrollbar(panel, command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        table.pack(fill='both', expand=True)
        status = tk.StringVar()
        def refresh(*_):
            table.delete(*table.get_children())
            needle=query.get().casefold()
            matches=[(i,r) for i,r in enumerate(rows) if needle in r['member'].casefold()]
            for i,r in matches[:2000]:
                table.insert('', 'end', iid=str(i), values=(r['archive_index']+1,r['member'],r['size']))
            status.set(f'一致 {len(matches)}件（表示上限2000件）／研究利用ロック中')
        query.trace_add('write',refresh)
        refresh()
        def save():
            try:
                count=save_market_selection(parent,digest,[rows[int(i)] for i in table.selection()])
                status.set(f'{count}件の選択をPC内に保存。読み取りは未許可。')
            except (OSError, ValueError, TypeError, KeyError, RecursionError):
                status.set('保存失敗。目録を再作成し、1～128件を選択してください。')
        def close():
            self.folder_dialog=None
            dialog.destroy()
        ttk.Label(panel,textvariable=status).pack(anchor='w',pady=6)
        ttk.Button(panel,text='選択を保存',command=save).pack(side='left')
        ttk.Button(panel,text='自動選択',command=lambda: self.open_auto_selection(dialog,parent,digest)).pack(side='left',padx=6)
        ttk.Button(panel,text='閉じる',command=close).pack(side='left',padx=6)
        dialog.protocol('WM_DELETE_WINDOW',close)
        dialog.grab_set()

    def open_auto_selection(self, owner, parent, digest):
        dialog=tk.Toplevel(owner)
        dialog.title('研究候補の自動選択（本体未読）')
        dialog.transient(owner)
        panel=ttk.Frame(dialog,padding=12)
        panel.pack(fill='both',expand=True)
        mode=tk.StringVar(value='seeded')
        count=tk.StringVar(value='32')
        seed=tk.StringVar(value='20251127')
        batch=tk.StringVar(value='0')
        ttk.Label(panel,text='全目録を対象に候補を選びます。研究実行・売買判断は行いません。',wraplength=420).pack(anchor='w')
        ttk.Radiobutton(panel,text='再現可能な無作為抽出',variable=mode,value='seeded').pack(anchor='w')
        ttk.Radiobutton(panel,text='全候補の順次処理用',variable=mode,value='sequential').pack(anchor='w')
        for label,var in [('1バッチ件数（1～128）',count),('乱数シード（0以上）',seed),('バッチ番号（0開始）',batch)]:
            ttk.Label(panel,text=label).pack(anchor='w')
            ttk.Entry(panel,textvariable=var).pack(fill='x')
        status=tk.StringVar(value='同じ目録・条件なら同じ候補になります。')
        ttk.Label(panel,textvariable=status,wraplength=420).pack(anchor='w',pady=8)
        def run():
            try:
                plan=save_auto_market_batch(parent,digest,mode.get(),int(count.get()),int(seed.get()),int(batch.get()))
                next_text='終了' if plan['next_batch'] is None else str(plan['next_batch'])
                status.set(f"{plan['selected_count']}件保存。次バッチ：{next_text}。研究利用ロック中。")
                if plan['next_batch'] is not None:
                    batch.set(str(plan['next_batch']))
            except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError):
                status.set('選択失敗または全候補終了。条件・目録を確認してください。')
        def close():
            dialog.destroy()
            owner.grab_set()
        ttk.Button(panel,text='自動選択・保存',command=run).pack(side='left')
        ttk.Button(panel,text='計画を作成・再開',command=lambda: self.open_research_plan(dialog,parent,digest,mode.get(),count.get(),seed.get())).pack(side='left',padx=5)
        ttk.Button(panel,text='閉じる',command=close).pack(side='right')
        dialog.protocol('WM_DELETE_WINDOW',close)
        dialog.grab_set()

    def open_research_plan(self, owner, parent, digest, mode, count, seed):
        try:
            p=plan_read(parent) if (parent / PLAN_FILE).exists() else plan_create(parent,digest,mode,int(count),int(seed))
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError):
            messagebox.showerror('研究準備計画','計画を読み込めません。目録変更または設定不正の可能性があります。既存計画は上書きしません。',parent=owner)
            return
        dialog=tk.Toplevel(owner)
        dialog.title('研究準備計画（本体未読）')
        dialog.transient(owner)
        panel=ttk.Frame(dialog,padding=12)
        panel.pack(fill='both',expand=True)
        status=tk.StringVar()
        ttk.Label(panel,text='保存済み条件で候補を順次準備します。研究実行・データ本体読み取りは行いません。',wraplength=430).pack(anchor='w')
        ttk.Label(panel,textvariable=status,wraplength=430).pack(anchor='w',pady=8)
        def show(state):
            status.set(f"準備済み：{state['prepared_count']}/{state['universe_size']}候補\nバッチ：{state['next_batch']}/{state['total_batches']}\n方式：{state['mode']} / 件数：{state['batch_size']} / seed：{state['seed']}\n研究実行：0件（ロック中）")
            progress.configure(maximum=state['universe_size'],value=state['prepared_count'])
            step_btn.configure(state='disabled' if state['status']=='COMPLETE' else 'normal')
        progress=ttk.Progressbar(panel,length=400)
        progress.pack(fill='x')
        def advance():
            try:
                show(plan_step(parent))
            except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError):
                status.set('準備失敗。計画を進めず、保存状態を確認してください。')
                step_btn.configure(state='disabled')
        step_btn=ttk.Button(panel,text='次バッチを準備',command=advance)
        step_btn.pack(side='left',pady=8)
        def close():
            dialog.destroy()
            owner.grab_set()
        ttk.Button(panel,text='閉じる',command=close).pack(side='right')
        dialog.protocol('WM_DELETE_WINDOW',close)
        show(p)
        dialog.grab_set()

    def run_synthetic_research(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        if not messagebox.askyesno('人工研究実行','固定の人工研究3工程を実行・再開します。完了工程は再実行しません。市場ZIPと2026封印データにはアクセスしません。',parent=self.root):
            return
        self.parquet_busy=True
        self.synthetic_run_btn.configure(state='disabled')
        parent=Path(self.path).parent
        self.log('人工研究の実行・再開を開始しました。')
        def run():
            try:
                state=synthetic_run_execute(parent)
                result=f"人工研究実行成功：{len(state['results'])}/3工程完了・結果保存・再開確認。"
            except Exception:
                result='人工研究実行停止。保存済み工程は維持。Parquet専用環境とチェックポイントを確認してください。'
            self.parquet_results.put(result)
        threading.Thread(target=run,daemon=False).start()
        self.root.after(250,self.poll_parquet)

    def run_ohlcv_probe(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        self.parquet_busy=True
        self.ohlcv_btn.configure(state='disabled')
        parent=Path(self.path).parent
        def run():
            try:
                synthetic_ohlcv_checkpoint(parent)
                result='人工OHLCV検査成功：欠損・重複・時刻・価格整合・期間制限・保存。'
            except Exception:
                result='人工OHLCV検査失敗。Parquet専用環境を確認してください。'
            self.parquet_results.put(result)
        threading.Thread(target=run,daemon=False).start()
        self.root.after(250,self.poll_parquet)

    def run_market_catalog(self):
        if self.closing or self.catalog_busy or self.parquet_busy or self.folder_dialog is not None:
            return
        if not messagebox.askyesno('市場ZIP目録', '登録済みZIPの中央ディレクトリ（名前・サイズ等）のみを読みます。\n中身は展開せず、研究利用はロックのままです。\n目録はPC内だけに保存します。実行しますか？', parent=self.root):
            return
        parent = Path(self.path).parent
        self.catalog_busy = True
        self.catalog_btn.configure(state='disabled')
        self.log('市場ZIP目録の確認開始。メンバー本体は読みません。')
        def run():
            try:
                result = (True, catalog_registered(parent))
            except Exception as exc:
                code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'CATALOG_[A-Z0-9_]+', str(exc)) else 'CATALOG_IO_OR_FORMAT'
                result = (False, code)
            self.catalog_results.put(result)
        threading.Thread(target=run, daemon=False).start()
        self.root.after(250, self.poll_catalog)

    def poll_catalog(self):
        try:
            ok, result = self.catalog_results.get_nowait()
        except queue.Empty:
            self.root.after(250, self.poll_catalog)
            return
        self.catalog_busy = False
        self.catalog_btn.configure(state='normal')
        if ok:
            archives, entries, candidates = result
            # Detailed counts and names stay on the local GUI, not in the runner log.
            messagebox.showinfo('市場ZIP目録完了', f'ZIP：{archives}件\n目録：{entries}件\nParquet候補：{candidates}件\n本体読み取り：0件\n研究利用：ロック中\n目録はPC内に保存しました。', parent=self.root)
            self.log('市場ZIP目録の保存再読込成功。本体未読・研究利用ロック中。')
        else:
            self.log('市場ZIP目録失敗：' + result + '。研究利用ロック中。')

    def configure_parquet(self):
        if self.closing or self.parquet_busy or self.catalog_busy or self.folder_dialog is not None:
            return
        parent = Path(self.path).parent
        install = messagebox.askyesnocancel('Parquet専用環境', 'はい：専用環境へPyArrow 26.0.1をインストールして人工テスト\nいいえ：既存の専用環境で人工テストのみ\nキャンセル：何もしない\n実市場ZIPは開きません。', parent=self.root)
        if install is None:
            return
        self.parquet_busy = True
        self.parquet_btn.configure(state='disabled')
        self.log('Parquet専用環境の処理を開始しました。')
        def run():
            try:
                parquet_runtime(parent, install)
                result = 'Parquet人工テスト成功：専用環境・ZIP64メンバー・期間制限・保存再読込。'
            except subprocess.TimeoutExpired:
                result = 'Parquet処理タイムアウト。専用環境から再試行できます。'
            except subprocess.CalledProcessError:
                result = 'Parquet導入または人工テスト失敗。Python環境・通信・空き容量を確認してください。'
            except (OSError, ValueError, RuntimeError, TypeError, UnicodeError):
                result = 'Parquet専用環境または保存確認に失敗しました。'
            self.parquet_results.put(result)
        threading.Thread(target=run, daemon=False).start()
        self.root.after(250, self.poll_parquet)

    def poll_parquet(self):
        try:
            result = self.parquet_results.get_nowait()
        except queue.Empty:
            self.root.after(250, self.poll_parquet)
            return
        self.parquet_busy = False
        self.parquet_btn.configure(state='normal')
        self.ohlcv_btn.configure(state='normal')
        self.synthetic_run_btn.configure(state='normal')
        self.log(result + ' 登録市場ZIPは未読。')

    def run_research_probe(self):
        if self.closing or self.folder_dialog is not None or self.catalog_busy or self.parquet_busy:
            return
        try:
            result = synthetic_probe_checkpoint(Path(self.path).parent / 'synthetic_zip_probe.local.json')
            self.log('人工ZIPテスト成功：選択読取・期間制限・集計・保存再読込。')
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, UnicodeError, TypeError):
            self.log('人工ZIPテスト失敗。実データは開いていません。')
            return
        try:
            found = importlib.util.find_spec('pyarrow') is not None
        except (ImportError, ValueError):
            found = False
        self.log('PyArrow：' + ('候補あり（動作未検証）' if found else '未検出') + '。登録市場ZIPは未読。')

    def update_tick(self):
        if self.folder_dialog is not None or self.parquet_busy or self.catalog_busy:
            return False
        return super().update_tick()

    def configure_folders(self):
        if self.closing or self.folder_dialog is not None or self.catalog_busy or self.parquet_busy:
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
        def monthly_quality_selection():
            win=tk.Toplevel(dialog)
            win.title('月別索引による研究候補選択（ローカル）')
            win.transient(dialog)
            pane=ttk.Frame(win,padding=12)
            pane.pack(fill='both',expand=True)
            ttk.Label(pane,text='2022年3月～2025年12月の月別索引を論理的に限定して参照します。市場ZIP本体は未読。混在SQLiteの物理分離とデータ由来の独立性は未証明です。',wraplength=480).pack(anchor='w')
            n=tk.StringVar(value='32')
            seed=tk.StringVar(value='20251127')
            months=tk.StringVar(value='12')
            bps=tk.StringVar(value='9000')
            for label,var in [('抽出上限（1～128）',n),('乱数シード',seed),('最少観測月数（1～46）',months),('最少収録率（9000=90%）',bps)]:
                ttk.Label(pane,text=label).pack(anchor='w')
                ttk.Entry(pane,textvariable=var).pack(fill='x')
            status=tk.StringVar(value='条件を固定して候補を選択します。研究実行はロック中。')
            ttk.Label(pane,textvariable=status,wraplength=480).pack(anchor='w',pady=8)
            def run():
                if not messagebox.askyesno('月別索引参照','既存索引の識別用列と2025年以前の月別集計だけを参照し、候補をPC内に保存します。実行しますか？',parent=win):
                    return
                try:
                    result=quality_index_run(Path(self.path).parent,int(n.get()),int(seed.get()),int(months.get()),int(bps.get()))
                    status.set(f"名前候補：{result['candidate_count']}件\n名前・サイズ・CRC一致：{result['metadata_matched_count']}件\n品質条件適合：{result['eligible_count']}件 / 選択：{len(result['selected'])}件\n研究利用ロック中（本体未読）")
                    self.log('月別索引の限定参照・研究候補選択保存成功。本体未読・研究利用ロック中。')
                except (OSError,ValueError,sqlite3.Error,TypeError,KeyError,AttributeError,RecursionError):
                    status.set('選択停止。索引・目録・列構造・入力条件を確認してください。実データ本体は未読。')
            def close():
                win.destroy()
                dialog.grab_set()
            ttk.Button(pane,text='限定参照・自動選択',command=run).pack(side='left')
            ttk.Button(pane,text='閉じる',command=close).pack(side='right')
            win.protocol('WM_DELETE_WINDOW',close)
            win.grab_set()
        def inspect_index_columns():
            if not messagebox.askyesno('既存索引・列構造','保存済み索引の列名とZIP目録上の銘柄名候補を確認します。データ行・市場ZIP本体は読みません。',parent=dialog):
                return
            try:
                result=index_column_map(Path(self.path).parent)
                window=tk.Toplevel(dialog)
                window.title('既存索引・列構造（ローカルのみ）')
                window.geometry('720x540')
                window.transient(dialog)
                panel2=ttk.Frame(window,padding=10)
                panel2.pack(fill='both',expand=True)
                report=tk.Text(panel2,wrap='word')
                scroll2=ttk.Scrollbar(panel2,command=report.yview)
                report.configure(yscrollcommand=scroll2.set)
                scroll2.pack(side='right',fill='y')
                report.pack(fill='both',expand=True)
                lines=[f"ファイル名からの銘柄候補：{len(result['filename_candidates'])}件",
                       f"曖昧：{result['ambiguous_filename_count']}件 / 形式外：{result['unrecognized_filename_count']}件",
                       "実際の索引行との照合：未実施 / 研究利用ロック中",""]
                for table,cols in result['columns'].items():
                    lines.append(table+': '+', '.join(c['name']+' ('+c['type']+')' for c in cols))
                report.insert('1.0','\n\n'.join(lines))
                report.configure(state='disabled')
                self.log('既存索引の列構造・銘柄ファイル名候補確認成功。データ行未照会・研究利用ロック中。')
            except (OSError,ValueError,sqlite3.Error,TypeError,KeyError,AttributeError,RecursionError):
                output.set('列構造を確認できません。既存索引確認と市場ZIP目録を再実行してください。')
        def inspect_existing_index():
            chosen=filedialog.askopenfilename(parent=dialog,title='既存のhf_light_index.sqliteを選択',
                                              filetypes=[('研究索引','hf_light_index.sqlite'),('SQLite','*.sqlite')])
            if not chosen:
                return
            if not messagebox.askyesno('既存研究索引','既存SQLite索引のテーブル・ビュー名だけを読みます。研究データの行、2026年の集計や市場ZIPは読みません。元ファイルは変更しません。',parent=dialog):
                return
            try:
                result=existing_index_probe(Path(self.path).parent,chosen)
                names=' / '.join(obj['name'] for obj in result['objects'])
                output.set('既存索引：参照成功（構造のみ）\nテーブル・ビュー：'+names+'\n研究期間：未証明・利用ロック中')
                self.log('既存研究索引の構造確認・保存再読込成功。データ行未照会・研究利用ロック中。')
            except (OSError,ValueError,sqlite3.Error,TypeError,UnicodeError):
                output.set('既存索引を確認できません。正しいファイル、アクセス権、使用中のアプリを確認してください。')
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
        ttk.Button(bar, text='既存索引確認', command=inspect_existing_index).pack(side='left',padx=5)
        ttk.Button(bar, text='列構造確認', command=inspect_index_columns).pack(side='left',padx=5)
        ttk.Button(bar, text='月別品質選択', command=monthly_quality_selection).pack(side='left',padx=5)
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
