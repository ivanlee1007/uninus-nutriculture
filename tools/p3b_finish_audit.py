"""Read-only production/source verification and append-only final receipts."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'uninus-nutriculture'
OUT = BACKEND / 'docs/evidence/p3b-finish-13-final-audit'
OUT.mkdir(parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pre = json.loads((BACKEND / 'docs/P3B_FINISH_PRODUCTION_PRE.json').read_text())
receipt = {}
inventory = {}
for name in ('uninus-nutriculture', 'uninus-nutriculture-card'):
    prod = Path('D:/UNiNUS Projects/AI project') / name
    isolated = ROOT / name
    tracked = pre[name]['sha256']
    relevant = [p for p in tracked if p.startswith(('custom_components/', 'tests/', 'demo/', '.github/')) or p in ('uninus-nutriculture-card.js', 'pyproject.toml', 'requirements-test.txt')]
    mismatches = [p for p in relevant if not (prod / p).is_file() or sha(prod / p) != tracked[p]]
    assert not mismatches, mismatches
    receipt[name] = {'published_function_head': pre[name]['head'], 'current_head': subprocess.check_output(['git', '-C', str(prod), 'rev-parse', 'HEAD'], text=True).strip(), 'protected_count': len(relevant), 'production_test_mismatches': mismatches}
    folders = ['custom_components', 'tests', 'tools', 'demo', '.github']
    files = [p for folder in folders for p in (isolated / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    files += [p for p in isolated.iterdir() if p.is_file() and p.suffix in ('.js', '.toml', '.txt', '.json', '.yaml', '.yml')]
    items = {}
    for p in sorted(set(files)):
        rel = p.relative_to(isolated).as_posix()
        target = OUT / 'snapshot' / name / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
        items[rel] = {'sha256': sha(p), 'bytes': p.stat().st_size, 'differs_from_published_worktree': not (prod / rel).is_file() or sha(p) != sha(prod / rel)}
    inventory[name] = items
runs = {}
for repo, labels in {'uninus-nutriculture': ['p3b-finish-09-mix-recovery-green', 'p3b-finish-10-full', 'p3b-finish-12-full-wire'], 'uninus-nutriculture-card': ['p3b-finish-07-node', 'p3b-finish-10-browser']}.items():
    for label in labels:
        p = ROOT / repo / 'docs/evidence' / label / 'run.json'
        run = json.loads(p.read_text())
        before = run.get('sha256', run.get('source_before'))
        assert before == run['source_after'], label
        assert run.get('returncode', run.get('child_exit')) == 0, label
        runs[repo + '/' + label] = {'child_exit': 0, 'pre_post_identical': True, 'run_sha256': sha(p)}
contract = BACKEND / 'docs/P3B_ACID_MIX_CONTRACT.md'
result = {'read_only_production': receipt, 'green_receipts': runs, 'frozen_contract_sha256': sha(contract), 'source_inventory': inventory}
(OUT / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
(BACKEND / 'docs/P3B_FINISH_SOURCES.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
print(json.dumps({'read_only_production': receipt, 'green_receipts': runs, 'contract_sha256': sha(contract), 'source_counts': {k: len(v) for k, v in inventory.items()}}, indent=2))
