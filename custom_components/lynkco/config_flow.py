import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import aiohttp

from .const import (
    CONFIG_2FA_KEY,
    CONFIG_DARK_HOURS_END,
    CONFIG_DARK_HOURS_START,
    CONFIG_EMAIL_KEY,
    CONFIG_EXPERIMENTAL_KEY,
    CONFIG_PASSWORD_KEY,
    CONFIG_SCAN_INTERVAL_KEY,
    CONFIG_VIN_KEY,
    DOMAIN,
    STORAGE_REFRESH_TOKEN_KEY,
)
from .login_flow import login, two_factor_authentication
from .token_manager import STORAGE_CCC_TOKEN_KEY, get_token_storage, send_device_login

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_EMAIL_KEY): str,
        vol.Required(CONFIG_PASSWORD_KEY): str,
        vol.Required(CONFIG_VIN_KEY): str,
    }
)

STEP_TWO_FA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_2FA_KEY): str,
    }
)


def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_vin(vin: str) -> bool:
    """Validate the VIN based on length and allowed characters."""
    vin_regex = r"^[A-HJ-NPR-Z0-9]{17}$"
    return bool(re.match(vin_regex, vin))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lynk & Co."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._session: aiohttp.ClientSession | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._vin: str | None = None
        self._login_details: dict | None = None
        self._reauth_entry = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return OptionsFlowHandler(config_entry)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(quote_cookie=False)
            self._session = aiohttp.ClientSession(cookie_jar=jar)
        return self._session

    async def _close_session(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        # Validate input
        email = user_input.get("email", "").strip()
        password = user_input.get("password", "")
        vin = user_input.get("vin", "").strip().upper()

        if not email or not password or not vin:
            errors["base"] = "missing_details"
        elif not is_valid_email(email):
            errors["email"] = "invalid_email"
        elif not is_valid_vin(vin):
            errors["vin"] = "invalid_vin"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        # Store credentials for use in 2FA step
        self._email = email
        self._password = password
        self._vin = vin

        # Get session and attempt login
        session = await self._get_session()
        
        try:
            login_result = await login(email, password, session)
            (
                x_ms_cpim_trans_value,
                x_ms_cpim_csrf_token,
                page_view_id,
                referer_url,
                code_verifier,
            ) = login_result

            if None in (x_ms_cpim_trans_value, x_ms_cpim_csrf_token):
                errors["base"] = "login_failed"
                await self._close_session()
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )

            # Store login details for 2FA step
            self._login_details = {
                "x_ms_cpim_trans_value": x_ms_cpim_trans_value,
                "x_ms_cpim_csrf_token": x_ms_cpim_csrf_token,
                "page_view_id": page_view_id,
                "referer_url": referer_url,
                "code_verifier": code_verifier,
            }

            # Proceed to 2FA step
            return await self.async_step_two_factor()

        except Exception as e:
            _LOGGER.error("Error during login: %s", e, exc_info=True)
            errors["base"] = "login_failed"
            await self._close_session()
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

    async def async_step_two_factor(self, user_input=None):
        """Handle the 2FA verification step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="two_factor",
                data_schema=STEP_TWO_FA_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "email": self._email,
                },
            )

        two_fa_code = user_input.get("2fa", "").strip()
        
        if not two_fa_code:
            errors["base"] = "missing_2fa_code"
            return self.async_show_form(
                step_id="two_factor",
                data_schema=STEP_TWO_FA_DATA_SCHEMA,
                errors=errors,
            )

        session = await self._get_session()

        try:
            access_token, refresh_token = await two_factor_authentication(
                two_fa_code,
                self._login_details.get("x_ms_cpim_trans_value"),
                self._login_details.get("x_ms_cpim_csrf_token"),
                self._login_details.get("page_view_id"),
                self._login_details.get("referer_url"),
                self._login_details.get("code_verifier"),
                session,
            )

            if not access_token or not refresh_token:
                errors["base"] = "invalid_2fa_code"
                return self.async_show_form(
                    step_id="two_factor",
                    data_schema=STEP_TWO_FA_DATA_SCHEMA,
                    errors=errors,
                )

            # Success - save tokens and create/update entry
            await self._close_session()

            token_storage = get_token_storage(self.hass)
            tokens = await token_storage.async_load() or {}
            tokens[STORAGE_REFRESH_TOKEN_KEY] = refresh_token
            
            ccc_token = await send_device_login(access_token)
            if ccc_token:
                tokens[STORAGE_CCC_TOKEN_KEY] = ccc_token
            else:
                _LOGGER.error("Failed to obtain CCC token")
                errors["base"] = "token_error"
                return self.async_show_form(
                    step_id="two_factor",
                    data_schema=STEP_TWO_FA_DATA_SCHEMA,
                    errors=errors,
                )
            
            await token_storage.async_save(tokens)

            # Handle reauth vs new entry
            if self._reauth_entry:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={"vin": self._vin},
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")
            
            return self.async_create_entry(
                title="Lynk & Co",
                data={"vin": self._vin},
            )

        except Exception as e:
            _LOGGER.error(
                "Error during two-factor authentication: %s", e, exc_info=True
            )
            errors["base"] = "two_factor_auth_failed"
            return self.async_show_form(
                step_id="two_factor",
                data_schema=STEP_TWO_FA_DATA_SCHEMA,
                errors=errors,
            )

    async def async_step_reauth(self, user_input=None):
        """Handle re-authentication flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._vin = self._reauth_entry.data.get(CONFIG_VIN_KEY) if self._reauth_entry else None
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth confirmation."""
        if user_input is not None:
            return await self.async_step_user(user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={},
            description_placeholders={
                "message": "Please re-enter your credentials to re-authenticate."
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            # Save the options and conclude the options flow
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONFIG_EXPERIMENTAL_KEY,
                    default=self.config_entry.options.get(
                        CONFIG_EXPERIMENTAL_KEY, False
                    ),
                ): bool,
                vol.Required(
                    CONFIG_SCAN_INTERVAL_KEY,
                    default=self.config_entry.options.get(
                        CONFIG_SCAN_INTERVAL_KEY, 120
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=1440)),
                vol.Required(
                    CONFIG_DARK_HOURS_START,
                    default=self.config_entry.options.get(CONFIG_DARK_HOURS_START, 1),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required(
                    CONFIG_DARK_HOURS_END,
                    default=self.config_entry.options.get(CONFIG_DARK_HOURS_END, 5),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            }
        )

        # Display or re-display the form with the current options as defaults
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
