"""Bounded local checks. Logs are evidence; a timeout is never a pass."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/baseline-integration'
OUT.mkdir(parents=True, exist_ok=True)


def run(job):
    name, command, limit = job
    start = time.monotonic()
    with (OUT/f'{name}.log').open('w', encoding='utf-8') as log:
        try:
            env = os.environ.copy()
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            if env.get('BASELINE_SCHEMA_SITE_PACKAGES'):
                env['PYTHONPATH'] = os.pathsep.join([str(ROOT), str(Path(sys.prefix)/'Lib/site-packages'), env['BASELINE_SCHEMA_SITE_PACKAGES']])
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=limit)
            row = dict(status='PASSED' if result.returncode == 0 else 'FAILED', exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            row = dict(status='TIMEOUT', limit_seconds=limit)
    row['seconds'] = round(time.monotonic()-start, 2)
    contents = (OUT/f'{name}.log').read_text(encoding='utf-8')
    count = re.search(r'Ran (\d+) tests?', contents) or re.search(r'ℹ tests (\d+)', contents)
    if count:
        row['tests'] = int(count.group(1))
    print(name, row, flush=True)
    return name, row


if __name__ == '__main__':
    files = sys.argv[1:] or [p.stem for p in (ROOT/'tests').glob('test_*.py')]
    jobs = [(name, [sys.executable, '-u', '-X', 'faulthandler', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name+'.py', '-v'], 90) for name in files]
    jobs += [('ui', ['node', '--test']+[str(p) for p in (ROOT/'tests').glob('*.test.mjs')], 60),
             ('build', ['cmd', '/c', 'npm', 'run', 'build'], 90)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(pool.map(run, jobs))
    (OUT/'check-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    sys.exit(int(any(r['status'] != 'PASSED' for r in results.values())))
