from pikesquares.domain.device import DeviceUWSGIOptions


class FakeDeviceUWSGIOptionsRepository:
    def __init__(self, existing_uwsgi_options: DeviceUWSGIOptions | None = None):
        self._uwsgi_options = existing_uwsgi_options
        self.added_uwsgi_options = None

    async def get_by_device_id(self, name:str) -> DeviceUWSGIOptions | None:
        return self._uwsgi_options

    async def add(self, uwsgi_options: DeviceUWSGIOptions):
        self.added_uwsgi_options = uwsgi_options