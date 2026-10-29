"""Synthetic public HTTP QA with fresh cookies per persona; no debug/history endpoints."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys
import time

import httpx


def persona(client, account, daily, method='SCENARIO'):
    session = client.get('/api/v2/session'); assert session.status_code == 200
    csrf = session.json()['csrf_token']
    def get(route):
        reply=client.get('/api/v2/'+route); assert reply.status_code==200,(route,reply.status_code)
        return reply.json()
    def post(route,body,key=None,expected=200):
        reply=client.post('/api/v2/'+route,json=body,headers={'X-CSRF-Token':csrf,'X-Idempotency-Key':key or secrets.token_hex(16)})
        assert reply.status_code==expected,(route,reply.status_code,reply.text)
        return reply.json()
    def profile(): return get('flowsense/profile/'+account)
    p=profile(); plan=get('flowsense/horizon-status/'+account); path=get('flowsense/forecast-30d/'+account)
    basis=p['spending_basis']
    assert basis==plan['spending_basis']==path['spending_basis']==plan['savings_estimate']['spending_basis']
    assert basis['method']==method and basis['daily_non_bill_thb']==daily
    assert len(path['timeline'])==31 and path['current_balance']==p['main_balance']
    assert path['projection_start']>path['timeline'][0]['date']
    assert path['input_as_of'][:10]==p['input_as_of'][:10]
    assert all(point['method']==method for point in path['timeline'][1:])
    row=dict(account_id=account,method=method,daily_thb=daily,N=basis['complete_known_days'],
        source=basis['source'],version=basis['source_version'],as_of=path['input_as_of'],projection_start=path['projection_start'])
    if method=='ABSTAIN':
        assert plan['savings_capacity'] is None and path['min_projected_balance'] is None
        assert all(point['projected_balance'] is None for point in path['timeline'][1:])
        post('flowsense/savings-preference',dict(account_id=account,enabled=True))
        post('flowsense/micro-sweep',dict(account_id=account,custom_sweep_amount=100),expected=409)
        before=profile();post('flowsense/vault/withdraw',dict(account_id=account,amount=1))
        assert profile()['main_balance']==before['main_balance']+1
        return {**row,'status':'PASS','null_capacity':True,'explicit_withdrawal':True}
    assert basis['complete_known_days']==0 and basis['source_version']=='synthetic-persona-assumptions.2026-10-29.1'
    post('flowsense/scenario',dict(account_id=account,scenario='healthy'))
    before=profile()
    post('flowsense/savings-preference',dict(account_id=account,enabled=True))
    after=profile()
    assert (before['main_balance'],before['vault_balance'])==(after['main_balance'],after['vault_balance'])
    key=secrets.token_hex(16);body=dict(account_id=account,custom_sweep_amount=100)
    saved=post('flowsense/micro-sweep',body,key);assert saved==post('flowsense/micro-sweep',body,key)
    after=profile(); assert after['main_balance']==before['main_balance']-100 and after['vault_balance']==before['vault_balance']+100
    post('flowsense/vault/withdraw',dict(account_id=account,amount=100))
    assert profile()['main_balance']==before['main_balance']
    target='ACC_0100' if account=='ACC_0101' else 'ACC_0101'
    transfer=dict(source_account_id=account,target_account_id=target,amount=100,is_first_time_transfer=0,session_duration_sec=90,ratio_to_daily_avg=1.1)
    review=post('trustgraph/evaluate-transfer',transfer); assert review['status']=='TRANSFER_REVIEW'
    assert review['liquidity_impact']['spending_basis']==profile()['spending_basis']
    proof={name:transfer[name] for name in ('source_account_id','target_account_id','amount')}
    # A changed balance invalidates the previously issued review token.
    post('flowsense/vault/withdraw',dict(account_id=account,amount=1))
    changed=post('trustgraph/confirm-transfer',{**proof,'decision':'PROCEED','review_token':review['review_token']},expected=409)
    assert changed['code']=='PLAN_CHANGED'
    review=post('trustgraph/evaluate-transfer',transfer)
    before=profile()['main_balance']; key=secrets.token_hex(16)
    body={**proof,'decision':'PROCEED','review_token':review['review_token']}
    receipt=post('trustgraph/confirm-transfer',body,key)
    assert receipt['status']=='TRANSFER_EXECUTED' and receipt==post('trustgraph/confirm-transfer',body,key)
    assert profile()['main_balance']==before-100
    risky={**transfer,'target_account_id':'ACC_0001','session_duration_sec':8,'ratio_to_daily_avg':8,'is_first_time_transfer':1}
    review=post('trustgraph/evaluate-transfer',risky)
    assert review['status']=='MICRO_AUTH_REQUIRED' and review['cooldown_remaining_sec']>0
    risk_proof={name:risky[name] for name in ('source_account_id','target_account_id','amount')}
    post('trustgraph/verify-micro-auth',risk_proof,expected=409)
    before=profile()['main_balance']
    assert post('trustgraph/confirm-transfer',{**risk_proof,'decision':'CANCEL'})['status']=='TRANSFER_CANCELLED'
    assert profile()['main_balance']==before
    assert post('trustgraph/evaluate-transfer',{**transfer,'target_account_id':'ACC_0000'})['status']=='BLOCKED_MULE_INTERDICTION'
    denied=client.post('/api/v2/flowsense/savings-preference',json=dict(account_id=account,enabled=False),headers={'X-Idempotency-Key':secrets.token_hex(16)})
    assert denied.status_code==403
    return {**row,'status':'PASS','preference_no_debit':True,'saving_replay_withdrawal':True,
        'transfer_review_basis':True,'stale_review_rejected':True,'normal_transfer_replay_one_debit':True,
        'cooldown_enforced_and_cancelled':True,'blocked_policy':True,'csrf_enforced':True}


def static_checks(client, expected_commit=None, expected_source=None):
    health=client.get('/api/v2/health'); assert health.status_code==200
    health=health.json(); assert health['loaded_models']==['trustgraph'] and health['flowsense_model_enabled'] is False
    release=client.get('/release.json'); assert release.status_code==200 and 'application/json' in release.headers['content-type']
    identity=release.json(); assert identity['release_id']=='application-baseline-20261030.1'
    if expected_commit: assert identity['deployed_commit']==expected_commit
    if expected_source: assert identity['source_sha256']==expected_source
    assets=[]
    for name,expected in identity['assets'].items():
        url='/' if name=='index.html' else '/'+name
        reply=client.get(url); assert reply.status_code==200,(url,reply.status_code)
        assert hashlib.sha256(reply.content).hexdigest()==expected,(url,'hash')
        mime=reply.headers['content-type']
        assert ('javascript' in mime if name.endswith('.js') else 'text/css' in mime if name.endswith('.css') else 'image/svg+xml' in mime if name.endswith('.svg') else 'text/html' in mime),(url,mime)
        assets.append(dict(path=url,status='PASS',sha256=expected,mime=mime))
    for route in ('/app','/flowsense','/dashboard','/trustgraph'):
        reply=client.get(route);assert reply.status_code==200 and hashlib.sha256(reply.content).hexdigest()==identity['assets']['index.html']
        assets.append(dict(path=route,status='PASS',mime=reply.headers['content-type']))
    return dict(health=health,identity=identity,assets=assets)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True);parser.add_argument('--expected-commit');parser.add_argument('--expected-source');parser.add_argument('--output',required=True);args=parser.parse_args()
    report=dict(base=args.base,transport='PUBLIC_HTTPS' if args.base.startswith('https:') else 'REAL_LOOPBACK_HTTP',personas=[])
    try:
        with httpx.Client(base_url=args.base,timeout=60) as client:
            report.update(static_checks(client,args.expected_commit,args.expected_source))
        for account,daily in [('ACC_0100',350),('ACC_0101',600),('ACC_0150',300)]:
            with httpx.Client(base_url=args.base,timeout=20) as client:
                report['personas'].append(persona(client,account,daily))
        report['status']='PASS'
        report['not_run']=['Risky transfer completion after unmodified 15 minute cooldown','Public HISTORY/ABSTAIN fixture injection (no public endpoint)']
    except Exception as error:
        report['status']='FAIL';report['error']=str(error);raise
    finally:
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('identity',)},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
