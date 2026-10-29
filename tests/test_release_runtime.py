import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src import app_v2 as backend
from src.model_package import load_package, sha256


class RuntimeDistributionTests(unittest.TestCase):
    def test_original_manifest_and_runtime_pair_load_only_trustgraph(self):
        self.assertEqual(sha256(backend.PACKAGE_DIR/'manifest.json'), backend.SERVING_CONFIG['manifest_sha256'])
        manifest, sessions, embeddings = load_package(backend.PACKAGE_DIR,
            backend.SERVING_CONFIG['manifest_sha256'], enabled_models=('trustgraph',), integrity_scope='runtime')
        self.assertEqual(set(sessions), {'trustgraph'})
        self.assertIn('ACC_0100', embeddings)
        self.assertEqual(manifest['models']['trustgraph']['threshold'], .5)
        self.assertFalse(backend.SERVING_CONFIG['flowsense_enabled'])

    def test_each_corrupted_runtime_file_and_manifest_fail_closed(self):
        for name in ('flowsense.onnx', 'trustgraph.onnx', 'trustgraph_embeddings.csv', 'manifest.json'):
            with self.subTest(file=name), tempfile.TemporaryDirectory() as folder:
                dest = Path(folder)/'package'
                shutil.copytree(backend.PACKAGE_DIR, dest)
                path = dest/name
                path.write_bytes(path.read_bytes()+b'corruption')
                with self.assertRaises(ValueError):
                    load_package(dest, backend.SERVING_CONFIG['manifest_sha256'],
                        enabled_models=('trustgraph',), integrity_scope='runtime')

    def test_build_identity_and_runtime_commit_are_separate(self):
        with patch.dict('os.environ', {'RENDER_GIT_COMMIT': 'a'*40}):
            body = json.loads(backend.release_identity().body)
        self.assertEqual(body['deployed_commit'], 'a'*40)
        self.assertEqual(len(body['source_sha256']), 64)
        self.assertEqual(body['loaded_models'], ['trustgraph'])
        self.assertFalse(body['flowsense_model_enabled'])
        self.assertNotIn('deployed_commit', json.loads((Path(backend.REACT_DIST_DIR)/'release.json').read_text()))
