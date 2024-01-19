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


