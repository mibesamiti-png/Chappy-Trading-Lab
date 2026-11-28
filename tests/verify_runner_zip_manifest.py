import hashlib
import json
import subprocess
from pathlib import Path

repo = Path(__file__).resolve().parents[1]

def committed(path):
    # The updater hashes raw Git blobs, not Windows CRLF-translated checkouts.
    return subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=repo)

m = json.loads(committed('operations/runner_release.json'))
assert m['scope'] == 'SYNTHETIC_ONLY'
assert set(m['files']) == {'START_GUI.pyw', 'app_version.py', 'api_bridge.py', 'desktop.py', 'synthetic_mailbox.py', 'vault.py'}
for name in ('START_GUI.pyw', 'app_version.py'):
    assert hashlib.sha256(committed('operations/runner_dist/' + name)).hexdigest() == m['files'][name], name
assert committed('operations/runner_dist/app_version.py') == ("VERSION = " + repr(m['version']) + "\n").encode()
print('Changed raw Git source hashes and version verified')
