"""P4a native registered recipe transactions; real HA, fake hardware."""

from copy import deepcopy

from homeassistant.core import Context
from test_p2_control import target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5


async def call(hass, service, payload):
    return await hass.services.async_call(
        "uninus_nutriculture",
        service,
        payload,
        blocking=True,
        return_response=True,
        context=hass.data["recipe_context"],
    )


async def test_native_save_apply_numbers_single_commit(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    from homeassistant.auth import auth_manager_from_config

    hass.auth = await auth_manager_from_config(hass, [], [])
    user = await hass.auth.async_create_user("owner")
    hass.data["recipe_context"] = Context(user_id=user.id)
    before = deepcopy(dict(entry.options))
    parameters = {**entry.runtime_data.parameters, "ph_high": 5.9}
    await hass.services.async_call(
        "uninus_nutriculture",
        "save_recipe_v1",
        dict(
            config_entry_id=entry.entry_id,
            expected_catalog_revision=0,
            recipe_id=None,
            name="  Grow  ",
            parameters=parameters,
        ),
        blocking=True,
        return_response=False,
        context=hass.data["recipe_context"],
    )
    assert len(entry.options.get("recipe_catalog", {}).get("recipes", [])) == 1
    assert entry.runtime_data.parameters != parameters
    assert entry.options["settings_revision"] == before["settings_revision"]
    dto = await call(hass, "get_recipes_v1", dict(config_entry_id=entry.entry_id))
    assert set(dto) == {
        "schema_version",
        "config_entry_id",
        "catalog_revision",
        "settings_revision",
        "recipes",
        "last_applied",
        "parameters_match",
        "parameters",
    }
    recipe = dto["recipes"][0]
    assert recipe["name"] == "Grow"
    commits = []

    async def observe(h, e):
        commits.append(deepcopy(dict(e.options)))

    remove = entry.add_update_listener(observe)
    try:
        result = await call(
            hass,
            "apply_recipe_v1",
            dict(
                config_entry_id=entry.entry_id,
                expected_catalog_revision=dto["catalog_revision"],
                expected_settings_revision=dto["settings_revision"],
                recipe_id=recipe["id"],
            ),
        )
        await hass.async_block_till_done()
        assert len(commits) == 1
        assert result["parameters_match"] is True
        for key, value in parameters.items():
            assert float(hass.states.get(target(hass, entry, "number", key)).state) == value
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert status.attributes["schema_version"] == 5
        assert status.attributes["parameters"] == parameters
        assert not hass.data["p2_fixture"]["calls"]
        assert not hass.data["p3_fixture"]["calls"]
    finally:
        remove()
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    expected = dict(entry.options)
    config_dir = hass.config.config_dir
    await hass.async_stop(force=True)
    script = """import asyncio,json,sys
from pathlib import Path
from conftest import make_hass
async def main():
 h=await make_hass(Path(sys.argv[1]))
 try:
  e=h.config_entries.async_entries('uninus_nutriculture')
  assert len(e)==1
  print(json.dumps(dict(e[0].options)))
 finally: await h.async_stop(force=True)
asyncio.run(main())
"""
    env = dict(os.environ)
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join((str(root / "tests"), str(root)))
    child = subprocess.run(
        [sys.executable, "-c", script, config_dir],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    print("RECIPE_NEW_PROCESS", child.returncode, child.stdout, child.stderr)
    assert child.returncode == 0
    persisted = json.loads(child.stdout.strip().splitlines()[-1])
    assert persisted == expected
