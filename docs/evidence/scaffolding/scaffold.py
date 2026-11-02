from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
def put(p, s):
    p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf-8')
put('.gitignore', '.venv/\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n*.pyc\n')
put('.gitattributes', '* text=auto eol=lf\ndocs/evidence/** -text\n')
put('custom_components/uninus_nutriculture/manifest.json', json.dumps({'domain':'uninus_nutriculture','name':'UNiNUS Nutriculture','codeowners':['@ivanlee1007'],'config_flow':True,'documentation':'https://github.com/ivanlee1007/uninus-nutriculture','issue_tracker':'https://github.com/ivanlee1007/uninus-nutriculture/issues','iot_class':'local_push','integration_type':'device','requirements':[],'version':'0.1.0'}, indent=2)+'\n')
put('custom_components/uninus_nutriculture/__init__.py', '"""Shadow-only nutrient tank integration."""\nasync def async_setup_entry(hass, entry):\n    return True\n\nasync def async_unload_entry(hass, entry):\n    return True\n')
put('pyproject.toml', '[tool.pytest.ini_options]\nasyncio_mode = "auto"\ntestpaths = ["tests"]\n[tool.ruff]\ntarget-version = "py314"\nline-length = 100\n')
put('tests/conftest.py', '''from pathlib import Path
import shutil
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.helpers import frame, entity_registry, device_registry

DOMAIN = "uninus_nutriculture"

async def make_hass(directory):
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).resolve().parents[1] / "custom_components", directory / "custom_components", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    hass = HomeAssistant(str(directory))
    hass.config.skip_pip = True
    loader.async_setup(hass)
    frame.async_setup(hass)
    await entity_registry.async_load(hass)
    await device_registry.async_load(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    return hass

def entry(name="Tank", options=None):
    return ConfigEntry(domain=DOMAIN, title=name, data={"name":name,"ph":"sensor.ph","ec":"sensor.ec","level":"sensor.level","max_age_seconds":300}, options=options or {}, source="user", version=1, minor_version=1, unique_id=None, discovery_keys={}, subentries_data=[])

@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = await make_hass(tmp_path / "ha")
    for key, value, unit in (("ph",5.6,"pH"),("ec",0.85,"mS/cm"),("level",2.3,"m")):
        instance.states.async_set("sensor."+key, value, {"unit_of_measurement":unit})
    yield instance
    await instance.async_stop(force=True)
''')
put('tests/test_native.py', '''from homeassistant.helpers import entity_registry as er
from conftest import DOMAIN, entry

async def test_native_owned_numbers_and_status(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    rows = er.async_entries_for_config_entry(er.async_get(hass), tank.entry_id)
    numbers = [r for r in rows if r.domain == "number"]
    assert len(numbers) == 10
    assert len([r for r in rows if r.domain == "sensor"]) == 1
    defaults = {"level_low":2.25,"level_high":2.4,"ph_low":5.4,"ph_high":5.8,"ec_low":0.8,"ec_high":0.9,"refill_timeout":190,"ec_timeout":90,"ph_timeout":190,"mix_duration":10}
    for r in numbers:
        key = r.unique_id.split(":")[-1]
        state = hass.states.get(r.entity_id)
        assert float(state.state) == defaults[key]
        assert state.attributes["mode"] == "box"
        assert str(r.entity_category) == "config"
    status = hass.states.get(next(r.entity_id for r in rows if r.domain == "sensor"))
    assert status.state == "within_range"
    assert status.attributes["schema_version"] == 1
    assert status.attributes["mode"] == "shadow"
    assert status.attributes["ready_for_irrigation"] is False
    assert status.attributes["parameters"] == defaults
    assert len(status.attributes["parameter_entities"]) == 10
''')
put('tools/evidence.py', '''"""Capture exact pre-run sources/tests and unmodified test output."""
from pathlib import Path
import datetime, hashlib, json, subprocess, sys
root = Path(__file__).resolve().parents[1]
label = sys.argv[1]
dest = root / "docs" / "evidence" / label
dest.mkdir(parents=True, exist_ok=False)
hashes = {}
for folder in ("custom_components", "tests"):
    for path in (root / folder).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            rel = path.relative_to(root)
            raw = path.read_bytes()
            target = dest / "snapshot" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            hashes[str(rel)] = hashlib.sha256(raw).hexdigest()
cmd = [sys.executable, "-m", "pytest", *sys.argv[2:]]
r = subprocess.run(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
(dest / "pytest.log").write_bytes(r.stdout)
(dest / "run.json").write_text(json.dumps({"timestamp": datetime.datetime.now(datetime.UTC).isoformat(), "command":cmd, "returncode":r.returncode,"sha256":hashes},indent=2))
print(r.stdout.decode(errors="replace"))
sys.exit(r.returncode)
''')
