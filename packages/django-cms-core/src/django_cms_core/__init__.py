__version__ = "0.1.0"

__all__ = [
    "ContentPage",
    "ContentBlock",
    "CMSSettings",
    "Redirect",
    "PageStatus",
    "AccessLevel",
]


def __getattr__(name):
    if name in ("ContentPage", "ContentBlock", "CMSSettings", "Redirect", "PageStatus", "AccessLevel"):
        from . import models
        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
