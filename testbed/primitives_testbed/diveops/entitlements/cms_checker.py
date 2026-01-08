"""CMS entitlement checker hook.

This module provides the entitlement checker function that the CMS
uses to determine if a user has access to entitlement-gated pages.

Configure in CMSSettings.entitlement_checker_path:
    'primitives_testbed.diveops.entitlements.cms_checker.cms_entitlement_checker'
"""

from .services import user_has_all_entitlements


def cms_entitlement_checker(user, required_entitlements, page=None) -> bool:
    """Check if a user has the required entitlements for CMS access.

    This function is called by the CMS when checking access to
    ENTITLEMENT-level pages. It receives the user, the list of
    required entitlements from the page, and optionally the page itself.

    Args:
        user: The Django user requesting access
        required_entitlements: List of entitlement codes required by the page
                               (from ContentPage.required_entitlements)
        page: The ContentPage being accessed (optional, for context)

    Returns:
        True if user has ALL required entitlements, False otherwise
    """
    # Handle both single code string and list of codes
    if isinstance(required_entitlements, str):
        required_entitlements = [required_entitlements]

    if not required_entitlements:
        # No entitlements required = allow access
        return True

    return user_has_all_entitlements(user, required_entitlements)
