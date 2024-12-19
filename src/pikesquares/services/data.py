from pathlib import Path

import pydantic


class VirtualHost(pydantic.BaseModel):
    address: str
    certificate_path: Path
    certificate_key: Path
    server_names: list[str]
    protocol: str = "https"
    static_files_mapping: dict = {}

    @property
    def is_https(self):
        return all([
            self.certificate_key,
            self.certificate_path
        ])


class Router(pydantic.BaseModel):
    router_id: str
    subscription_server_address: str
    app_name: str

    @pydantic.computed_field
    def subscription_server_port(self) -> int:
        try:
            return int(self.subscription_server_address.split(":")[-1])
        except IndexError:
            return 0

    @pydantic.computed_field
    def subscription_server_key(self) -> str:
        # return f"{self.app_name}.pikesquares.dev:{self.subscription_server_port}"
        print("subscription_server_key")
        return f"{self.app_name}.pikesquares.dev"

    @pydantic.computed_field
    def subscription_server_protocol(self) -> str:
        return "http" if str(self.subscription_server_port).startswith("9") else "https"


class WsgiAppOptions(pydantic.BaseModel):
    root_dir: Path
    pyvenv_dir: Path
    wsgi_file: Path
    wsgi_module: str
    routers: list[Router] = []
    project_id: str
    workers: int = 3


class RouterNode(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    name: str
    modifier1: int
    modifier2: int
    last_check: int
    pid: int
    uid: int
    gid: int
    requests: int
    last_requests: int
    tx: int
    rx: int
    cores: int
    load: int
    weight: int
    wrr: int
    ref: int
    failcnt: int
    death_mark: int


class RouterSubscription(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    key: str  # 'muffled-castle.pikesquares.dev:5700'
    hash: int
    hits: int = pydantic.Field(ge=0)
    sni_enabled: int
    nodes: list[RouterNode]


class RouterStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    version: str
    pid: int = pydantic.Field(ge=0)
    uid: int = pydantic.Field(ge=0)
    gid: int = pydantic.Field(ge=0)
    cwd: str
    active_sessions: int = pydantic.Field(ge=0)
    http: list[str]  # ['0.0.0.0:8034', '127.0.0.1:5700'],
    subscriptions: list[RouterSubscription]
    cheap: int = pydantic.Field(ge=0)


class DeviceAppStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    id: str  # "project_sandbox.json",
    pid: int
    born: int
    last_mod: int
    last_heartbeat: int
    loyal: int
    ready: int
    accepting: int
    last_loyal: int
    last_ready: int
    last_accepting: int
    first_run: int
    last_run: int
    cursed: int
    zerg: int
    on_demand: str
    uid: int
    gid: int
    monitor: str
    respawns: int


class DeviceStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    version: str
    pid: int = pydantic.Field(ge=0)
    uid: int = pydantic.Field(ge=0)
    gid: int = pydantic.Field(ge=0)
    cwd: str
    emperor: list[str]
    emperor_tyrant: int
    throttle_level: int
    vassals: list[DeviceAppStats]
    blacklist: list


class SocketStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    name: str  # "127.0.0.1:4017"
    proto: str  # "uwsgi"
    queue: int
    max_queue: int
    shared: int
    can_offload: int


class WorkerAppStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    id: int
    modifier1: int
    mountpoint: str
    startup_time: int
    requests: int
    exceptions: int
    chdir: str


class WorkerCoresStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    id: int
    requests: int
    static_requests: int
    routed_requests: int
    offloaded_requests: int
    write_errors: int
    read_errors: int
    in_request: int
    vars: list
    req_info: dict


class WorkerStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    id: int
    pid: int
    accepting: int
    requests: int
    delta_requests: int
    exceptions: int
    harakiri_count: int
    signals: int
    signal_queue: int
    status: str  # "idle",
    rss: int
    vsz: int
    running_time: int
    last_spawn: int
    respawn_count: int
    tx: int
    avg_rt: int
    apps: list[WorkerAppStats]


class AppStats(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    version: str
    listen_queue: int
    listen_queue_errors: int
    signal_queue: int
    load: int
    pid: int
    uid: int
    gid: int
    cwd: str
    locks: list[dict[str, int]]
    sockets: list[SocketStats]
    workers: list[WorkerStats]
