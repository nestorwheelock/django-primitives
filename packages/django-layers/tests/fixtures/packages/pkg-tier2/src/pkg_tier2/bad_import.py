"""Tier 2 file with illegal import from tier 3."""

from pkg_tier3.utils import helper

def use_helper():
    return helper()
