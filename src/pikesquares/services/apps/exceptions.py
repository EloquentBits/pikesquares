
class UvSyncError(Exception):
    pass


class UvPipInstallError(Exception):
    pass


class UvPipListError(Exception):
    pass


class PythonRuntimeCheckError(Exception):
    pass


class PythonRuntimeDjangoCheckError(Exception):
    pass


class PythonRuntimeInitError(Exception):
    pass

class PythonRuntimeDepsInstallError(Exception):
    pass

class DjangoCheckError(Exception):
    pass


class DjangoSettingsError(Exception):
    pass


class DjangoDiffSettingsError(Exception):
    pass


class UvCommandExecutionError(Exception):
    pass
