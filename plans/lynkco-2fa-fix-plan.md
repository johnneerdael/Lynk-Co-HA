# Lynk & Co Home Assistant Integration - 2FA Config Flow Fix Plan

## Problem Statement

The Lynk & Co Home Assistant integration's config_flow.py requires 2FA (SMS-based) for authentication, but the current implementation has issues that prevent successful 2FA code entry during the integration setup process. Users receive the SMS code but authentication fails.

## Current Implementation Analysis

### File Structure
- [`config_flow.py`](../custom_components/lynkco/config_flow.py) - Main config flow handler
- [`login_flow.py`](../custom_components/lynkco/login_flow.py) - Login and 2FA logic
- [`strings.json`](../custom_components/lynkco/strings.json) - UI text strings
- [`translations/en.json`](../custom_components/lynkco/translations/en.json) - English translations

### Current Flow (Lines 62-185 in config_flow.py)

```
async_step_user() → async_step_two_factor() → create_entry/abort
```

### Identified Issues

#### Issue 1: Session Management Problem
**Location**: [`config_flow.py:66-68`](../custom_components/lynkco/config_flow.py:66)

```python
jar = aiohttp.CookieJar(quote_cookie=False)
session = aiohttp.ClientSession(cookie_jar=jar)
self.context['session'] = session
```

The session is created at the START of `async_step_user`, even when `user_input` is None (first form display). This means:
- A new session is created every time the step is called
- When returning to show the form with errors, a new session overwrites the previous one
- The session cookies from the login step may be lost

**Fix**: Only create the session when actually needed (when `user_input` is provided and valid).

#### Issue 2: Session Not Properly Preserved Between Steps
The session is stored in `self.context['session']`, but the context handling for multi-step flows may not preserve this correctly across HA restarts or reloads.

**Best Practice**: Store session-related data in instance variables (`self.session`) and ensure proper cleanup.

#### Issue 3: Potential Race Condition / Timing Issue
**Location**: [`login_flow.py`](../custom_components/lynkco/login_flow.py)

The 2FA flow involves multiple HTTP calls:
1. `postVerification()` - Submit the 2FA code
2. `getRedirect()` - Get authorization code
3. `getTokens()` - Exchange code for tokens

If timing or cookie state is incorrect, the verification may fail silently.

#### Issue 4: Error Handling Gaps
**Location**: [`config_flow.py:173-178`](../custom_components/lynkco/config_flow.py:173)

```python
except Exception as e:
    _LOGGER.error(
        "Error during two-factor authentication: %s", e, exc_info=True
    )
    errors["base"] = "two_factor_auth_failed"
```

The generic exception catch may hide specific errors. Better error handling with specific exceptions would help debug issues.

#### Issue 5: Missing Error String
The error key `"two_factor_auth_failed"` is used in code but not defined in [`strings.json`](../custom_components/lynkco/strings.json) or translations.

## Research: Best Practices from Other Integrations

### Wyze Integration Pattern (Recommended)
```python
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    def __init__(self):
        self.email = None
        self.password = None
        # Store credentials as instance variables
    
    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=SCHEMA)
        
        try:
            await self.client.login(user_input[...])
        except TwoFactorAuthenticationEnabled:
            # Store credentials for use in 2FA step
            self.email = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            return await self.async_step_2fa()
        # ... handle success/errors
    
    async def async_step_2fa(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="2fa", data_schema=SCHEMA_2FA)
        
        # Use stored credentials + 2FA code
        token = await self.client.login_with_2fa(user_input[CONF_CODE])
        return self.async_create_entry(...)
```

### Key Improvements

1. **Instance Variables**: Store data in `self.` variables, not `self.context`
2. **Session Lifecycle**: Create session once, reuse across steps, close on completion
3. **Clear Step Separation**: Each step has single responsibility
4. **Proper Error Mapping**: Map specific exceptions to user-friendly errors

## Proposed Solution

### Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   async_step_user   │────▶│async_step_two_factor│────▶│   Create Entry /    │
│                     │     │                     │     │   Update + Reload   │
│ - Validate input    │     │ - Show 2FA form     │     │                     │
│ - Start login flow  │     │ - Verify code       │     │                     │
│ - Trigger SMS       │     │ - Complete login    │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
         │                           │
         │  Store in self.*:         │  Use from self.*:
         │  - session                │  - session
         │  - email, password, vin   │  - login_details
         │  - login_details          │  - code_verifier
         │  - code_verifier          │
         ▼                           ▼
```

### Code Changes Required

#### 1. config_flow.py - Major Refactoring

```python
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
        self._reauth_entry: ConfigEntry | None = None

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
        errors = {}
        
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "message": "Please re-enter your credentials to re-authenticate."
                },
            )
        
        return await self.async_step_user(user_input)
```

#### 2. strings.json and translations/en.json Updates

Add missing error strings:

```json
{
  "config": {
    "error": {
      "invalid_email": "The provided email is invalid.",
      "invalid_vin": "The provided VIN is invalid.",
      "invalid_2fa_code": "The 2FA code is invalid or expired. Please try again.",
      "login_failed": "Login failed. Please check your credentials.",
      "missing_details": "Please fill in all required fields.",
      "missing_2fa_code": "Please enter the 2FA code.",
      "two_factor_auth_failed": "Two-factor authentication failed. Please try again.",
      "token_error": "Failed to obtain authentication token."
    },
    "step": {
      "two_factor": {
        "title": "Two-Factor Authentication",
        "description": "A verification code has been sent to your phone. Please enter it below.",
        "data": {
          "2fa": "Verification Code"
        }
      },
      "reauth_confirm": {
        "title": "Re-authentication Required",
        "description": "Your session has expired. Please re-enter your credentials."
      }
    }
  }
}
```

## Implementation Checklist

- [ ] Refactor `ConfigFlow.__init__()` to use instance variables
- [ ] Add `_get_session()` and `_close_session()` helper methods
- [ ] Refactor `async_step_user()` to properly handle session lifecycle
- [ ] Refactor `async_step_two_factor()` to use instance variables
- [ ] Add `async_step_reauth_confirm()` for proper reauth flow
- [ ] Update error handling with specific exception types
- [ ] Update `strings.json` with all error messages
- [ ] Update `translations/en.json` with all error messages
- [ ] Test the complete flow: user → 2fa → success
- [ ] Test the reauth flow
- [ ] Test error cases (invalid credentials, invalid 2FA code, network errors)

## Testing Recommendations

1. **Unit Tests**: Mock the login_flow functions to test config_flow logic
2. **Integration Tests**: Test with real Lynk & Co credentials (in a controlled environment)
3. **Edge Cases**:
   - What happens if user goes back/forward in the browser during 2FA?
   - What happens if HA restarts during the config flow?
   - What happens if the SMS code expires?

## Alternative Approaches Considered

### 1. External Step Approach (Alexa Media Style)
Using `async_external_step` to redirect to an external auth page. Not suitable because Lynk & Co doesn't have an OAuth2 endpoint - they use a custom B2C flow.

### 2. IMAP Email Polling (Arlo Style)
Automatically read 2FA codes from email. Too fragile and requires additional configuration for email access.

### 3. TOTP Secret Storage
Store a TOTP secret and generate codes automatically. Not possible because Lynk & Co uses SMS-based 2FA, not TOTP.

## Conclusion

The current implementation has session management issues that cause the 2FA flow to fail. By refactoring to use instance variables, properly managing the HTTP session lifecycle, and improving error handling, the 2FA flow should work correctly.

The recommended approach follows the Wyze integration pattern, which is well-tested and follows Home Assistant best practices for multi-step config flows with 2FA.