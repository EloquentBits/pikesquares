from aiopath import AsyncPath

from pikesquares.domain.process_compose import (
    DNSMASQProcess,
    Process,
    ProcessMessages,
    ProcessAvailability,
)
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares import services

def dnsmasq_close():
    ...
    #logger.debug("dnsmasq closed")


async def dnsmasq_ping(dnsmasq_data: tuple[DNSMASQProcess, ProcessMessages]):
    process, msgs = dnsmasq_data
    # raise ServiceUnavailableError("dnsmasq down")
    return True


async def register_dnsmasq_process(
    context: dict,
    addresses: list[str],
    port: int = 5353,
    listen_address: str = "127.0.0.34",
) -> None:
    """register device"""

    async def dnsmasq_process_factory(svcs_container) -> tuple[Process, ProcessMessages]:
        """dnsmasq process-compose process"""

        conf = await svcs_container.aget(AppConfig)
        if conf.DNSMASQ_BIN and not await AsyncPath(conf.DNSMASQ_BIN).exists():
            raise AppConfigError(f"unable locate dnsmasq binary @ {conf.DNSMASQ_BIN}") from None

        #--interface=incusbr0
        cmd = f"{conf.DNSMASQ_BIN} "\
            "--bind-interfaces "\
            "--conf-file=/dev/null "\
            "--keep-in-foreground "\
            "--log-queries "\
            f"--log-facility {conf.log_dir / 'dnsmasq.log'} "\
            f"--port {port} "\
            f"--listen-address {listen_address} "\
            "--no-resolv "\
            "-u pikesquares -g pikesquares"

        for addr in addresses:
            cmd = cmd + f" --address {addr}"

        process_messages = ProcessMessages(
            title_start="dnsmasq starting",
            title_stop="abc",
        )
        process = Process(
            disabled=not conf.DNSMASQ_ENABLED,
            description="dns resolver",
            command=cmd,
            working_dir=conf.data_dir,
            availability=ProcessAvailability(),
            # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
            # ),
        )
        return process, process_messages

    services.register_factory(
        context,
        DNSMASQProcess,
        dnsmasq_process_factory,
        ping=dnsmasq_ping,
        on_registry_close=dnsmasq_close,
    )


