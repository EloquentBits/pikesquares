from .base import ServiceBase


class Device(ServiceBase, table=True):

    machine_id: str
