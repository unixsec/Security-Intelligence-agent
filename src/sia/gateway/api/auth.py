"""API authentication — backward-compatible shim.

The real auth logic lives in sia.auth.rbac. This module re-exports
the main dependency so existing routers that import `verify_api_key`
continue to work without changes.
"""

from sia.auth.rbac import get_current_user

# Existing routers use `Depends(verify_api_key)`.
# Re-export under the old name for backward compatibility.
verify_api_key = get_current_user
