from pathlib import Path

import pydantic


class VersionParts(pydantic.BaseModel):
    major: int
    minor: int
    patch: int


class PythonRuntimeVersion(pydantic.BaseModel):
    """
    [{'key': 'cpython-3.14.3-linux-x86_64-gnu',
      'version': '3.14.3',
      'version_parts': {'major': 3, 'minor': 14, 'patch': 3},
      'path': '/home/pk/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14',
      'symlink': None,
      'url': None,
      'os': 'linux',
      'variant': 'default',
      'implementation': 'cpython',
      'arch': 'x86_64',
      'libc': 'gnu'},
    """

    key: str
    version: str
    version_parts: VersionParts
    path: Path | None = None
    symlink: Path | None = None
    url: pydantic.HttpUrl | None = None
    variant: str
    implementation: str
    arch: str
    libc: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def uwsgi_plugin_name(self) -> str:
        return f"{self.implementation}_{self.version.replace('.', '_')}"
