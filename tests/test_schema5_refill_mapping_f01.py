"""SCHEMA5-REFILL-MAP-F01: real published Core DTO and unchanged shipped consumer."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from homeassistant.helpers import entity_registry as er
from p3_fixtures import nutrient_hass as nutrient_hass
from p3_fixtures import nutrient_payload
from test_p2_control import add_tank, configure, target
from test_p3c_flow import save_v5

BROWSER = (
    r"""
import hashlib, json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
capture, shipped = map(Path, sys.argv[1:])
import playwright, pyee, greenlet
print(json.dumps({'executable':sys.executable,'module_origins':{m.__name__:m.__file__ for m in (playwright,pyee,greenlet)}}), flush=True)
data = json.loads(capture.read_text())
with sync_playwright() as p:
    launch = {'headless': True}
    if os.environ.get('CHROMIUM_EXECUTABLE'):
        launch['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
    browser = p.chromium.launch(**launch)
    try:
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/*', lambda route: route.abort())
        page.set_content('<html><body></body></html>')
        page.add_script_tag(path=str(shipped))
        page.evaluate("""
    + '"""'
    + r"""data => {
            window.calls=[];
            window.card=document.createElement('uninus-nutriculture-card');
            document.body.append(card);
            card.setConfig({entity:data.status_id});
            card.hass={states:data.states,callService:(...args)=>{
                calls.push(args); return Promise.reject(Error('no mutations allowed'));
            }};
        }"""
    + '"""'
    + r""", data)
        assert page.evaluate('card.controls.isConnected'), 'native DTO rejected by shipped Card'
        assert page.locator('[data-runtime-panel]').count() == 1
        assert 'unsupported' in page.locator('[data-runtime-stage="refill"]').inner_text()
        assert page.locator('[data-control="refill_enabled"] button').is_disabled()
        assert page.evaluate("card.controlRows.get('refill_enabled').boundTarget === undefined")
        assert page.evaluate('card.status().attributes') == data['states'][data['status_id']]['attributes']
        assert page.evaluate('calls') == []
        assert not errors, errors
        print(json.dumps({'browser':browser.version,'shipped_path':str(shipped),'shipped_sha256':hashlib.sha256(shipped.read_bytes()).hexdigest(),'native_sha256':hashlib.sha256(capture.read_bytes()).hexdigest(),'controls_connected':True,'refill_enable_disabled':True,'refill_bound_target_absent':True,'mutations':[],'page_errors':errors}))
    finally:
        browser.close()
"""
)


def published(hass, entry):
    status_id = target(hass, entry, "sensor", "control_status")
    # Republish only the real status sensor: Tank.publish also recreates removed
    # switch states and would invalidate the missing-state boundary prerequisite.
    sensor = hass.data["sensor"].get_entity(status_id)
    assert sensor is not None
    sensor.async_write_ha_state()
    state = hass.states.get(status_id)
    assert state is not None
    return dict(state.attributes)


async def version(hass, entry, value):
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "control_contract_version": value}
    )
    await hass.async_block_till_done()


def _run_owned_process(command, output, timeout):
    """Bound only this launcher tree/session, with file-backed durable logs."""
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    timed_out = False
    cleanup_code = None
    with (output / "browser.log").open("xb") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, **options)
        # start_new_session makes this owned child's PID its session/group ID.
        pgid = child.pid if os.name != "nt" else None
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            if os.name == "nt":
                if child.poll() is None:
                    cleanup = subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=10,
                    )
                    cleanup_code = cleanup.returncode
                    (output / "browser-cleanup.log").write_bytes(cleanup.stdout + cleanup.stderr)
            else:
                # Do not use child.poll() here: a reaped root can leave a live
                # descendant (even one ignoring TERM) in our known owned group.
                try:
                    os.killpg(pgid, signal.SIGTERM)
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline:
                        try:
                            os.killpg(pgid, 0)
                        except ProcessLookupError:
                            break
                        time.sleep(0.05)
                    else:
                        os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            code = child.wait(timeout=10)
    result = {
        "pid": child.pid,
        "pgid": pgid,
        "returncode": code,
        "timeout": timed_out,
        "cleanup_returncode": cleanup_code,
    }
    (output / "browser-process.json").write_text(json.dumps(result))
    return result


def browser_check(capture, output):
    shipped = (
        Path(__file__).resolve().parents[2] / "uninus-nutriculture-card/uninus-nutriculture-card.js"
    )
    command = [
        os.environ.get("SCHEMA5_CARD_PYTHON") or sys.executable,
        "-B",
        "-c",
        BROWSER,
        str(capture),
        str(shipped),
    ]
    (output / "browser-command.json").write_text(json.dumps(command))
    result = _run_owned_process(command, output, timeout=45)
    assert not result["timeout"] and result["returncode"] == 0, (output / "browser.log").read_text()


async def test_schema5_uncommissioned_published_mapping_and_shipped_card(control_hass, tmp_path):
    hass = control_hass
    entry = await add_tank(hass)
    assert (await configure(hass, entry, commissioned=False))["type"] == "create_entry"
    assert not entry.options.get("control", {}).get("commissioned")
    await save_v5(hass, entry)
    await hass.async_block_till_done()
    attrs = published(hass, entry)
    refill = target(hass, entry, "switch", "refill_enabled")
    row = er.async_get(hass).async_get(refill)
    assert row and not row.disabled_by and row.config_entry_id == entry.entry_id
    assert hass.states.get(refill) is not None
    assert attrs["schema_version"] == 5
    assert attrs["capabilities"]["refill"] is False
    export = os.environ.get("SCHEMA5_EVIDENCE")
    root = Path(export) if export else tmp_path
    root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="schema5-", dir=root))
    capture = output / "native-schema5.json"
    capture.write_text(
        json.dumps(
            {
                "status_id": target(hass, entry, "sensor", "control_status"),
                "states": {
                    s.entity_id: {"state": s.state, "attributes": dict(s.attributes)}
                    for s in hass.states.async_all()
                },
            },
            default=str,
            indent=2,
        )
    )
    assert "refill_enabled" not in attrs["control_entities"], (
        "uncommissioned schema5 advertises unsupported refill Enable target",
        attrs,
    )
    await asyncio.to_thread(browser_check, capture, output)
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize(
    "schema,commissioned,expected",
    [
        (2, False, True),
        (2, True, True),
        (4, False, False),
        (4, True, True),
        (5, True, True),
    ],
)
async def test_existing_mapping_compatibility(control_hass, schema, commissioned, expected):
    hass = control_hass
    entry = await add_tank(hass)
    if commissioned:
        result = await configure(hass, entry)
        assert result["type"] == "create_entry"
    await version(hass, entry, schema)
    attrs = published(hass, entry)
    assert attrs["schema_version"] == schema
    refill = target(hass, entry, "switch", "refill_enabled")
    assert (attrs["control_entities"].get("refill_enabled") == refill) is expected
    assert attrs["capabilities"]["refill"] is (commissioned or schema == 2)
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("commissioned", [False, True])
async def test_schema3_legacy_mapping_retained(nutrient_hass, commissioned):
    hass = nutrient_hass
    entry = await add_tank(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    values = nutrient_payload(hass, commissioned=commissioned)
    if not commissioned:
        values.pop("refill_output")
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    attrs = published(hass, entry)
    assert attrs["schema_version"] == 3
    assert attrs["capabilities"]["refill"] is True
    assert attrs["control_entities"]["refill_enabled"] == target(
        hass, entry, "switch", "refill_enabled"
    )
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("schema", [4, 5])
@pytest.mark.parametrize(
    "boundary", ["disabled", "missing_state", "missing_registry", "foreign_entry"]
)
async def test_commissioned_registry_boundaries(control_hass, schema, boundary):
    hass = control_hass
    entry = await add_tank(hass)
    assert (await configure(hass, entry))["type"] == "create_entry"
    await version(hass, entry, schema)
    refill = target(hass, entry, "switch", "refill_enabled")
    assert published(hass, entry)["control_entities"]["refill_enabled"] == refill
    registry = er.async_get(hass)
    if boundary == "disabled":
        registry.async_update_entity(refill, disabled_by=er.RegistryEntryDisabler.USER)
    elif boundary == "missing_state":
        hass.states.async_remove(refill)
    elif boundary == "missing_registry":
        registry.async_remove(refill)
    else:
        other = await add_tank(hass)
        registry.async_update_entity(refill, config_entry_id=other.entry_id)
    attrs = published(hass, entry)
    assert attrs["capabilities"]["refill"] is True
    assert "refill_enabled" not in attrs["control_entities"]
    assert not hass.data["p2_fixture"]["calls"]
