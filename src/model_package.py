"""Pinned, immutable handoff validation. Never train or export here."""
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as rt
import pandas as pd

FLOW_SCHEMA = ['days_to_payday', 'fixed_due_in_7d', 'is_weekend', 'spend_lag_1', 'spend_lag_3', 'spend_lag_7']
TRUST_SCHEMA = ['amount', 'is_first_time_transfer', 'device_switch_last_24h', 'session_duration_sec',
                'ratio_to_daily_avg', 'auth_face_scan', 'auth_none', 'auth_pin'] + [f'target_emb_{i}' for i in range(16)]
CATEGORIES = {'salary': 'income', 'rent': 'bill', 'debt_emi': 'bill', 'utilities': 'bill',
              'food_daily': 'non_bill', 'transport': 'non_bill', 'entertainment': 'non_bill', 'unplanned_transfer': 'non_bill'}


def load_legacy(directory, hashes):
    """Explicit rollback of the original model AND original embedding together."""
    directory = Path(directory)
    for name in ('trustgraph.onnx', 'trustgraph_embeddings.csv', 'flowsense.onnx'):
        if sha256(directory/name) != hashes[name]:
            raise ValueError(f'Legacy integrity failed: {name}')
    options = rt.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = rt.InferenceSession(str(directory/'trustgraph.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
    frame = pd.read_csv(directory/'trustgraph_embeddings.csv').set_index('account_id')
    values = frame[TRUST_SCHEMA[8:]].to_numpy(dtype=np.float32)
    if values.shape[1] != 16 or not np.isfinite(values).all() or frame.index.duplicated().any():
        raise ValueError('Legacy embedding contract mismatch')
    return session, dict(zip(frame.index, values))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_package(directory, manifest_hash, *, enabled_models=('flowsense', 'trustgraph'), integrity_scope='full'):
    directory = Path(directory)
    if sha256(directory / 'manifest.json') != manifest_hash:
        raise ValueError('Unapproved manifest checksum')
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'READY' or manifest['package_version'] != '2026.10.27.1':
        raise ValueError('Unapproved package version/status')
    if integrity_scope not in ('full', 'runtime'):
        raise ValueError('Unknown integrity scope')
    # A serving distribution retains the original signed-by-hash manifest and
    # runtime bytes. Training weights, text exports and parity/evaluation inputs
    # remain outside the release; they are never needed to create a model session.
    required = {manifest['models'][name]['file'] for name in ('flowsense', 'trustgraph')}
    required.add(manifest['models']['trustgraph']['embedding_file'])
    if not required.issubset(manifest['hashes']):
        raise ValueError('Missing runtime hashes')
    for name, digest in manifest['hashes'].items():
        if integrity_scope == 'runtime' and name not in required:
            continue
        if Path(name).name != name or sha256(directory / name) != digest:
            raise ValueError(f'Package integrity failed: {name}')
    sessions = {}
    options = rt.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    for name, schema in [('flowsense', FLOW_SCHEMA), ('trustgraph', TRUST_SCHEMA)]:
        spec = manifest['models'][name]
        if spec['ordered_feature_schema'] != schema:
            raise ValueError(f'Feature order mismatch: {name}')
        if name not in enabled_models:
            continue
        sess = rt.InferenceSession(str(directory / spec['file']), sess_options=options, providers=['CPUExecutionProvider'])
        inp = sess.get_inputs()
        if len(inp) != 1 or inp[0].name != spec['input']['name'] or inp[0].type != 'tensor(float)' or inp[0].shape != spec['input']['shape']:
            raise ValueError(f'Input contract mismatch: {name}')
        actual = [{'name': o.name, 'type': o.type, 'shape': o.shape} for o in sess.get_outputs()]
        if actual != spec['outputs']:
            raise ValueError(f'Output contract mismatch: {name}')
        sessions[name] = sess
    if manifest['models']['flowsense']['category_mapping'] != CATEGORIES or manifest['models']['trustgraph']['positive_class_index'] != 1:
        raise ValueError('Target/class contract mismatch')
    embeddings = pd.read_csv(directory / manifest['models']['trustgraph']['embedding_file'])
    if set(embeddings.columns) != set(['account_id'] + TRUST_SCHEMA[8:]) or embeddings.account_id.duplicated().any():
        raise ValueError('Embedding schema/identity mismatch')
    values = embeddings[TRUST_SCHEMA[8:]].to_numpy(dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError('Non-finite embedding')
    return manifest, sessions, dict(zip(embeddings.account_id, values))
