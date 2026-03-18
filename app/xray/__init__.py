from random import randint
from typing import TYPE_CHECKING, Dict, Sequence

from app.models.proxy import ProxyHostSecurity
from app.utils.store import DictStorage
from app.utils.system import check_port
from app.xray import operations
from app.xray.config import XRayConfig
from app.xray.core import XRayCore
from app.xray.node import XRayNode
from config import (
    HYSTERIA2_ENABLED,
    HYSTERIA2_PORT,
    JUICITY_ENABLED,
    JUICITY_PORT,
    TUIC_ENABLED,
    TUIC_PORT,
    XRAY_ASSETS_PATH,
    XRAY_EXECUTABLE_PATH,
    XRAY_JSON,
)
from xray_api import XRay as XRayAPI
from xray_api import exceptions, types
from xray_api import exceptions as exc

core = XRayCore(XRAY_EXECUTABLE_PATH, XRAY_ASSETS_PATH)

# Search for a free API port
try:
    for api_port in range(randint(10000, 60000), 65536):
        if not check_port(api_port):
            break
finally:
    config = XRayConfig(XRAY_JSON, api_port=api_port)
    del api_port

api = XRayAPI(config.api_host, config.api_port)

nodes: Dict[int, XRayNode] = {}

if HYSTERIA2_ENABLED:
    from config import HYSTERIA2_OBFS_PASSWORD

    _hy2_inbound = {
        "tag": "Hysteria2",
        "protocol": "hysteria2",
        "network": "hysteria2",
        "tls": "tls",
        "port": HYSTERIA2_PORT,
        "sni": [],
        "host": [],
        "path": "",
        "header_type": "",
        "is_fallback": False,
        "obfs_password": HYSTERIA2_OBFS_PASSWORD,
    }
    config.inbounds.append(_hy2_inbound)
    config.inbounds_by_tag["Hysteria2"] = _hy2_inbound
    config.inbounds_by_protocol["hysteria2"] = [_hy2_inbound]

if TUIC_ENABLED:
    _tuic_inbound = {
        "tag": "TUIC",
        "protocol": "tuic",
        "network": "quic",
        "tls": "tls",
        "port": TUIC_PORT,
        "sni": [],
        "host": [],
        "path": "",
        "header_type": "",
        "is_fallback": False,
    }
    config.inbounds.append(_tuic_inbound)
    config.inbounds_by_tag["TUIC"] = _tuic_inbound
    config.inbounds_by_protocol["tuic"] = [_tuic_inbound]

if JUICITY_ENABLED:
    _juicity_inbound = {
        "tag": "Juicity",
        "protocol": "juicity",
        "network": "quic",
        "tls": "tls",
        "port": JUICITY_PORT,
        "sni": [],
        "host": [],
        "path": "",
        "header_type": "",
        "is_fallback": False,
    }
    config.inbounds.append(_juicity_inbound)
    config.inbounds_by_tag["Juicity"] = _juicity_inbound
    config.inbounds_by_protocol["juicity"] = [_juicity_inbound]


if TYPE_CHECKING:
    from app.db.models import ProxyHost


@DictStorage
def hosts(storage: dict):
    from app.db import GetDB, crud

    storage.clear()
    with GetDB() as db:
        for inbound_tag in config.inbounds_by_tag:
            inbound_hosts: Sequence[ProxyHost] = crud.get_hosts(db, inbound_tag)

            storage[inbound_tag] = [
                {
                    "remark": host.remark,
                    "address": [i.strip() for i in host.address.split(',')] if host.address else [],
                    "port": host.port,
                    "path": host.path if host.path else None,
                    "sni": [i.strip() for i in host.sni.split(',')] if host.sni else [],
                    "host": [i.strip() for i in host.host.split(',')] if host.host else [],
                    "alpn": host.alpn.value,
                    "fingerprint": host.fingerprint.value,
                    # None means the tls is not specified by host itself and
                    #  complies with its inbound's settings.
                    "tls": None
                    if host.security == ProxyHostSecurity.inbound_default
                    else host.security.value,
                    "allowinsecure": host.allowinsecure,
                    "mux_enable": host.mux_enable,
                    "fragment_setting": host.fragment_setting,
                    "noise_setting": host.noise_setting,
                    "random_user_agent": host.random_user_agent,
                    "use_sni_as_host": host.use_sni_as_host,
                } for host in inbound_hosts if not host.is_disabled
            ]


__all__ = [
    "config",
    "hosts",
    "core",
    "api",
    "nodes",
    "operations",
    "exceptions",
    "exc",
    "types",
    "XRayConfig",
    "XRayCore",
    "XRayNode",
]
