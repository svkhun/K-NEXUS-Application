"""Production ASGI verification; explicitly distinct from real public HTTP/browser QA."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['BASELINE','OFF'],default='BASELINE');args=parser.parse_args()
os.environ.update(ENVIRONMENT='production',PUBLIC_ORIGIN='https://release-qa.example',FLOWSENSE_BASELINE_MODE=args.mode,DEMO_SESSION_SECRET=secrets.token_hex(32))
from fastapi.testclient import TestClient
from src.app_v2 import app
from scripts.verify_release_public import persona, static_checks

with TestClient(app,base_url='https://release-qa.example') as client:
    report=static_checks(client)
    assert report['health']['baseline_mode']==args.mode
    assert report['identity']['baseline_mode']==args.mode
rows=[]
for account,daily in [('ACC_0100',350),('ACC_0101',600),('ACC_0150',300)]:
    with TestClient(app,base_url='https://release-qa.example') as client:
        rows.append(persona(client,account,daily if args.mode=='BASELINE' else None,'SCENARIO' if args.mode=='BASELINE' else 'ABSTAIN'))
        cookie=client.cookies.jar
        assert all(c.secure and c.name=='__Host-flowsense' for c in cookie)
report.update(status='PASS',transport='IN_PROCESS_PRODUCTION_ASGI',personas=rows)
out=ROOT/'artifacts/application-release'/('serving-'+args.mode+'.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',mode=args.mode,personas=rows),ensure_ascii=True))
