"""Public scenario lifecycle QA, isolated cookie jars; never records session secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import httpx


def run(base, commit, source):
    rows = []
    with httpx.Client(base_url=base, timeout=60) as public:
        identity = public.get('/release.json').json()
        assert identity['deployed_commit'] == commit
        assert identity['source_sha256'] == source
        assert identity['flowsense_model_enabled'] is False
        assert identity['loaded_models'] == ['trustgraph']
        assert identity['demo_initialization_version'] == 'demo-opening.2026-10-30.1'
        for name, digest in identity['assets'].items():
            asset = public.get('/' if name == 'index.html' else '/'+name)
            assert asset.status_code == 200
            assert hashlib.sha256(asset.content).hexdigest() == digest
    for account in ('ACC_0100', 'ACC_0101', 'ACC_0150'):
        with httpx.Client(base_url=base, timeout=60, headers={'Origin':base}) as client:
            opening = client.get('/api/v2/session').json()
            assert opening['lifecycle'] == 'NEW'
            def get(kind, target=account):
                r = client.get('/api/v2/flowsense/'+kind+'/'+target)
                assert r.status_code == 200, r.text
                return r.json()
            def post(route, body=None, key=None):
                r = client.post('/api/v2/'+route,json=body or {},headers={
                    'X-CSRF-Token':opening['csrf_token'],'X-Idempotency-Key':key or secrets.token_hex(16)})
                assert r.status_code == 200, r.text
                return r.json()
            initial = get('horizon-status')
            assert initial['scenario'] == 'default' and initial['max_sweep_amount'] > 1 and initial['remaining_today'] > 1
            others = {a:get('profile', a) for a in ('ACC_0100', 'ACC_0101', 'ACC_0150') if a != account}
            risk = post('flowsense/scenario',dict(account_id=account,scenario='commitment_risk'))
            assert risk['scenario'] == 'commitment_risk' and risk['remaining_today'] == 0 and risk['current_balance'] > 0
            assert risk['budget_reserve_shortfall'] > 0
            before = get('profile')
            resumed = client.get('/api/v2/session').json()
            assert resumed['lifecycle'] == 'RESUMED' and resumed['session_id'] == opening['session_id']
            for _ in range(2):
                get('forecast-30d'); plan = get('horizon-status')
                p = get('profile')
                for field in ('main_balance','vault_balance','events'):
                    assert p[field] == before[field]
                assert plan['scenario'] == 'commitment_risk'
            post('flowsense/reset-state/'+account)
            restored = get('horizon-status')
            assert restored['scenario'] == 'default'
            assert restored['current_balance'] == initial['current_balance']
            assert restored['max_sweep_amount'] > 1
            for other, p in others.items():
                after = get('profile', other)
                for field in ('main_balance','vault_balance','events','savings_enabled'):
                    assert p[field] == after[field]
            post('flowsense/savings-preference',dict(account_id=account,enabled=True))
            before = get('profile'); key=secrets.token_hex(16)
            body = dict(account_id=account,custom_sweep_amount=1)
            saved = post('flowsense/micro-sweep',body,key)
            assert post('flowsense/micro-sweep',body,key) == saved
            after = get('profile')
            assert round(after['main_balance']+after['vault_balance'],2) == round(before['main_balance']+before['vault_balance'],2)
            assert after['main_balance'] == before['main_balance']-1
            rows.append(dict(account=account,status='PASS',opening_balance=initial['current_balance'],opening_budget=initial['remaining_today'],opening_max_save=initial['max_sweep_amount'],risk_balance=risk['current_balance'],risk_budget=risk['remaining_today'],resume_preserved=True,reset_scoped=True,sweep_retry_single_debit=True))
    return dict(status='PASS',identity={k:identity[k] for k in ('release_id','deployed_commit','source_sha256','demo_initialization_version','baseline_mode','flowsense_model_enabled','loaded_models','package_manifest_sha256')},personas=rows)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--commit',required=True);p.add_argument('--source',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    result=run(args.base.rstrip('/'),args.commit,args.source)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
