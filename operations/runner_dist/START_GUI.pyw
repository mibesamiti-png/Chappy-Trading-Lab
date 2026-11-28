"""GUI entry point with an immediate, supervisor-mediated update check."""
import sys
import os
import json
import stat
import re
import io
import zipfile
import struct
import csv
from datetime import date
import hashlib
import importlib.util
import subprocess
import threading
import queue
from tkinter import messagebox
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


class DataDesktop(UpdateDesktop):
    def __init__(self, *args, **kwargs):
        self.folder_dialog = None
        self.parquet_busy = False
        self.parquet_results = queue.Queue()
        self.catalog_busy = False
        self.catalog_results = queue.Queue()
        super().__init__(*args, **kwargs)
        self.folder_btn = ttk.Button(self.link_btn.master, text='研究データ設定', command=self.configure_folders)
        self.folder_btn.pack(side='left', padx=3)
        self.probe_btn = ttk.Button(self.link_btn.master, text='研究基盤テスト', command=self.run_research_probe)
        self.probe_btn.pack(side='left', padx=3)
        self.parquet_btn = ttk.Button(self.link_btn.master, text='Parquet環境', command=self.configure_parquet)
        self.parquet_btn.pack(side='left', padx=3)
        self.catalog_btn = ttk.Button(self.link_btn.master, text='市場ZIP目録', command=self.run_market_catalog)
        self.catalog_btn.pack(side='left', padx=3)

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
