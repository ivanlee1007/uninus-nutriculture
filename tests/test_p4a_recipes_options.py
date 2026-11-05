"""Native Options user workflow: drafts, explicit save/apply and second delete page."""

from copy import deepcopy

from homeassistant.auth import auth_manager_from_config
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5


async def test_native_options_full_recipe_workflow(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    hass.auth = await auth_manager_from_config(hass, [], [])
    user = await hass.auth.async_create_user("owner")
    context = {"user_id": user.id}
    before = deepcopy(dict(entry.options))
    flow = await hass.config_entries.options.async_init(entry.entry_id, context=context)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            **{k: entry.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "recipe_management": True,
        },
    )
    assert flow["step_id"] == "recipes"
    assert dict(entry.options) == before
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "new", "recipe_id": ""}
    )
    parameters = {**entry.runtime_data.parameters, "ph_high": 5.9}
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {**parameters, "name": "Grow", "action": "save"}
    )
    assert len(entry.options.get("recipe_catalog", {}).get("recipes", [])) == 1
    assert entry.runtime_data.parameters != parameters
    identity = entry.options["recipe_catalog"]["recipes"][0]["id"]
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "edit", "recipe_id": identity}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {**parameters, "name": "Renamed", "action": "save"}
    )
    assert entry.options["recipe_catalog"]["recipes"][0]["id"] == identity
    assert entry.options["recipe_catalog"]["recipes"][0]["name"] == "Renamed"
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "apply", "recipe_id": identity}
    )
    assert entry.runtime_data.parameters == parameters
    snapshot = deepcopy(dict(entry.options))
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "delete", "recipe_id": identity}
    )
    assert flow["step_id"] == "recipe_delete"
    assert dict(entry.options) == snapshot
    flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"action": "cancel"})
    assert dict(entry.options) == snapshot
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "delete", "recipe_id": identity}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "confirm_delete"}
    )
    assert not entry.options["recipe_catalog"]["recipes"]
    assert (
        entry.options["recipe_catalog"]["last_applied"]
        == snapshot["recipe_catalog"]["last_applied"]
    )
    saved = deepcopy(dict(entry.options))
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "cancel", "recipe_id": ""}
    )
    assert flow["type"] == "abort"
    assert dict(entry.options) == saved
    assert not hass.data["p2_fixture"]["calls"]
    assert not hass.data["p3_fixture"]["calls"]
