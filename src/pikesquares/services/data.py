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
    subscription_notify_socket: Path
    app_name: str

    @pydantic.computed_field
    def subscription_server_port(self) -> int:
        try:
            return int(self.subscription_server_address.split(":")[-1])
        except IndexError:
            return 0

    @pydantic.computed_field
    def subscription_server_key(self) -> str:
        return f"{self.app_name}.pikesquares.dev:{self.subscription_server_port}"

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
