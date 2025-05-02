
from pikesquares.domain.wsgi_app import WsgiApp

class FakeWsgiAppRepository:
    def __init__(self, existing_wsgi_apps: WsgiApp | None = None):
                self._wsgi_apps = existing_wsgi_apps
                self.added_wsgi_apps = None

    async def get_by_name(self, name:str) -> WsgiApp| None:
        return self._wsgi_apps

    async def add(self, wsgi_apps: WsgiApp):
        self.added_wsgi_apps = wsgi_apps