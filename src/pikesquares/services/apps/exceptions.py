
class UvSyncError(Exception):
    pass


class UvPipInstallError(Exception):
    pass


class PythonRuntimeCheckError(Exception):
    pass

class PythonRuntimeDjangoCheckError(Exception):
    pass

class PythonRuntimeInitError(Exception):
    pass


class DjangoCheckError(Exception):
    pass


class DjangoDiffSettingsError(Exception):
    pass


class UvCommandExecutionError(Exception):
    pass
