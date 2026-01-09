"""Diver preferences module for progressive preference collection."""

__all__ = [
    "PreferenceDefinition",
    "PartyPreference",
]


def __getattr__(name):
    if name == "PreferenceDefinition":
        from .models import PreferenceDefinition
        return PreferenceDefinition
    if name == "PartyPreference":
        from .models import PartyPreference
        return PartyPreference
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
