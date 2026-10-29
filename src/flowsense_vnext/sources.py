"""Explicit local source capabilities. No automatic discovery, truth or network IO."""
import hashlib
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from .boundary import check, decode


class ArtifactResolver:
    """One immutable, raw-hash checked source snapshot per explicit resolver.

    Callers must obtain the inventory from a trusted/verified manifest. A request
    cannot extend this inventory or the allowed source roots. No truth sidecar
    can be read even when it is present in the output manifest.
    """
    def __init__(self, root, files, allowed=('observed/', 'inputs/')):
        self.root = Path(root).resolve()
        check(bool(allowed) and all(p in ('observed/', 'inputs/', 'fixtures/source/',
              'stress/leap/observed/', 'stress/leap/inputs/') for p in allowed), 'HISTORY_ARTIFACT_PATH')
        self.allowed = tuple(allowed)
        self.files = MappingProxyType(dict(files))
        self._raw, self._documents = {}, {}
        self._source_schema_checked, self._selections = set(), {}
        self.read_paths = set()

    def __call__(self, name):
        check(isinstance(name, str) and '\\' not in name and ':' not in name and
              not PurePosixPath(name).is_absolute() and all(p not in ('', '.', '..') for p in name.split('/')),
              'HISTORY_ARTIFACT_PATH')
        check(name in self.files and name.startswith(self.allowed) and
              not any('truth' in p.lower() or 'label' in p.lower() for p in name.split('/')), 'HISTORY_ARTIFACT_PATH')
        path = (self.root / name).resolve()
        check(path.is_relative_to(self.root) and path.is_file(), 'HISTORY_ARTIFACT_PATH')
        if name not in self._raw:
            raw = path.read_bytes()
            check(hashlib.sha256(raw).hexdigest() == self.files[name], 'HISTORY_ARTIFACT_HASH')
            self._raw[name] = raw
            self.read_paths.add(name)
        return self._raw[name]

    def document(self, name):
        if name not in self._documents:
            self._documents[name] = decode(self(name))
        return self._documents[name]
