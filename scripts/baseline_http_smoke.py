"""Actual socket HTTP evidence, separate cookies from the user's browser."""
import argparse
import json
from pathlib import Path
import secrets
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--base', default='http://127.0.0.1:8023')
parser.add_argument('--method', default='SCENARIO')
args=parser.parse_args()
results=[]
for account in ('ACC_0100','ACC_0101','ACC_0150'):
    with httpx.Client(base_url=args.base, timeout=10) as client:
        session=client.get('/api/v2/session').json()
        def get(route):
            r=client.get('/api/v2/'+route); assert r.status_code==200,r.text
            return r.json()
        def post(route,body,key=None,expected=200):
            r=client.post('/api/v2/'+route,json=body,headers={'X-CSRF-Token':session['csrf_token'],'X-Idempotency-Key':key or secrets.token_hex(16)})
            assert r.status_code==expected,(route,r.status_code,r.text)
            return r.json()
        values=[get('flowsense/'+r+'/'+account) for r in ('profile','horizon-status','forecast-30d')]
        profile,plan,path=values
        assert len({v['spending_basis']['selection_id'] for v in values})==1
        basis=path['spending_basis']; assert basis['method']==args.method,basis
        assert all(p['method']==args.method for p in path['timeline'][1:])
        assert plan['savings_estimate']['spending_basis']==basis
        assert path['current_balance']==profile['main_balance']
        assert path['projection_start']>path['timeline'][0]['date']
        if args.method=='ABSTAIN':
            assert plan['savings_capacity'] is None and path['min_projected_balance'] is None
            assert all(p['projected_balance'] is None for p in path['timeline'][1:])
            post('flowsense/savings-preference',dict(account_id=account,enabled=True))
            post('flowsense/micro-sweep',dict(account_id=account,custom_sweep_amount=100),expected=409)
        if args.method=='SCENARIO':
            post('flowsense/scenario',dict(account_id=account,scenario='healthy'))
            before=get('flowsense/profile/'+account)
            post('flowsense/savings-preference',dict(account_id=account,enabled=True))
            key=secrets.token_hex(16)
            saved=post('flowsense/micro-sweep',dict(account_id=account,custom_sweep_amount=100),key)
            assert saved==post('flowsense/micro-sweep',dict(account_id=account,custom_sweep_amount=100),key)
            after=get('flowsense/profile/'+account)
            assert abs(before['main_balance']+before['vault_balance']-after['main_balance']-after['vault_balance'])<.001
            post('flowsense/vault/withdraw',dict(account_id=account,amount=100))
            target='ACC_0100' if account=='ACC_0101' else 'ACC_0101'
            transfer=dict(source_account_id=account,target_account_id=target,amount=100,is_first_time_transfer=0,session_duration_sec=90,ratio_to_daily_avg=1.1)
            review=post('trustgraph/evaluate-transfer',transfer)
            assert review['status']=='TRANSFER_REVIEW'
            assert review['liquidity_impact']['spending_basis']['selection_id']==get('flowsense/profile/'+account)['spending_basis']['selection_id']
            proof={k:transfer[k] for k in ('source_account_id','target_account_id','amount')}
            before=get('flowsense/profile/'+account)['main_balance']
            post('trustgraph/confirm-transfer',{**proof,'decision':'CANCEL'})
            assert before==get('flowsense/profile/'+account)['main_balance']
            risky=post('trustgraph/evaluate-transfer',{**transfer,'target_account_id':'ACC_0001','session_duration_sec':8,'ratio_to_daily_avg':8,'is_first_time_transfer':1})
            assert risky['status']=='MICRO_AUTH_REQUIRED' and risky['cooldown_remaining_sec']>0
            blocked=post('trustgraph/evaluate-transfer',{**transfer,'target_account_id':'ACC_0000'})
            assert blocked['status']=='BLOCKED_MULE_INTERDICTION'
        health=get('health')
        assert health['loaded_models']==['trustgraph'] and health['flowsense_model_enabled'] is False
        results.append(dict(account_id=account,status='PASSED',method=basis['method'],source=basis['source'],source_version=basis['source_version'],daily_thb=basis['daily_non_bill_thb'],N=basis['complete_known_days'],as_of=path['input_as_of'],projection_start=path['projection_start'],health=health))
report=dict(transport='REAL_LOOPBACK_HTTP',base=args.base,method=args.method,results=results)
output=Path('artifacts/baseline-integration')/('http-'+args.method.lower()+'.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
