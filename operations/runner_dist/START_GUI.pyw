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
        self.ohlcv_btn = ttk.Button(self.link_btn.master, text='OHLCV人工検査', command=self.run_ohlcv_probe)
        self.ohlcv_btn.pack(side='left', padx=3)
        self.parquet_btn = ttk.Button(self.link_btn.master, text='Parquet環境', command=self.configure_parquet)
        self.parquet_btn.pack(side='left', padx=3)
        self.catalog_btn = ttk.Button(self.link_btn.master, text='市場ZIP目録', command=self.run_market_catalog)
        self.catalog_btn.pack(side='left', padx=3)
        self.selection_btn = ttk.Button(self.link_btn.master, text='銘柄候補', command=self.open_market_selection)
        self.selection_btn.pack(side='left', padx=3)

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
