import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'operations'
m = json.loads((root / 'runner_release.json').read_text(encoding='utf-8'))
assert m['scope'] == 'SYNTHETIC_ONLY'
assert m['version'] == '0.7.5'
assert set(m['files']) == {'START_GUI.pyw', 'app_version.py', 'api_bridge.py', 'desktop.py', 'synthetic_mailbox.py', 'vault.py'}
for name in ('START_GUI.pyw', 'app_version.py'):
    assert hashlib.sha256((root / 'runner_dist' / name).read_bytes()).hexdigest() == m['files'][name], name
assert (root / 'runner_dist' / 'app_version.py').read_bytes() == b"VERSION = '0.7.5'\n"
print('Changed source hashes and version verified')
