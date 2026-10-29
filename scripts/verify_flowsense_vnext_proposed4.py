"""215 published literal cases through Application consumer. No producer execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from contextlib import nullcontext
from uuid import uuid4

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP)); sys.path.insert(0, str(APP/'scripts'))
from review_flowsense_vnext_proposed4 import OUT, write, load
from verify_flowsense_vnext import at, mutate
from src.flowsense_vnext.boundary import REVISIONS, Rejected, _validator, canonical, check, decode, digest, shape
from src.flowsense_vnext.files import read_data_bundle, ROLES, FULL_ROLES
from src.flowsense_vnext.ingestion import prepare
from src.flowsense_vnext.projection import TracePredictor, aggregate, features_only, forecast
from src.flowsense_vnext.response import validate_response
from src.flowsense_vnext.issuance import IssueRegistry
from src.flowsense_vnext.sources import ArtifactResolver

PIN = REVISIONS['2.0.0-proposed.4']['pin']


def resolver():
    return ArtifactResolver(PIN, load(PIN/'fixture-source-manifest.json')['files'], ('fixtures/source/',))


def bundle(root, q):
    root.mkdir()
    roles = {**ROLES, **(FULL_ROLES if q['request_kind']=='FULL_FORECAST' else {}),
             'historical-bill-references.json': 'historical_bill_references'}
    files = {}
    for name, field in roles.items():
        value = q[field] if field else {k:v for k,v in q.items() if k not in roles.values()}
        raw = canonical(value); (root/name).write_bytes(raw); files[name]=hashlib.sha256(raw).hexdigest()
    (root/'bundle-manifest.json').write_bytes(canonical({'contract_version': q['contract_version'], 'request_kind': q['request_kind'], 'files':files}))


def update_manifest(root, fn):
    p=root/'bundle-manifest.json';m=decode(p.read_bytes());fn(m);p.write_bytes(canonical(m))


def update_file(root, name, fn):
    p=root/name;v=decode(p.read_bytes());fn(v);p.write_bytes(canonical(v))
    update_manifest(root, lambda m:m['files'].update({name:hashlib.sha256(p.read_bytes()).hexdigest()}))


def run():
    start = time.monotonic()
    rows=[];resolve=resolver()
    for c in load(PIN/'fixtures.json')['cases']:
        frozen=canonical(c);q=c['request'];reason=None;error=None;schema_valid=True;comparisons={};diagnostic={}
        mock=TracePredictor(tuple(c['mock_predictions'])) if 'mock_predictions' in c else None
        try:
            try:shape(q)
            except Rejected:schema_valid=False;raise
            state=prepare(canonical(q),resolver=resolve);diagnostic=state.diagnostic()
            response=copy.deepcopy(c['response_literal']) if 'response_literal' in c else (
                forecast(q,mock_predictor=mock,resolver=resolve) if q['request_kind']=='FULL_FORECAST' else features_only(q,resolver=resolve))
            response=mutate(response,c.get('response_mutations',[]))
            name=('forecast.' if q['request_kind']=='FULL_FORECAST' else '')+'response.schema.json'
            if any(_validator(name,q['contract_version']).iter_errors(response)):schema_valid=False
            validate_response(q,response,mock_predictor=mock,resolver=resolve)
            for path,expected in c['expected'].items():
                actual=at(diagnostic if path.startswith(('history.','day_reasons.')) else response,path)
                comparisons[path]={'expected':expected,'actual':actual,'equal':actual==expected}
        except Rejected as e:reason=e.reason
        except Exception as e:error=repr(e)
        okay=not error and reason==c['reason'] and schema_valid==c['schema_valid'] and canonical(c)==frozen and all(v['equal'] for v in comparisons.values()) and (reason is not None or len(comparisons)==len(c['expected']))
        category='rejection' if c['reason'] else 'unknown' if any(v is None for k,v in c['expected'].items() if k.startswith('history.')) else 'positive'
        rows.append({'id':c['id'],'clause':c['clause'],'group':'migrated_109','category':category,'pass':okay,
                     'expected':c['expected'],'expected_reason':c['reason'],'actual_reason':reason,'expected_schema':c['schema_valid'],
                     'actual_schema':schema_valid,'assertions':comparisons,'error':error,'input_immutable':canonical(c)==frozen,'request_sha256':digest(q)})
    for c in load(PIN/'targeted-fixtures.json')['cases']:
        frozen=canonical(c);q=c['request'];reason=None;error=None;schema_valid=True;actual=None
        try:
            try:shape(q)
            except Rejected:schema_valid=False;raise
            state=prepare(q,resolver=resolve);check(state==prepare(canonical(q),resolver=resolve),'INGRESS_DISAGREEMENT')
            r=forecast(q,resolver=resolve);validate_response(q,r,resolver=resolve);d=state.diagnostic();dates=('2026-10-25','2026-10-26')
            actual={'history':{t:d['history'][t] for t in dates},'day_reasons':{t:d['day_reasons'].get(t,[]) for t in dates},
                    **{k:r['aggregate'][k] for k in ('numerator_satang','complete_known_days','mean_satang')},
                    'method':r['points'][0]['method'],'forecast_dependent_claim':r['forecast_dependent_claim']}
        except Rejected as e:reason=e.reason
        except Exception as e:error=repr(e)
        category='rejection' if c['expected_rejection'] else 'unknown' if None in c['expected']['history'].values() else 'positive'
        rows.append({'id':c['id'],'clause':c['clause'],'group':'targeted_38','category':category,
            'pass':not error and canonical(c)==frozen and reason==c['expected_rejection'] and schema_valid==c['schema_valid'] and actual==c['expected'],
            'expected':c['expected'],'actual':actual,'expected_reason':c['expected_rejection'],'actual_reason':reason,
            'error':error,'input_immutable':canonical(c)==frozen,'request_sha256':digest(q)})
    cases=load(PIN/'historical-fixtures.json')['cases']
    for c in cases:
        q=c['request'];want=c['expected'];frozen=canonical(q);reason=None;error=None;actual={}
        try:
            state=prepare(q,resolver=resolve);d=state.diagnostic();actual={'target':d['history'].get('2025-10-05'),'reasons':d['day_reasons'].get('2025-10-05',[])}
            if want['target'] is not None:assert actual['target']==want['target']
            if want['unknown']:assert actual['target'] is None and want['unknown'] in actual['reasons']
            action=want['check'];opening=decode(state.bills_bytes)
            if action in ('sample','scope'):
                assert 'utilities:2025-09-27' not in {b['id'] for b in opening}
                assert q['historical_bill_references']['bills'][0]['due_date']<'2025-09-29'
                a=aggregate(state);assert [a.numerator_satang,a.complete_known_days,a.mean_satang]==[777068,28,27752]
            if action in ('partial','late_partial'):
                b=next(b for b in opening if b['id']=='utilities:2025-09-27')
                assert b['original_satang']-b['paid_satang']==50000 and b['id'] in q['opening_snapshot']['prior_overdue_ids']
                assert b['id'] not in {b['id'] for b in q['historical_bill_references']['bills']}
                assert forecast(q,resolver=resolve)['points'][0]['bill_payment_thb']>=500
            if action=='boundary':assert aggregate(state).complete_known_days==28
            if action=='duplicate_dates':assert d['history']['2025-10-06'] is None and 'DUPLICATE_LEDGER_PAYMENT_EVENT' in d['day_reasons']['2025-10-06']
            if action in ('builder_correction','before_correction'):
                b=next(b for b in q['historical_bill_references']['bills'] if b['id']=='utilities:2025-09-27')
                assert sorted(p['amount_satang'] for p in b['payment_events'])==([40000,60000] if action=='builder_correction' else [50000,50000])
                assert all(p['revision']==(2 if action=='builder_correction' else 1) for p in b['payment_events'])
            if action=='old_reject':
                old=copy.deepcopy(q);old['contract_version']='2.0.0-proposed.3'
                try:prepare(old)
                except Rejected as e:assert e.reason=='SCHEMA_INVALID'
                else:raise AssertionError('old revision accepted history')
            if action=='issued':
                r=forecast(q,resolver=resolve);saved=canonical(r);validate_response(q,r,previous_issue=copy.deepcopy(r),resolver=resolve)
                changed=copy.deepcopy(q);changed['historical_bill_references']['revision']+=1
                try:validate_response(changed,r,resolver=resolve)
                except Rejected as e:assert e.reason=='ISSUED_SNAPSHOT_MISMATCH'
                else:raise AssertionError('unbound history')
                later=copy.deepcopy(r);later['forecast_dependent_claim']='UNAVAILABLE'
                try:validate_response(q,later,previous_issue=r,resolver=resolve)
                except Rejected as e:assert e.reason=='ISSUED_SNAPSHOT_IMMUTABLE'
                else:raise AssertionError('mutable issuance')
                assert canonical(r)==saved
            if action=='feature':
                feature={k:copy.deepcopy(v) for k,v in q.items() if k not in FULL_ROLES.values()};feature['request_kind']='FEATURE_ONLY'
                fs=prepare(feature,resolver=resolve);assert fs.history==state.history
                fr=features_only(feature,resolver=resolve);validate_response(feature,fr,resolver=resolve)
        except Rejected as e:reason=e.reason
        except Exception as e:error=repr(e)
        rows.append({'id':c['id'],'clause':'H1-H5.WIRE; published historical-fixtures.json literal', 'source_kind':c['source_kind'],
                     'group':'amendment_56','category':'rejection' if want['reject'] else 'unknown' if want['unknown'] else 'positive',
                     'pass':not error and reason==want['reject'] and canonical(q)==frozen,'expected':want,'actual':actual,
                     'actual_reason':reason,'error':error,'input_immutable':canonical(q)==frozen,'request_sha256':digest(q)})
    wire=[('wire-roundtrip',lambda r:None,None),
      ('wire-historical-raw-hash',lambda r:(r/'historical-bill-references.json').write_bytes(b'{}'),'DATA_BUNDLE_HASH_MISMATCH'),
      ('wire-unknown-role',lambda r:update_manifest(r,lambda m:m['files'].update({'other.json':'0'*64})),'DATA_BUNDLE_MANIFEST'),
      ('wire-missing-sidecar-role',lambda r:update_manifest(r,lambda m:m['files'].pop('historical-bill-references.json')),'DATA_BUNDLE_MANIFEST'),
      ('wire-unsupported-version',lambda r:update_manifest(r,lambda m:m.update(contract_version='2.0.0-proposed.3')),'DATA_BUNDLE_MANIFEST'),
      ('wire-core-version-disagreement',lambda r:update_file(r,'request-core.json',lambda m:m.update(contract_version='2.0.0-proposed.3')),'DATA_BUNDLE_MANIFEST'),
      ('wire-kind-disagreement',lambda r:update_file(r,'request-core.json',lambda m:m.update(request_kind='FEATURE_ONLY')),'DATA_BUNDLE_MANIFEST'),
      ('wire-unknown-manifest-field',lambda r:update_manifest(r,lambda m:m.update(extra=1)),'DATA_BUNDLE_MANIFEST'),
      ('wire-core-shadow-sidecar',lambda r:update_file(r,'request-core.json',lambda m:m.update(historical_bill_references={})),'DATA_BUNDLE_MANIFEST'),
      ('wire-registry-unknown-field',lambda r:update_file(r,'historical-bill-references.json',lambda m:m.update(extra=1)),'SCHEMA_INVALID')]
    scratch = OUT / 'scratch' / str(uuid4())
    scratch.mkdir(parents=True)
    with nullcontext(scratch) as tmp:
        for i,(name,mutation,expected) in enumerate(wire):
            root=Path(tmp)/str(i);bundle(root,cases[0]['request']);mutation(root);reason=None;error=None
            try:assert decode(read_data_bundle(root,expected_version='2.0.0-proposed.4',resolver=resolve).request_bytes)==cases[0]['request']
            except Rejected as e:reason=e.reason
            except Exception as e:error=repr(e)
            rows.append({'id':name,'clause':'H5.WIRE','group':'wire_12','category':'rejection' if expected else 'positive',
                         'pass':not error and reason==expected,'expected_reason':expected,'actual_reason':reason,'error':error})
    for name,raw,expected in [('duplicate-json-key',b'{"bills":[],"bills":[]}','DUPLICATE_JSON_KEY'),('nonfinite-json',b'{"x":NaN}','NONFINITE_WIRE')]:
        reason=None
        try:decode(raw)
        except Rejected as e:reason=e.reason
        rows.append({'id':name,'clause':'H5.WIRE','group':'wire_12','category':'rejection','pass':reason==expected,'expected_reason':expected,'actual_reason':reason})
    assert len(rows)==215 and len({(r['group'],r['id']) for r in rows})==215
    sources={p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (APP/'src/flowsense_vnext').glob('*.py')}
    report={'layer':'INDEPENDENT_APPLICATION_CONSUMER','contract_version':'2.0.0-proposed.4','consumer_sources':sources,
      'summary':{'pass':sum(r['pass'] for r in rows),'fail':sum(not r['pass'] for r in rows),
                 **{c:sum(r['category']==c for r in rows) for c in ('positive','rejection','unknown')}},
      'groups':{g:{'count':sum(r['group']==g for r in rows),'pass':sum(r['group']==g and r['pass'] for r in rows),
                  **{c:sum(r['group']==g and r['category']==c for r in rows) for c in ('positive','rejection','unknown')}} for g in sorted({r['group'] for r in rows})},
      'cases':rows,'expectation_migrations':load(PIN/'fixture-migration.json'),
      'late_receipt_expectation_delta':load(PIN/'historical-fixtures.json')['expectation_delta'],
      'source_paths_read':sorted(resolve.read_paths),'producer_semantic_code_executed':False,'models_loaded':0,
      'category_definition':'Exclusive published fixture intent. Positive may deliberately have sparse coverage. Unknown denotes an expected day-local failure assertion, not request rejection.',
      'command':[sys.executable,'-B',*sys.argv],'elapsed_seconds':round(time.monotonic()-start,3),
      'forbidden_imports_present':[n for n in ('semantic_validator','historical','wire','onnxruntime','torch','lightgbm','src.app_v2','src.model_package') if n in sys.modules]}
    assert not report['forbidden_imports_present']
    write('conformance-results.json',report)
    print(json.dumps({k:report[k] for k in ('summary','groups')},indent=2))
    for r in rows:
        if not r['pass']:print(json.dumps(r,ensure_ascii=False))
    return int(report['summary']['fail']>0)


if __name__=='__main__':
    if '--schema-site-packages' in sys.argv:sys.path.append(sys.argv[sys.argv.index('--schema-site-packages')+1])
    raise SystemExit(run())
