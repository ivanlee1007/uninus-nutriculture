"""Reject stale native entity handles across asynchronous admission."""

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def admission_guard(entity):
    entity_id = entity.entity_id
    row = er.async_get(entity.hass).async_get(entity_id)
    registry_id = row.id if row else None

    def validate():
        row = er.async_get(entity.hass).async_get(entity_id)
        domain = entity_id.split(".", 1)[0]
        if (
            not entity.tank.active
            or entity.entity_id != entity_id
            or row is None
            or row.id != registry_id
            or row.disabled_by
            or row.platform != DOMAIN
            or row.unique_id != entity.unique_id
            or row.config_entry_id != entity.tank.entry.entry_id
            or entity.hass.data[domain].get_entity(entity_id) is not entity
        ):
            raise ServiceValidationError("inactive_control_entity")

    validate()
    return validate
