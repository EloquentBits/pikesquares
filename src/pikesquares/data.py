import logging
from typing import Optional

import pydantic

logger = logging.getLogger(__name__)


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

class ZmqPublishMessage(pydantic.BaseModel):
    action: str = ""
    event_type: str = "config-update"

    #"Sub-Emperor", "WSGI-App", "Managed-Service"
    service_name: str = ''
    service_id: str = ''
    parent_service_id: str = ''
    hc_ping_url: Optional[pydantic.HttpUrl]
    project_id: str = ''
    config: pydantic.Json

    #_api_client: HCAPI = pydantic.PrivateAttr()
    def __init__(self, **kwargs):
        logger.debug(f'ZMQ_PUBLISH_MSG: {kwargs=}')
        super().__init__(**kwargs)

    #if self.SERVICE_NAME == "Sub-Emperor":
    #    parent_service_id = None
    #if self.SERVICE_NAME in ("WSGI-App", "Managed-Service", "Cron-Job"):
    #    parent_service_id = self.parent.cuid

