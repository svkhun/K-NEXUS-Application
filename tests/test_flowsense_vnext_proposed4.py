"""Consumer-specific source, wire and durable issuance regressions."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from uuid import uuid4

from src.flowsense_vnext.boundary import Rejected, canonical, decode, digest
from src.flowsense_vnext.ingestion import prepare
from src.flowsense_vnext.projection import aggregate, forecast, features_only
from src.flowsense_vnext.response import validate_response
from src.flowsense_vnext.issuance import IssueRegistry
from src.flowsense_vnext.files import read_data_bundle
from src.flowsense_vnext.sources import ArtifactResolver

APP=Path(__file__).resolve().parents[1]
OUT=APP/'docs/contracts/flowsense-vnext-data-review/proposed.4-v2.1.1'
PIN=OUT/'pinned'


class Proposed4ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.cases={c['id']:c['request'] for c in decode((PIN/'historical-fixtures.json').read_bytes())['cases']}
        self.q=copy.deepcopy(self.cases['original-nonbill-32197-not-zero'])
        self.resolver=ArtifactResolver(PIN,decode((PIN/'fixture-source-manifest.json').read_bytes())['files'],('fixtures/source/',))

    def rejected(self, reason, fn):
        with self.assertRaises(Rejected) as cm:fn()
        self.assertEqual(cm.exception.reason,reason)

    def scratch(self):
        root=OUT/'consumer-test-scratch'/str(uuid4());root.mkdir(parents=True);return root

    def test_file_hash_and_row_hash_do_not_authorize_fabricated_row_content(self):
        receipt=self.q['historical_bill_references']['bills'][0]['payment_events'][0]
        proof=receipt['provenance'];raw=self.resolver(proof['source'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['sha256'])
        doc=decode(raw);row=next(r for r in doc['receipt_facts'] if r['row_id']==receipt['source_row']['row_id'])
        self.assertEqual(digest(row),receipt['source_row']['sha256'])
        receipt['amount_satang']+=1
        self.rejected('HISTORY_RECEIPT_SOURCE_MISMATCH',lambda:prepare(self.q,resolver=self.resolver))

    def test_valid_bill_row_digest_does_not_authorize_other_original_amount(self):
        b=self.q['historical_bill_references']['bills'][0];b['original_satang']+=1
        self.rejected('HISTORY_BILL_SOURCE_MISMATCH',lambda:prepare(self.q,resolver=self.resolver))

    def test_source_correction_selects_known_maximum_and_future_isolation(self):
        earlier=copy.deepcopy(self.cases['builder-correction-before-availability-original'])
        corrected=copy.deepcopy(self.cases['builder-correction-known-selected-maxima'])
        old=next(b for b in earlier['historical_bill_references']['bills'] if b['id']=='utilities:2025-09-27')['payment_events']
        new=next(b for b in corrected['historical_bill_references']['bills'] if b['id']=='utilities:2025-09-27')['payment_events']
        self.assertEqual(sorted(r['amount_satang'] for r in old),[50000,50000])
        self.assertEqual(sorted(r['amount_satang'] for r in new),[40000,60000])
        frozen=canonical(earlier);before=prepare(earlier,resolver=self.resolver)
        self.assertEqual(dict(before.history)['2025-10-05'],32197)
        self.assertEqual(dict(prepare(corrected,resolver=self.resolver).history)['2025-10-05'],32197)
        future=copy.deepcopy(earlier['historical_bill_references']['bills'][0]);future['revision']=999;future['available_at']='2099-01-01T00:00:00+07:00';future['account_id']='OTHER'
        poisoned=copy.deepcopy(earlier);poisoned['historical_bill_references']['bills'].append(future)
        self.assertEqual(prepare(poisoned,resolver=self.resolver).history,before.history)
        self.assertEqual(canonical(earlier),frozen)

    def test_superseded_source_row_rejected_even_when_both_hashes_correct(self):
        q=copy.deepcopy(self.cases['builder-correction-known-selected-maxima'])
        receipt=q['historical_bill_references']['bills'][0]['payment_events'][0]
        proof=copy.deepcopy(receipt['provenance']);doc=decode(self.resolver(proof['source']))
        old=next(r for r in doc['receipt_facts'] if r['id']==receipt['id'] and r['revision']==1)
        receipt.clear();receipt.update({k:v for k,v in old.items() if k!='row_id'})
        proof.update(as_of=old['available_at'],available_at=old['available_at'])
        receipt.update(provenance=proof,source_row={'collection':'receipt_facts','row_id':old['row_id'],'sha256':digest(old)})
        self.rejected('HISTORY_RECEIPT_SOURCE_MISMATCH',lambda:prepare(q,resolver=self.resolver))

    def test_cross_registry_id_and_event_collisions(self):
        for name,reason in [('opening-history-id-collision','HISTORY_OPENING_ID_COLLISION'),
                            ('receipt-identity-collision-across-registries','DUPLICATE_SOURCE_PAYMENT_EVENT')]:
            with self.subTest(name=name):self.rejected(reason,lambda:prepare(self.cases[name],resolver=self.resolver))

    def test_historical_scope_bounded_by_selected_28day_debits(self):
        q=copy.deepcopy(self.q)
        q['transactions']=[r for r in q['transactions'] if 'bill_instance_id' not in r or r['bill_instance_id']!='utilities:2025-09-27']
        self.rejected('UNREFERENCED_HISTORY_BILL',lambda:prepare(q,resolver=self.resolver))

    def test_source_resolver_rejects_truth_network_path_escape_and_unlisted(self):
        for name in ('truth/labels.jsonl','../observed/x.json','https://example.com/a','fixtures/source/../x.json','C:/secret.json','fixtures/source/unlisted.json'):
            with self.subTest(name=name):self.rejected('HISTORY_ARTIFACT_PATH',lambda:self.resolver(name))

    def test_source_hash_checks_actual_file_before_document_decode(self):
        root=self.scratch();(root/'observed').mkdir();path=root/'observed/facts.json';path.write_bytes(b'{}')
        resolve=ArtifactResolver(root,{'observed/facts.json':'0'*64})
        self.rejected('HISTORY_ARTIFACT_HASH',lambda:resolve.document('observed/facts.json'))

    def test_strict_sidecar_duplicate_keys_and_nonfinite_raw_ingress(self):
        from scripts.verify_flowsense_vnext_proposed4 import bundle, update_manifest
        for raw,reason in [(b'{"bills":[],"bills":[]}','DUPLICATE_JSON_KEY'),(b'{"bad":1e999}','NONFINITE_WIRE')]:
            root=self.scratch()/'bundle';bundle(root,self.q)
            (root/'historical-bill-references.json').write_bytes(raw)
            update_manifest(root,lambda m:m['files'].update({'historical-bill-references.json':hashlib.sha256(raw).hexdigest()}))
            self.rejected(reason,lambda:read_data_bundle(root,resolver=self.resolver))

    def test_proposed3_rejects_history_and_proposed4_requires_source(self):
        q=copy.deepcopy(self.q);q['contract_version']='2.0.0-proposed.3'
        self.rejected('SCHEMA_INVALID',lambda:prepare(q,resolver=self.resolver))
        self.rejected('HISTORY_SOURCE_REQUIRED',lambda:prepare(self.q))

    def test_complete_request_binding_in_response_and_aggregate(self):
        response=forecast(self.q,resolver=self.resolver)
        self.assertEqual(response['request_sha256'],digest(self.q))
        self.assertEqual(response['aggregate']['input_sha256'],digest(self.q))
        for field in ('revision','provenance'):
            q=copy.deepcopy(self.q)
            if field=='revision':q['historical_bill_references']['revision']+=1
            else:q['historical_bill_references']['provenance']['id']+=':new'
            self.rejected('ISSUED_SNAPSHOT_MISMATCH',lambda:validate_response(q,response,resolver=self.resolver))
        feature={k:v for k,v in self.q.items() if k not in ('opening_balance','salary','aggregate_provenance','scenario','model_eligibility')};feature['request_kind']='FEATURE_ONLY'
        r=features_only(feature,resolver=self.resolver);self.assertEqual(r['request_sha256'],digest(feature))
        feature['historical_bill_references']=copy.deepcopy(feature['historical_bill_references']);feature['historical_bill_references']['revision']+=1
        self.rejected('ISSUED_SNAPSHOT_MISMATCH',lambda:validate_response(feature,r,resolver=self.resolver))

    def test_row_order_input_immutability_and_projection_isolation(self):
        frozen=canonical(self.q);state=prepare(self.q,resolver=self.resolver);r=forecast(self.q,resolver=self.resolver)
        q=copy.deepcopy(self.q)
        for field in ('transactions','coverage','bills'):q[field].reverse()
        q['historical_bill_references']['bills'].reverse()
        for b in q['historical_bill_references']['bills']:b['payment_events'].reverse()
        other=prepare(q,resolver=self.resolver);rr=forecast(q,resolver=self.resolver)
        self.assertEqual(other.history,state.history);self.assertEqual(other.day_reasons,state.day_reasons);self.assertEqual(other.bills_bytes,state.bills_bytes)
        self.assertEqual(r['points'],rr['points']);self.assertEqual(canonical(self.q),frozen)
        self.assertNotIn('utilities:2025-09-27',{b['id'] for b in decode(state.bills_bytes)})
        self.assertEqual(aggregate(state).mean_satang,27752)

    def test_issued_record_survives_restart_and_rejects_amended_replacement(self):
        path=self.scratch()/'issued.sqlite';registry=IssueRegistry(path);r=forecast(self.q,resolver=self.resolver)
        saved=registry.issue(self.q,r,resolver=self.resolver);q=copy.deepcopy(self.q);q['historical_bill_references']['revision']+=1
        newer=forecast(q,resolver=self.resolver)
        self.rejected('ISSUED_SNAPSHOT_IMMUTABLE',lambda:IssueRegistry(path).issue(q,newer,resolver=self.resolver))
        self.assertEqual(IssueRegistry(path).read(self.q['account_id'],self.q['origin']),saved)


if __name__=='__main__':unittest.main()
