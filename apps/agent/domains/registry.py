"""Registre global des domaines et verticales.

Usage :
    from domains.registry import register_vertical, get_vertical, list_verticals

    register_vertical(ma_config)
    v = get_vertical("droit", "cabinets")
"""

from domains.base import VerticalConfig

_DOMAINS: dict[str, dict[str, VerticalConfig]] = {}


def register_vertical(config: VerticalConfig) -> None:
    if config.domain not in _DOMAINS:
        _DOMAINS[config.domain] = {}
    _DOMAINS[config.domain][config.id] = config


def get_vertical(domain: str, vertical_id: str) -> VerticalConfig:
    return _DOMAINS[domain][vertical_id]


def list_verticals(domain: str) -> list[VerticalConfig]:
    return list(_DOMAINS.get(domain, {}).values())


def list_domains() -> list[str]:
    return list(_DOMAINS.keys())
