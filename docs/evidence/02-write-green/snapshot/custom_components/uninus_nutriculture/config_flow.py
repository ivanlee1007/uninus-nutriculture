"""Native flow scaffold."""
from homeassistant.config_entries import ConfigFlow

class NutricultureConfigFlow(ConfigFlow, domain="uninus_nutriculture"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_abort(reason="not_implemented")
