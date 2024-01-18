
import pydantic

class VirtualHost(pydantic.BaseModel):
    address: str
    certificate_path: str
    certificate_key: str
    server_names: list[str]
    protocol: str = "https"
    static_files_mapping: dict = {}

    @property
    def is_https(self):
        return all([
            self.certificate_key,
            self.certificate_path
        ])


