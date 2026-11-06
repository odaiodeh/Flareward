"""Receiver-local network transport settings for bounded capability subprocesses."""

from collections.abc import Mapping


def network_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Keep approved proxy/TLS transport without inheriting application authority."""
    names = {
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
    return {name: value for name, value in source.items() if name in names}
