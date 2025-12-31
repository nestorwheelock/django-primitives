"""Exceptions for django-modules."""


class ModuleError(Exception):
    """Base exception for module errors."""

    pass


class ModuleDisabled(ModuleError):
    """Raised when attempting to use a disabled module."""

    def __init__(self, module_key: str, org=None):
        self.module_key = module_key
        self.org = org
        if org:
            message = f"Module '{module_key}' is disabled for organization '{org}'"
        else:
            message = f"Module '{module_key}' is disabled"
        super().__init__(message)


class ModuleNotFound(ModuleError):
    """Raised when a module key does not exist."""

    def __init__(self, module_key: str):
        self.module_key = module_key
        super().__init__(f"Module '{module_key}' does not exist")


class ModulesConfigError(ModuleError):
    """Raised when modules configuration is invalid."""

    pass
