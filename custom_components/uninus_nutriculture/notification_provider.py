"""Core 2026.10 typed NotifyEntity compatibility seam; no ServiceRegistry fallback."""

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent

from .notifications import text


def binding(hass, entity_id):
    row = er.async_get(hass).async_get(entity_id)
    component = hass.data.get("notify")
    entity = component.get_entity(entity_id) if isinstance(component, EntityComponent) else None
    if (
        row is None
        or row.domain != "notify"
        or row.disabled_by
        or not isinstance(entity, NotifyEntity)
        or not entity.available
        or not text(row.id)
        or not text(row.platform)
        or not text(row.unique_id, 512)
    ):
        raise ServiceValidationError("invalid_provider")
    return dict(
        entity_id=row.entity_id,
        registry_entry_id=row.id,
        platform=row.platform,
        unique_id=row.unique_id,
        config_entry_id=row.config_entry_id,
    )


def resolve(hass, saved):
    if not saved:
        raise ServiceValidationError("provider_unavailable")
    row = next(
        (r for r in er.async_get(hass).entities.values() if r.id == saved["registry_entry_id"]),
        None,
    )
    if row is None:
        raise ServiceValidationError("provider_unavailable")
    try:
        actual = binding(hass, row.entity_id)
    except ServiceValidationError:
        raise ServiceValidationError("provider_unavailable") from None
    if any(
        actual[k] != saved[k]
        for k in ("registry_entry_id", "platform", "unique_id", "config_entry_id")
    ):
        raise ServiceValidationError("provider_unavailable")
    return hass.data["notify"].get_entity(row.entity_id)


def catalog(hass, configured=None):
    rows = []
    for row in sorted(er.async_get(hass).entities.values(), key=lambda r: r.entity_id):
        if row.domain != "notify":
            continue
        try:
            binding(hass, row.entity_id)
        except ServiceValidationError:
            continue
        rows.append(dict(entity_id=row.entity_id, label=row.entity_id[:80], available=True))
    selected = None
    if configured:
        row = next(
            (
                r
                for r in er.async_get(hass).entities.values()
                if r.id == configured["registry_entry_id"]
            ),
            None,
        )
        entity_id = row.entity_id if row else configured["entity_id"]
        try:
            resolve(hass, configured)
            available = True
        except ServiceValidationError:
            available = False
        selected = dict(entity_id=entity_id, label=entity_id[:80], available=available)
        rows = [r for r in rows if r["entity_id"] != entity_id]
        rows.append(selected)
        rows.sort(key=lambda r: r["entity_id"])
    result = rows[:256]
    if selected and selected not in result:
        result[-1] = selected
    return result


async def send(hass, saved, message, title, fence):
    entity = resolve(hass, saved)
    if not fence():
        return
    await entity.async_send_message(
        message, title=title if entity.supported_features & NotifyEntityFeature.TITLE else None
    )
    # Native timestamp is recorded only after normal return and same identity/owner.
    if fence() and resolve(hass, saved) is entity:
        entity._async_record_notification()
