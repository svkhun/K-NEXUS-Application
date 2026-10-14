"""Pin the installed, tested runtime dependency closure (run after upgrades)."""
from importlib.metadata import distribution, version
from pathlib import Path
from packaging.requirements import Requirement

roots = [Requirement(line) for line in Path("requirements.txt").read_text().splitlines() if line.strip() and not line.startswith("#")]
pins = {}


def collect(requirement):
    if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
        return
    name = requirement.name.lower().replace("_", "-")
    actual = version(name)
    if actual not in requirement.specifier:
        raise RuntimeError(f"Installed {name}=={actual} does not satisfy {requirement}")
    if name in pins:
        return
    pins[name] = actual
    for dependency in distribution(name).requires or []:
        collect(Requirement(dependency))


for root in roots:
    collect(root)
Path("requirements.lock").write_text("# Runtime versions tested together; regenerate with scripts/lock_runtime.py.\n" + "\n".join(f"{name}=={pins[name]}" for name in sorted(pins)) + "\n", encoding="utf-8")
print(f"Pinned {len(pins)} runtime distributions")
