"""Native recipe forms; transactions go through registered authenticated services."""

import voluptuous as vol
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import selector

from .const import SPECS

CODES = {
    "settings_schema_mismatch",
    "entry_not_loaded",
    "recipe_conflict",
    "settings_conflict",
    "recipe_not_found",
    "invalid_recipe",
    "recipe_limit",
    "busy",
    "confirmation_required",
    "invalid_parameters",
    "invalid_parameter_value",
    "invalid_parameter_pair",
    "invalid_commissioning",
    "invalid_dosing_parameters",
}


def choice(options):
    return selector.SelectSelector(selector.SelectSelectorConfig(options=options))


class RecipeOptions:
    """Mixin keeps native Options completion from replaying stale options."""

    async def _recipe_call(self, service, **data):
        from .recipes import execute

        return await execute(
            self.hass,
            Context(user_id=self.context.get("user_id")),
            service,
            {"config_entry_id": self.config_entry.entry_id, **data},
        )

    def _recipe_error(self, err):
        if isinstance(err, Unauthorized):
            return "unauthorized"
        code = str(err)
        return code if code in CODES else "invalid_recipe"

    async def async_step_recipes(self, user_input=None):
        errors = {}
        try:
            if not hasattr(self, "_recipe_dto"):
                self._recipe_dto = await self._recipe_call("get_recipes_v1")
            if user_input is not None:
                action = user_input["action"]
                if action == "cancel":
                    return self.async_abort(reason="recipe_cancelled")
                identity = user_input.get("recipe_id") or None
                self._recipe_identity = identity
                if action in ("new", "edit"):
                    row = next(
                        (r for r in self._recipe_dto["recipes"] if r["id"] == identity), None
                    )
                    if action == "edit" and row is None:
                        raise ServiceValidationError("recipe_not_found")
                    self._recipe_identity = None if action == "new" else identity
                    self._recipe_draft = (
                        {"name": "", **self._recipe_dto["parameters"]}
                        if action == "new"
                        else {"name": row["name"], **row["parameters"]}
                    )
                    return await self.async_step_recipe_edit()
                if action == "delete":
                    return await self.async_step_recipe_delete()
                if action == "apply":
                    self._recipe_dto = await self._recipe_call(
                        "apply_recipe_v1",
                        recipe_id=identity,
                        expected_catalog_revision=self._recipe_dto["catalog_revision"],
                        expected_settings_revision=self._recipe_dto["settings_revision"],
                    )
                elif action == "refresh":
                    self._recipe_dto = await self._recipe_call("get_recipes_v1")
        except (ServiceValidationError, Unauthorized) as err:
            errors["base"] = self._recipe_error(err)
        rows = getattr(self, "_recipe_dto", {}).get("recipes", [])
        return self.async_show_form(
            step_id="recipes",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional("recipe_id", default=""): choice(
                        [{"value": "", "label": "—"}]
                        + [
                            {"value": r["id"], "label": r["name"] + " · " + r["id"][:6]}
                            for r in rows
                        ]
                    ),
                    vol.Required("action", default="new"): choice(
                        ["new", "edit", "apply", "delete", "refresh", "cancel"]
                    ),
                }
            ),
        )

    async def async_step_recipe_edit(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input["action"] == "cancel":
                return await self.async_step_recipes()
            self._recipe_draft = {k: v for k, v in user_input.items() if k != "action"}
            try:
                self._recipe_dto = await self._recipe_call(
                    "save_recipe_v1",
                    recipe_id=self._recipe_identity,
                    expected_catalog_revision=self._recipe_dto["catalog_revision"],
                    name=user_input["name"],
                    parameters={k: user_input[k] for k in SPECS},
                )
                return await self.async_step_recipes()
            except (ServiceValidationError, Unauthorized) as err:
                errors["base"] = self._recipe_error(err)
        fields = {vol.Required("name", default=self._recipe_draft["name"]): str}
        for key, (_, minimum, maximum, step, _) in SPECS.items():
            fields[vol.Required(key, default=self._recipe_draft[key])] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
                )
            )
        fields[vol.Required("action", default="save")] = choice(["save", "cancel"])
        return self.async_show_form(
            step_id="recipe_edit", errors=errors, data_schema=vol.Schema(fields)
        )

    async def async_step_recipe_delete(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input["action"] == "cancel":
                return await self.async_step_recipes()
            try:
                self._recipe_dto = await self._recipe_call(
                    "delete_recipe_v1",
                    recipe_id=self._recipe_identity,
                    expected_catalog_revision=self._recipe_dto["catalog_revision"],
                    confirm_delete=True,
                )
                return await self.async_step_recipes()
            except (ServiceValidationError, Unauthorized) as err:
                errors["base"] = self._recipe_error(err)
        return self.async_show_form(
            step_id="recipe_delete",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="cancel"): choice(["cancel", "confirm_delete"]),
                }
            ),
        )
