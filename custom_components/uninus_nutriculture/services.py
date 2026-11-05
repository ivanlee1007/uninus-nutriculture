"""Domain control service admission."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse

from .const import DOMAIN
from .control_auth import authorize


async def async_setup(hass, config):
    async def start(call):
        await authorize(hass, call.context)
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
            or not getattr(entry, "runtime_data", None)
            or not entry.runtime_data.active
        ):
            from homeassistant.exceptions import ServiceValidationError

            raise ServiceValidationError("entry_not_loaded")
        result = await entry.runtime_data.control.start(
            call.context, request_id=call.data.get("request_id"), service=True
        )
        return result if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        "start_flow",
        start,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): str,
                vol.Optional("request_id"): vol.All(str, vol.Length(min=1, max=128)),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def apply_settings(call):
        from homeassistant.exceptions import ServiceValidationError

        from .control_settings import resolve

        await authorize(hass, call.context)  # Deny before protected target lookup.
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("entry_not_loaded")
        tank = getattr(entry, "runtime_data", None)
        if tank is None or not tank.active:
            raise ServiceValidationError("entry_not_loaded")
        async with tank.lock:
            await authorize(hass, call.context)
            if (
                not tank.active
                or entry.state is not ConfigEntryState.LOADED
                or entry.runtime_data is not tank
            ):
                raise ServiceValidationError("entry_not_loaded")
            version = entry.options.get("control_contract_version", 3)
            is_v4 = version in (4, 5)
            expected_service = {4: "apply_control_settings_v4", 5: "apply_control_settings_v5"}.get(
                version, "apply_control_settings"
            )
            if call.service != expected_service:
                raise ServiceValidationError("settings_schema_mismatch")
            config = dict(entry.options.get("control", {}))
            for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding"):
                if config.get(key):
                    resolve(hass, config[key])
            if version != 5:
                config["allowed_weekdays"] = call.data["allowed_weekdays"]
            extra = {}
            if is_v4:
                for name in ("dosing", "acid", "mix"):
                    commissioned = config.get(
                        ("nutrient" if name == "dosing" else name) + "_commissioned", False
                    )
                    incoming = call.data[name + "_parameters"]
                    if commissioned != (incoming is not None):
                        raise ServiceValidationError("invalid_commissioning")
                safety = call.data["safety_parameters"]
                incoming = call.data["dosing_parameters"]
                if incoming is not None and any(incoming.get(k) != v for k, v in safety.items()):
                    raise ServiceValidationError("invalid_dosing_parameters")
                extra = {
                    k: call.data[k]
                    for k in ("acid_parameters", "mix_parameters", "safety_parameters")
                }
            revision = tank.write_settings(
                parameters=call.data["parameters"],
                dosing_parameters=call.data["dosing_parameters"],
                control=config,
                expected_revision=call.data["expected_revision"],
                **extra,
            )
        return {"applied": True, "settings_revision": revision} if call.return_response else None

    def revision(value):
        if type(value) is not int or value < 0:
            raise vol.Invalid("invalid_revision")
        return value

    hass.services.async_register(
        DOMAIN,
        "apply_control_settings",
        apply_settings,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): vol.All(str, vol.Length(min=1)),
                vol.Required("expected_revision"): revision,
                vol.Required("parameters"): dict,
                vol.Required("dosing_parameters"): dict,
                vol.Required("allowed_weekdays"): dict,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "apply_control_settings_v4",
        apply_settings,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): vol.All(str, vol.Length(min=1)),
                vol.Required("expected_revision"): revision,
                vol.Required("parameters"): dict,
                vol.Required("dosing_parameters"): vol.Any(None, dict),
                vol.Required("acid_parameters"): vol.Any(None, dict),
                vol.Required("mix_parameters"): vol.Any(None, dict),
                vol.Required("safety_parameters"): dict,
                vol.Required("allowed_weekdays"): dict,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "apply_control_settings_v5",
        apply_settings,
        schema=vol.Schema(
            {
                vol.Required("config_entry_id"): vol.All(str, vol.Length(min=1)),
                vol.Required("expected_revision"): revision,
                vol.Required("parameters"): dict,
                vol.Required("dosing_parameters"): vol.Any(None, dict),
                vol.Required("acid_parameters"): vol.Any(None, dict),
                vol.Required("mix_parameters"): vol.Any(None, dict),
                vol.Required("safety_parameters"): dict,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    from .flow_settings import register

    register(hass)

    from .recipes import register as register_recipes

    register_recipes(hass)
    return True
