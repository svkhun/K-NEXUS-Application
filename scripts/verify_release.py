"""Bounded release regressions. Retired full research-package checks are explicit NOT_RUN."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/application-release'
sys.path.insert(0, str(ROOT))


def worker(filename):
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=filename)
    selected = unittest.TestSuite()
    not_run = []
    def collect(node):
        if isinstance(node, unittest.TestSuite):
            for child in node: collect(child)
        elif '.PackageIntegrityTests.' in node.id():
            not_run.append(dict(test=node.id(), status='NOT_RUN', reason='Full research package/parity/legacy inference outside runtime distribution; runtime integrity checked separately'))
        else: selected.addTest(node)
    collect(suite)
    result = unittest.TextTestRunner(verbosity=2).run(selected)
    row = dict(tests=result.testsRun, passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        failed=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), not_run=not_run)
    print('RELEASE_RESULT '+json.dumps(row), flush=True)
    return int(not result.wasSuccessful())


def run(filename):
    start=time.monotonic()
    with (OUT/(filename+'.log')).open('w', encoding='utf-8') as log:
        try:
            process=subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', filename], cwd=ROOT,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            row=dict(status='PASS' if process.returncode==0 else 'FAIL', exit_code=process.returncode)
        except subprocess.TimeoutExpired:
            row=dict(status='TIMEOUT', timeout=90)
    for line in (OUT/(filename+'.log')).read_text(encoding='utf-8').splitlines():
        if line.startswith('RELEASE_RESULT '): row.update(json.loads(line[15:]))
    row['seconds']=round(time.monotonic()-start,2)
    print(filename, row, flush=True)
    if row['status'] != 'PASS':
        print((OUT/(filename+'.log')).read_text(encoding='utf-8')[-12000:], flush=True)
    return filename,row


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');args=parser.parse_args()
    if args.worker: sys.exit(worker(args.worker))
    OUT.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=dict(pool.map(run,[p.name for p in sorted((ROOT/'tests').glob('test_*.py'))]))
    (OUT/'checks.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    sys.exit(int(any(r['status']!='PASS' for r in rows.values())))
