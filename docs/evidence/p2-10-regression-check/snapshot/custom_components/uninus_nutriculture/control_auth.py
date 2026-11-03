"""Shared human control policy (internal automation is permitted)."""
from homeassistant.exceptions import Unauthorized


async def authorize(hass, context):
    if context is not None and context.user_id is not None:
        user = await hass.auth.async_get_user(context.user_id)
        if user is None or not user.is_active or not user.is_admin:
            raise Unauthorized()
