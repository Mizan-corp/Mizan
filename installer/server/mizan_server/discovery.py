"""LAN installs: make `mizan.local` reach this server.

Advertises the name over mDNS (Bonjour), which Windows 10+, macOS, iOS, most
Linux desktops and recent Android resolve without any setup, plus a
`_https._tcp` service so the server shows up in network browsers. If another
Mizan server already uses the name, this one is still reachable by its
address and computer name.
"""
from __future__ import annotations

import logging
import socket

logger = logging.getLogger("mizan.discovery")

HOSTNAME = "mizan.local."


class Advertiser:
    def __init__(self, port: int):
        self.port = port
        self._zc = None
        self._info = None

    def start(self) -> list[str]:
        try:
            from zeroconf import IPVersion, ServiceInfo, Zeroconf
        except ImportError:  # running from source without it
            logger.warning("zeroconf isn't installed: mizan.local won't be advertised")
            return []
        from mizan_server.tls import lan_addresses

        addresses = lan_addresses()
        if not addresses:
            logger.warning("No network address found: mizan.local won't be advertised")
            return []
        self._info = ServiceInfo(
            "_https._tcp.local.",
            "Mizan._https._tcp.local.",
            addresses=[socket.inet_aton(a) for a in addresses],
            port=self.port,
            server=HOSTNAME,
            properties={"path": "/", "product": "mizan"},
        )
        try:
            self._zc = Zeroconf(ip_version=IPVersion.V4Only)
            self._zc.register_service(self._info, allow_name_change=True)
        except Exception:
            logger.exception("Couldn't advertise mizan.local")
            self.stop()
            return []
        logger.info("Advertising %s on %s", HOSTNAME.rstrip("."), ", ".join(addresses))
        return addresses

    def stop(self) -> None:
        if self._zc is None:
            return
        try:
            if self._info is not None:
                self._zc.unregister_service(self._info)
            self._zc.close()
        except Exception:
            pass
        self._zc = None
