"""Observed-only synthetic research request construction, outside active runtime.

No producer imports; truth/derived outputs are unavailable to this builder. The
resolver restricts every read to observed/ or inputs/ manifest capabilities.
"""
import copy
from datetime import timedelta
from decimal import Decimal
import hashlib
from .boundary import day, timestamp
from .historical import latest


class DatasetAccount:
    def __init__(self, resolver, account_id):
        self.resolver = resolver
        self.name = 'observed/' + account_id + '.json'
        self.observed = resolver.document(self.name)
        self.config = resolver.document('inputs/config.json')
        self.eligibility = resolver.document('inputs/model-eligibility.json')
        self.account_id = account_id
        self.hashes = {name: hashlib.sha256(resolver(name)).hexdigest() for name in
                       (self.name, 'inputs/config.json', 'inputs/model-eligibility.json')}

    def provenance(self, label, at, *, config=False, scenario=False):
        source = 'inputs/config.json' if config else self.name
        return {'id':f'{label}:{self.account_id}:{at[:10]}', 'version':self.config['transformation_version'],
                'source':source, 'sha256':self.hashes[source], 'as_of':at, 'available_at':at,
                'kind':'explicit_scenario' if scenario else 'synthetic_generator_explicit'}

    def build(self, date, horizon=30):
        observed=self.observed;config=self.config;account=observed['account']
        origin=date.isoformat()+'T00:00:00+07:00';at=timestamp(origin)
        lower=(date-timedelta(days=28)).isoformat();through=(date+timedelta(days=horizon+5)).isoformat()
        ledger=[copy.deepcopy(r) for r in observed['ledger'] if lower<=r['event_time'][:10]<str(date) and timestamp(r['available_at'])<=at]
        coverage=[copy.deepcopy(c) for c in observed['coverage'] if lower<=c['date']<str(date) and timestamp(c['available_at'])<=at]
        selected=latest(observed['ledger'],('account_id','source','transaction_id'),('user_id','event_time'),at,'TRANSACTION')
        balance=account['initial_balance_satang']+sum(int(Decimal(r['signed_amount_thb'])*100) for r in selected if timestamp(r['event_time'])<at)
        bill_facts=latest(observed['bill_source_observations'],('account_id','id'),('user_id','kind','due_date','source'),at,'SOURCE_HISTORY_BILL')
        receipts=latest(observed['payment_receipts'],('account_id','source','id'),('user_id','event_time','bill_instance_id'),at,'SOURCE_HISTORY_RECEIPT')
        opening=[];prior=[];historical=[]
        for fact in bill_facts:
            if fact['due_date']>through:continue
            events=[r for r in receipts if r['bill_instance_id']==fact['id'] and timestamp(r['event_time'])<at]
            paid=sum(r['amount_satang'] for r in events)
            if fact['due_date']<str(date.replace(day=1)) and paid>=fact['original_satang']:continue
            if fact['due_date']<str(date.replace(day=1)):prior.append(fact['id'])
            opening.append({k:fact[k] for k in ('id','kind','due_date','original_satang')} | {
                'paid_satang':paid,'payment_events':[{k:e[k] for k in ('id','source','amount_satang','event_time','available_at')} for e in events],
                'revision':(date-day(config['warmup_start'])).days+1,'observed_at':origin,'available_at':origin,'source':'syn-bill-observer'})
        needed={r['bill_instance_id'] for r in latest(ledger,('account_id','source','transaction_id'),('user_id','event_time'),at,'TRANSACTION')
                if r['direction']=='DR' and 'bill_instance_id' in r}-{b['id'] for b in opening}
        for fact in bill_facts:
            if fact['id'] not in needed or fact['due_date']>=str(date.replace(day=1)):continue
            events=[r for r in receipts if r['bill_instance_id']==fact['id'] and timestamp(r['event_time'])<at]
            paid=sum(r['amount_satang'] for r in events)
            if paid!=fact['original_satang']:continue
            b={k:copy.deepcopy(fact[k]) for k in ('id','account_id','user_id','revision','source','kind','due_date','original_satang','source_row','provenance')}
            b.update(observed_at=origin,available_at=origin,paid_satang=paid)
            b['provenance'].update(as_of=origin,available_at=origin)
            fields=('id','account_id','user_id','source','bill_instance_id','revision','amount_satang','event_time','observed_at','available_at','enrichment_version','transformation_version','source_row','provenance')
            b['payment_events']=[{k:copy.deepcopy(e[k]) for k in fields} for e in events];historical.append(b)
        initial=observed['mapping']['available_at'];snapshot=f'opening:{self.account_id}:{date}'
        eligibility=copy.deepcopy(self.eligibility)
        eligibility['evidence']={'id':'eligibility:'+self.account_id,'source':'inputs/model-eligibility.json','sha256':self.hashes['inputs/model-eligibility.json'],
            'version':config['data_version'],'kind':'synthetic_generator_explicit','as_of':initial,'available_at':initial}
        scenario=None
        if account['cohort'] in config['scenario']['cohorts']:
            scenario={'daily_satang':config['scenario']['daily_satang'],'effective_from':str(date),'effective_to':str(date+timedelta(days=horizon-1)),
                      'provenance':self.provenance('scenario',initial,config=True,scenario=True)}
        return {'contract_version':config['contract_version'],'request_kind':'FULL_FORECAST','account_id':self.account_id,'user_id':account['user_id'],
          'origin':origin,'horizon':horizon,'history_source':'EXPLICIT_COMPLETE_LEDGER','transactions':ledger,'coverage':coverage,
          'mappings':[copy.deepcopy(observed['mapping'])],
          'source_registry':{'registry_id':'registry:'+self.account_id,'sources':copy.deepcopy(config['coverage']['sources']),'available_at':initial,'provenance':self.provenance('sources',initial,config=True)},
          'bill_calendar':{'materialized_through':through,'revisions':[copy.deepcopy(s) for s in observed['schedule_revisions'] if timestamp(s['available_at'])<=at]},
          'bills':opening,'opening_snapshot':{'snapshot_id':snapshot,'as_of':origin,'available_at':origin,'source':'syn-bill-observer','assumption':'EXPLICIT_OBSERVATION',
             'prior_overdue_ids':sorted(prior),'provenance':self.provenance('opening',origin)},
          'opening_balance':{'snapshot_id':snapshot,'as_of':origin,'amount_satang':balance,'provenance':self.provenance('balance',origin)},
          'salary':{'monthly_satang':observed['monthly_salary_satang'],'payday':28,'known_at':initial,'available_at':initial,'provenance':self.provenance('salary',initial,config=True)},
          'aggregate_provenance':self.provenance('aggregate',origin),'scenario':scenario,'model_eligibility':eligibility,
          'historical_bill_references':{'registry_id':f'history:{self.account_id}:{origin}','revision':1,'account_id':self.account_id,'user_id':account['user_id'],
              'as_of':origin,'available_at':origin,'provenance':self.provenance('historical-registry',origin),'bills':historical}}
