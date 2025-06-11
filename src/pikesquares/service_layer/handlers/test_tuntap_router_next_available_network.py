import pytest
from ipaddress import IPv4Network
import netifaces

from pikesquares.service_layer.handlers.routers import tuntap_router_next_available_network

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lan_addresses, existing_networks, expected_result",
    [
        # Case 1: LAN 172.28.1.1, existing_networks=[], res: 172.28.100.0/24
        (
            [{"addr": "172.28.1.1", "netmask": "255.255.255.0"}],
            [],
            "172.28.100.0/24"
        ),
        # Case 2: LAN 172.28.1.1, existing_networks=[172.28.100.0/24], res: 172.28.101.0/24
        (
            [{"addr": "172.28.1.1", "netmask": "255.255.255.0"}],
            [IPv4Network("172.28.100.0/24")],
            "172.28.101.0/24"
        ),
        # Case 3: LAN 172.28.1.1, existing_networks=[172.28.100.0/24, 172.28.101.0/24, 172.28.105.0/24], res: 172.28.102.0/24
        (
            [{"addr": "172.28.1.1", "netmask": "255.255.255.0"}],
            [IPv4Network("172.28.100.0/24"), IPv4Network("172.28.101.0/24"), IPv4Network("172.28.105.0/24")],
            "172.28.102.0/24"
        ),
        # Case 4: LAN 172.28.100.10, existing_networks=[], res: 172.28.1.0/24
        (
            [{"addr": "172.28.100.10", "netmask": "255.255.255.0"}],
            [],
            "172.28.1.0/24"
        ),
        # Case 5: LAN 172.28.100.10, existing_networks=[172.28.1.0/24, 172.28.3.0/24, 172.28.5.0/24], res: 172.28.2.0/24
        (
            [{"addr": "172.28.100.10", "netmask": "255.255.255.0"}],
            [IPv4Network("172.28.1.0/24"), IPv4Network("172.28.3.0/24"), IPv4Network("172.28.5.0/24")],
            "172.28.2.0/24"
        ),
        # Case 6: LAN 172.28.100.10, existing_networks=[172.28.1.0/24, 172.28.3.0/24, 172.28.5.0/24], res: 172.28.2.0/24
        (
            [{"addr": "172.28.100.10", "netmask": "255.255.255.0"}],
            [IPv4Network("172.28.1.0/24"), IPv4Network("172.28.3.0/24"), IPv4Network("172.28.5.0/24")],
            "172.28.2.0/24"
        ),
        # Case 7: LAN 172.28.1.1, 172.28.100.10, existing_networks=[], res: 172.28.200.0/24
        (
            [
                {"addr": "172.28.1.1", "netmask": "255.255.255.0"},
                {"addr": "172.28.100.10", "netmask": "255.255.255.0"}
            ],
            [],
            "172.28.200.0/24"
        ),
        # Case 8: LAN 172.28.1.1, 172.28.100.10, existing_networks=[172.28.200.0/24, 172.28.201.0/24, 172.28.205.0/24], res: 172.28.202.0/24
        (
            [
                {"addr": "172.28.1.1", "netmask": "255.255.255.0"},
                {"addr": "172.28.100.10", "netmask": "255.255.255.0"}
            ],
            [IPv4Network("172.28.200.0/24"), IPv4Network("172.28.201.0/24"), IPv4Network("172.28.205.0/24")],
            "172.28.202.0/24"
        ),
        # Case 9: LAN 172.28.1.1, 172.28.100.10, existing_networks=[172.28.200.0/24, 172.28.201.0/24, 172.28.205.0/24], res: 172.28.202.0/24
        (
            [
                {"addr": "172.28.1.1", "netmask": "255.255.255.0"},
                {"addr": "172.28.100.10", "netmask": "255.255.255.0"}
            ],
            [IPv4Network("172.28.200.0/24"), IPv4Network("172.28.201.0/24"), IPv4Network("172.28.205.0/24")],
            "172.28.202.0/24"
        ),
        # Case 10: LAN 172.28.1.1, 172.28.100.10, 172.28.205.0, res: Error
        (
            [
                {"addr": "172.28.1.1", "netmask": "255.255.255.0"},
                {"addr": "172.28.100.10", "netmask": "255.255.255.0"},
                {"addr": "172.28.205.0", "netmask": "255.255.255.0"}
            ],
            [],
            None  
        ),
    ],
    ids=[
        "LAN_192.168.1.1_empty",
        "LAN_192.168.1.1_existing_100",
        "LAN_192.168.1.1_existing_100_101_105",
        "LAN_192.168.100.10_empty",
        "LAN_192.168.100.10_existing_1",
        "LAN_192.168.100.10_existing_1_3_5",
        "LAN_1.1_100.10_empty",
        "LAN_1.1_100.10_existing_1",
        "LAN_1.1_100.10_existing_200_201_205",
        "LAN_1.1_100.10_205_error",
    ]
)
async def test_tuntap_router_next_available_network(monkeypatch, lan_addresses, existing_networks, expected_result):
    class FakeUnitOfWork:
        class TuntapRouters:
            async def list(self):
                return [
                    type("FakeRouter", (), {
                        "ip": str(en.network_address + 1),
                        "netmask": "255.255.255.0"
                    }) for en in existing_networks
                ]
        tuntap_routers = TuntapRouters()

    monkeypatch.setattr(netifaces, "interfaces", lambda: ["eth0"])
    monkeypatch.setattr(netifaces, "ifaddresses", lambda iface: {
        netifaces.InterfaceType.AF_INET: lan_addresses
    })

    if expected_result is None:
        with pytest.raises(RuntimeError, match="No available subnet range found"):
            await tuntap_router_next_available_network(FakeUnitOfWork())
    else:
        result = await tuntap_router_next_available_network(FakeUnitOfWork())
        assert isinstance(result, IPv4Network)
        assert str(result) == expected_result