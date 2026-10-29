"""Application-owned acquisition and preservation. Never executes producer validators."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import ast

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'scripts'))
import review_flowsense_vnext_proposed3 as old
OUT = APP / 'docs/contracts/flowsense-vnext-data-review/proposed.4-v2.1.1'
SHOWCASE = old.SHOWCASE
SOURCE = SHOWCASE / 'docs/contracts/flowsense-vnext/revisions/2.0.0-proposed.4'
DATA = SHOWCASE / 'data/synthetic-v2/v2.1.1'
RAW = 'a3ebbe36a3225b9d8c9af5a6c644aecec39dd43503b07c34addea1c93e77e62f'
BUNDLE = '79804e41736b0613f940fc3e4c034148bd15fd98518c4ab4d8c920c587c4679c'
DM = 'adc3efeb328d493fd033e23e2b6bd43b1cfbe2b548d610de9f3a49f58972f7e4'
EM = '3821ec7a2cf6f2edd8e768b212b1a2f388fca7d332e35ece31d8e5f48fdac10e'
old.OUT = OUT
sha, load, canonical = old.sha, old.load, old.canonical


def write(name, value):
    (OUT / name).write_bytes(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False).encode('utf-8') + b'\n')


def inventory(root):
    return old.inventory(root)


def acquire():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'snapshot-before.json').exists(), 'Never replace baseline'
    before = {'application': inventory(APP), 'showcase': inventory(SHOWCASE),
              'git': old.git_state(), 'agent_instructions': 'No AGENTS.md found in either repository or workspace ancestors',
              'command': [sys.executable, '-B', *sys.argv]}
    assert not before['application']['errors'] and not before['showcase']['errors']
    write('snapshot-before.json', before)
    manifest = load(SOURCE / 'revision-manifest.json')
    external = load(DATA / 'external-source-manifest.json')
    assert sha(SOURCE / 'contract.json') == RAW
    assert hashlib.sha256(canonical({k: manifest[k] for k in ('algorithm', 'files')})).hexdigest() == BUNDLE == manifest['bundle_sha256']
    assert sha(DATA / 'dataset-manifest.json') == DM and sha(DATA / 'external-source-manifest.json') == EM
    rows = []
    for group, root, files in [('contract', SOURCE, manifest['files']), ('dataset', DATA, external['output_files']),
                               ('generator_source', SHOWCASE, external['source_files'])]:
        for name, expected in files.items():
            path = (root / name).resolve()
            assert path.is_relative_to(root.resolve())
            actual = sha(path)
            rows.append({'group': group, 'path': name, 'expected': expected, 'actual': actual, 'pass': actual == expected})
    assert all(r['pass'] for r in rows), [r for r in rows if not r['pass']]
    def names(root):
        return {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert names(SOURCE) == set(manifest['files']) | {'revision-manifest.json'}
    assert names(DATA) == set(external['output_files']) | {'external-source-manifest.json'}
    second = SHOWCASE / 'data/synthetic-v2/reproduction/v2.1.1-run2'
    left, right = {n: sha(DATA/n) for n in names(DATA)}, {n: sha(second/n) for n in names(second)}
    comparison = {'first': str(DATA), 'second': str(second), 'first_files': len(left), 'second_files': len(right),
                  'differences': {n: [left.get(n), right.get(n)] for n in sorted(set(left)|set(right)) if left.get(n) != right.get(n)},
                  'method': 'Independent raw SHA-256 comparison of existing directories; no generator rerun'}
    assert len(left) == len(right) == 424 and not comparison['differences']
    pin = OUT / 'pinned'
    for name in [*manifest['files'], 'revision-manifest.json']:
        target = pin / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (SOURCE / name).read_bytes()
        assert not target.exists() or target.read_bytes() == raw
        if not target.exists(): target.write_bytes(raw)
    write('source-verification.json', {'status': 'PASS', 'contract_raw_sha256': RAW, 'source_bundle_sha256': BUNDLE,
          'dataset_manifest_raw_sha256': DM, 'external_source_output_manifest_raw_sha256': EM,
          'exact_contract_inventory': True, 'exact_dataset_inventory': True, 'files': rows,
          'generation_directory_comparison': comparison, 'producer_validators_executed': False})
    print(json.dumps({'verified': len(rows), 'contract_files': len(manifest['files']), 'comparison': comparison}))


def preservation():
    before = load(OUT / 'snapshot-before.json')
    after = {'application': inventory(APP), 'showcase': inventory(SHOWCASE), 'git': old.git_state()}
    write('snapshot-after.json', after)
    result = {}
    allowed = ('src/flowsense_vnext/', 'tests/test_flowsense_vnext_proposed4.py', 'tests/test_flowsense_vnext_proposed3.py',
               'scripts/review_flowsense_vnext_proposed4.py', 'scripts/verify_flowsense_vnext_proposed4.py',
               'scripts/check_flowsense_vnext_data.py', 'scripts/validate_flowsense_vnext_bundle.py')
    for repo in ('application', 'showcase'):
        a,b=before[repo]['files'],after[repo]['files']
        changed=[p for p,h in a.items() if b.get(p)!=h];added=sorted(set(b)-set(a))
        result[repo]={'baseline_files':len(a),'changed_or_removed':changed,'added':added,
                      'out_of_scope_changes':[p for p in changed+added if repo=='showcase' or not p.startswith(allowed)],
                      'read_errors':after[repo]['errors']}
    result['head_unchanged']=before['git']['head']==after['git']['head']
    result['staged_diff_unchanged']=before['git']['staged_diff']==after['git']['staged_diff']
    result['historical_pins_and_ACK_unchanged']=all(after['application']['files'].get(p)==h for p,h in before['application']['files'].items()
        if p.startswith(('docs/contracts/flowsense-vnext-review/', 'docs/contracts/flowsense-vnext-data-review/G1-BILL-HISTORY-01/')))
    result['runtime_config_models_legacy_data_unchanged']=all(after['application']['files'].get(p)==h for p,h in before['application']['files'].items()
        if p.startswith(('src/','models/','data/','frontend/','public/')) and not p.startswith('src/flowsense_vnext/'))
    result['serving_config']=load(APP/'models/serving.json')
    result['status']='PASS' if all([result['head_unchanged'],result['staged_diff_unchanged'],result['historical_pins_and_ACK_unchanged'],
        result['runtime_config_models_legacy_data_unchanged'], result['serving_config']['flowsense_enabled'] is False,
        *[not result[r]['out_of_scope_changes'] and not result[r]['read_errors'] for r in ('application','showcase')]]) else 'FAIL'
    result['scope']='Raw work-file comparison preserving existing dirty bytes; dependencies/caches/.git excluded; HEAD and staged diff independently compared. No deployed-process claim.'
    write('preservation-results.json',result)
    print(json.dumps(result,indent=2));return int(result['status']!='PASS')


def regressions(schema_path):
    root=OUT/'regressions';root.mkdir(exist_ok=True)
    tests_code="import sys,unittest; sys.path.append(sys.argv[1]); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests',pattern='test_flowsense_vnext*.py')); sys.exit(not r.wasSuccessful())"
    # Reuse exact pure regression tests. Redirect only their report destination
    # so the historical proposed.2 evidence is never overwritten.
    path=APP/'scripts/flowsense_vnext_regressions.py'
    code=path.read_text(encoding='utf-8')
    old_output="out = APP / 'docs/contracts/flowsense-vnext-review/proposed.2/existing-python-regressions.json'"
    assert code.count(old_output)==1
    code=code.replace(old_output,"out = Path("+repr(str(root/'existing-python-regressions.json'))+")")
    wrapper="import sys; sys.path.append(sys.argv[1]); exec(compile(sys.argv[2],sys.argv[3],'exec'),{'__name__':'__main__','__file__':sys.argv[3]})"
    tasks=[('isolated-63', [sys.executable,'-B','-c',tests_code,str(schema_path)],60),
           ('existing-pure', [sys.executable,'-B','-c',wrapper,str(schema_path),code,str(path)],60)]
    for revision in ('2','3'):
        dest=root/('proposed'+revision);dest.mkdir(exist_ok=True)
        src=APP/('docs/contracts/flowsense-vnext-review/proposed.'+revision+'/source-verification.json')
        (dest/'source-verification.json').write_bytes(src.read_bytes())
        tasks.append(('historical-proposed'+revision,[sys.executable,'-B','scripts/verify_flowsense_vnext.py',
             '--revision','2.0.0-proposed.'+revision,'--output-dir',str(dest),'--schema-site-packages',str(schema_path)],60))
    results=[]
    for name,command,timeout in tasks:
        start=time.monotonic()
        try:
            proc=subprocess.run(command,cwd=APP,capture_output=True,timeout=timeout)
            (root/(name+'.log')).write_bytes(proc.stdout+proc.stderr)
            results.append({'name':name,'pass':proc.returncode==0,'exit_code':proc.returncode,'timeout_seconds':timeout,
                            'elapsed_seconds':round(time.monotonic()-start,3),'log':name+'.log',
                            'command':command if name!='existing-pure' else [sys.executable,'-B','exact pure runner with report-path-only redirection'],
                            'report_path_only_redirection':name=='existing-pure'})
        except subprocess.TimeoutExpired as e:
            (root/(name+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''))
            results.append({'name':name,'pass':False,'status':'TIMEOUT','timeout_seconds':timeout})
    write('regression-results.json',{'results':results,'pass':all(r['pass'] for r in results),
          'dependency_install_or_upgrade':False,'schema_site_packages_read_only':str(schema_path),
          'not_run':['HTTP','browser','frontend build','ONNX or model load','training/tuning','accuracy','export','activation','commit/push/deploy']})
    print(json.dumps(results,indent=2));return int(any(not r['pass'] for r in results))


def provenance():
    config=load(DATA/'inputs/config.json');seeds=load(DATA/'inputs/seeds.json')
    source=SHOWCASE/'src/synthetic_v2_1/generate.py';uses=[]
    for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
        if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id=='seeds':
            uses.append({'line':node.lineno,'seed':ast.literal_eval(node.slice)})
    assert {u['seed'] for u in uses}=={'economic_events'}
    assert seeds==load(SHOWCASE/'src/synthetic_v2_1/seeds.json')
    assert config['seed_usage']['used']=={'economic_events':seeds['economic_events']}
    assert config['seed_usage']['reserved_unused']=={k:v for k,v in seeds.items() if k!='economic_events'}
    manifest=load(DATA/'external-source-manifest.json')
    write('provenance-details.json',{'status':'PASS','config_raw_sha256':sha(DATA/'inputs/config.json'),
      'seeds_raw_sha256':sha(DATA/'inputs/seeds.json'),'enrichment_source_raw_sha256':sha(SHOWCASE/'src/synthetic_v2_1/enrichment.py'),
      'environment_raw_sha256':sha(DATA/'environment.json'),'environment':load(DATA/'environment.json'),
      'active_seed':config['seed_usage']['used'],'reserved_unused_seeds':config['seed_usage']['reserved_unused'],
      'actual_generator_seed_subscripts':uses,'source_seeds_equal_delivered_values':True,
      'seed_audit_method':'Static AST plus source review; generator not run',
      'availability_policy':'Explicit initial bill declarations and bill-observer receipts event+2 seconds, independent of bank ledger hiding/delay; simulated logical times',
      'bill_derivation':'Known effective schedule, or explicit available preexisting obligation; independent source-row hashes',
      'output_inventory_entries':len(manifest['output_files']),'source_inventory_entries':len(manifest['source_files']),
      'eligibility':load(DATA/'inputs/model-eligibility.json')})
    print('Seed/provenance audit PASS')


def finalize():
    source=load(OUT/'source-verification.json');conformance=load(OUT/'conformance-results.json')
    data=load(OUT/'data-check-results.json');samples=load(OUT/'sample-cli-results.json')
    regression=load(OUT/'regression-results.json');preserved=load(OUT/'preservation-results.json')
    assert source['status']==preserved['status']==data['status']==data['integrity_only']['status']=='PASS'
    assert conformance['summary']['pass']==215 and conformance['summary']['fail']==0
    assert data['consumer_origins']==6688 and not data['prediction_stage']['truth_or_network_attempts']
    assert samples['summary']=={'pass':21,'fail':0,'accepted':18,'expected_rejections':3}
    assert regression['pass'] and load(OUT/'provenance-details.json')['status']=='PASS'
    assert sha(DATA/'dataset-manifest.json')==DM and sha(DATA/'external-source-manifest.json')==EM
    assert sha(SOURCE/'contract.json')==RAW
    assert all(sha(APP/n)==h for n,h in conformance['consumer_sources'].items()),'Consumer changed after final conformance'
    eligibility={'status':'UNVALIDATED','package_version':None,'validated_horizons':[],'validated_cohorts':[]}
    assert load(DATA/'inputs/model-eligibility.json')==eligibility
    hashes={'contract_raw_sha256':RAW,'source_bundle_sha256':BUNDLE,'dataset_manifest_raw_sha256':DM,
            'external_source_output_manifest_raw_sha256':EM}
    write('decisions.json',{'review_date':'2026-10-28','timezone':'Asia/Bangkok','scope':'ISOLATED_CONSUMER_SYNTHETIC_RESEARCH_ONLY',
      'amendment_ack':{'contract_version':'2.0.0-proposed.4','status':'ACK_SPEC_CONFORMANCE','gate0':'SPEC_ALIGNED',
        'contract_raw_sha256':RAW,'source_bundle_sha256':BUNDLE,'conformance_cases_passed':215,'blockers':[]},
      'dataset_gate1':{'dataset_version':'fs-synthetic-v2.1.1','status':'ACCEPTED_FOR_SYNTHETIC_RESEARCH','accepted_hashes':hashes,
        'consumer_origins_passed':6688,'sample_bundles_passed':21,'blockers':[],
        'performance_or_threshold_evaluation_required_for_gate1':False},
      'gate2':'NOT_OPENED','gate3':'NOT_OPENED','gate4':'NOT_OPENED','new_model_eligibility':eligibility,
      'legacy_lineage':'UNKNOWN_UNCHANGED','historical_proposed2_proposed3_pins_ACKs_preserved':True,
      'flowsense_enabled':False,'trustgraph_and_startup_guard_unchanged':True,
      'limitations':['32 accounts / 16 designed cohorts / 2 replicas are not a population sample',
        'Simulated logical availability and deterministic observation/account policies',
        'Main leap-day and unsupported groups have N=0/NOT_ESTIMABLE; stress/conformance are not performance observations',
        '5584 known labels under proposed day-end+7; maturity/splits/masks/thresholds must be frozen before scoring',
        'Overlapping window counts are not unique payments or population spending',
        'No predictive performance, field efficacy or production certification'],
      'not_run':regression['not_run']+['producer semantic validators','fresh generator run'],
      'evidence':{name:sha(OUT/name) for name in ['source-verification.json','conformance-results.json','data-check-results.json',
        'sample-cli-results.json','regression-results.json','provenance-details.json','preservation-results.json']},
      'implementation_sources':{p.relative_to(APP).as_posix():sha(p) for p in [
          *sorted((APP/'src/flowsense_vnext').glob('*.py')),APP/'tests/test_flowsense_vnext_proposed4.py',
          APP/'scripts/verify_flowsense_vnext_proposed4.py',APP/'scripts/check_flowsense_vnext_data.py',
          APP/'scripts/review_flowsense_vnext_proposed4.py',APP/'scripts/validate_flowsense_vnext_bundle.py']}})
    required=['ACKNOWLEDGEMENT.md','decisions.json','source-verification.json','conformance-results.json',
              'DATA_ACCEPTANCE.md','data-check-results.json','REPRODUCTION_LOG.md','preservation-results.json','SHOWCASE_GATE2_HANDOFF.md']
    assert all((OUT/n).is_file() and (OUT/n).stat().st_size for n in required)
    write('deliverable-validation.json',{'status':'PASS','required_files':{n:sha(OUT/n) for n in required},
          'decisions':'Separate exact-hash amendment ACK and Gate1 acceptance; Gate2–4 remain NOT_OPENED'})
    print('Final deliverables PASS; amendment ACK and dataset Gate1 acceptance issued')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('acquire','preservation','regressions','provenance','finalize'))
    parser.add_argument('--schema-site-packages',type=Path);args=parser.parse_args()
    raise SystemExit(({'acquire':acquire,'preservation':preservation,'provenance':provenance,'finalize':finalize}.get(args.action,lambda:regressions(args.schema_site_packages))()) or 0)
