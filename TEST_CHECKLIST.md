# Lynk & Co 2FA Fix - Test Checklist

## Pre-Testing Setup

- [ ] Back up current integration configuration
- [ ] Enable debug logging:
  ```yaml
  logger:
    logs:
      custom_components.lynkco: debug
      custom_components.lynkco.config_flow: debug
      custom_components.lynkco.login_flow: debug
  ```
- [ ] Restart Home Assistant

## Test Cases

### 1. Fresh Installation ✓
- [ ] Navigate to Configuration → Integrations
- [ ] Click "+ Add Integration"
- [ ] Search for "Lynk & Co"
- [ ] Enter valid email address
- [ ] Enter valid password
- [ ] Enter valid VIN (17 characters)
- [ ] Click Submit
- [ ] Verify SMS received with 2FA code
- [ ] Enter 2FA code in the form
- [ ] Click Submit
- [ ] **Expected**: Integration added successfully
- [ ] **Expected**: Vehicle entities appear

### 2. Invalid Credentials (User Step)
- [ ] Start new integration setup
- [ ] Enter invalid email format (e.g., "notanemail")
- [ ] **Expected**: Error "The provided email is invalid."
- [ ] Enter valid email but wrong password
- [ ] **Expected**: Error "Login failed. Please check your credentials."
- [ ] Enter invalid VIN (e.g., too short)
- [ ] **Expected**: Error "The provided VIN is invalid."

### 3. 2FA Code Validation
- [ ] Start new integration setup
- [ ] Complete user step successfully
- [ ] Wait for 2FA form
- [ ] Click Submit without entering code
- [ ] **Expected**: Error "Please enter the 2FA code."
- [ ] Enter wrong 2FA code
- [ ] **Expected**: Error "The 2FA code is invalid or expired."
- [ ] Enter correct 2FA code
- [ ] **Expected**: Integration succeeds

### 4. Re-authentication Flow
- [ ] Have existing Lynk & Co integration
- [ ] Force re-auth (or wait for token expiration)
- [ ] Click "Fix" in notification
- [ ] Enter credentials
- [ ] Enter 2FA code
- [ ] **Expected**: Existing entry updated (not new entry created)
- [ ] **Expected**: Integration continues working
- [ ] **Expected**: No duplicate entries

### 5. Session Persistence (Critical Test)
- [ ] Start integration setup
- [ ] Enter valid credentials
- [ ] **Check logs**: Should see "Store credentials for use in 2FA step"
- [ ] **Check logs**: Should see "Store login details for 2FA step"
- [ ] When 2FA form appears, check logs
- [ ] **Expected**: Session should be reused (not recreated)
- [ ] Enter 2FA code
- [ ] **Expected**: Authentication succeeds
- [ ] **Check logs**: Should see "Success - save tokens"

### 6. Error Recovery
- [ ] Start integration setup
- [ ] Disconnect internet during login
- [ ] **Expected**: Error "Login failed"
- [ ] **Expected**: Can retry by re-entering credentials
- [ ] Reconnect internet and retry
- [ ] **Expected**: Should succeed

### 7. Multiple Attempts
- [ ] Start integration setup
- [ ] Enter wrong 2FA code 3 times
- [ ] **Expected**: Each time shows error but allows retry
- [ ] Enter correct code
- [ ] **Expected**: Still succeeds

## Success Criteria

All tests must pass:
- ✅ Fresh installation completes successfully with 2FA
- ✅ All error messages display correctly
- ✅ Session cookies are preserved between login and 2FA steps
- ✅ Re-authentication updates existing entry (no duplicates)
- ✅ Integration works after authentication

## Debug Checklist

If 2FA still fails, check:

1. **Session Management**:
   - [ ] Look for "Get or create the aiohttp session" in logs
   - [ ] Verify session is created only once
   - [ ] Check no "Session closed" between login and 2FA

2. **Cookie Preservation**:
   - [ ] Verify `x-ms-cpim-trans` cookie exists
   - [ ] Verify `x-ms-cpim-csrf` cookie exists
   - [ ] Check cookies are passed to `two_factor_authentication()`

3. **Data Persistence**:
   - [ ] Verify `self._login_details` is not None
   - [ ] Verify all 5 keys present (trans, csrf, page_view_id, referer, code_verifier)
   - [ ] Verify `self._email`, `self._password`, `self._vin` are set

4. **Token Flow**:
   - [ ] Verify `access_token` returned from 2FA
   - [ ] Verify `refresh_token` returned from 2FA
   - [ ] Verify `ccc_token` obtained from `send_device_login()`
   - [ ] Verify all tokens saved to storage

## Reporting Issues

If tests fail, provide:
1. Home Assistant version
2. Integration version
3. Full debug logs from config flow
4. Exact steps to reproduce
5. Which test case failed