"""Fail closed on unlisted public files; human content/rights review is still required."""
import argparse,pathlib,re
ROOT_FILES={'README.md','ROADMAP.md','RESEARCH_CHARTER.md','STATE.md','TASK_QUEUE.json','AUTONOMY_RULES.md','HANDOFF.md','.gitignore'}
CODE_FILES={'scripts/run_guard.py','scripts/publication_gate.py','tests/test_run_guard.py','tests/test_publication_gate.py','operations/PERSISTENCE.md','operations/LEASE_PROTOCOL.md','operations/PUBLICATION.md','runs/2026-11-27-execution.md'}
PATTERNS=[re.compile(p,re.I) for p in [r'[A-Z]:[\\/](?:Users|Documents)[\\/]',r'/(?:Users|home)/[^/\s]+/',r'gh[pousr]_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'AKIA[0-9A-Z]{16}']]
def check(root,paths):
    root=pathlib.Path(root).resolve();bad=[]
    for name in paths:
        p=pathlib.Path(name)
        if p.is_absolute() or '..' in p.parts or p.as_posix() not in ROOT_FILES|CODE_FILES:bad.append((name,'not_public_allowlist'));continue
        target=root/p
        if target.is_symlink():bad.append((name,'symlink'));continue
        try:
            if not target.resolve().is_relative_to(root):raise ValueError()
            raw=target.read_bytes();text=raw.decode('utf-8-sig')
            if len(raw)>100_000 or '\x00' in text:bad.append((name,'binary_or_oversize'))
            if any(pattern.search(text) for pattern in PATTERNS):bad.append((name,'private_path_or_secret'))
        except (OSError,UnicodeError,ValueError):bad.append((name,'unreadable_or_nontext'))
    return bad
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('paths',nargs='+');a=p.parse_args();bad=check(a.root,a.paths)
    print('PASS: mechanical checks only; rights and full content review required' if not bad else 'BLOCKED: '+str(bad));raise SystemExit(1 if bad else 0)
