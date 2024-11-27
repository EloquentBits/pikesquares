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


class WsgiAppOptions(pydantic.BaseModel):

    root_dir: Path
    pyvenv_dir: Path
    wsgi_file: Path
    wsgi_module: str
    router_id: str
    project_id: str
    workers: int = 3


