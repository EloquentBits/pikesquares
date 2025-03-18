import json
from pathlib import Path
from typing import Union

import structlog

from uwsgiconf.config import (
    Section as _Section, 
    TypeSection, 
    Configuration as _Configuration,
)
from uwsgiconf.typehints import Strlist
from uwsgiconf.utils import listify
from uwsgiconf.formatters import (
    FormatterBase,
    ArgsFormatter,
    IniFormatter,
)

logger = structlog.get_logger()


class JSONFormatter(FormatterBase):
    """Translates a configuration as JSON file."""

    alias: str = "json"

    def format(self) -> str:
        config = {}
        for section_name, key, value in self.iter_options():
            # print(f"{section_name=}, {str(key)=}, {value=}")

            if not section_name in config:
                config[section_name] = {}

            if isinstance(key, tuple):
                _, key = key

            if str(key) == "plugin":
                try:
                    existing_plugins = config[section_name]["plugin"]
                except KeyError:
                    config[section_name][str(key)] = str(value).strip()
                else:
                    existing_plugins = existing_plugins.split(",")
                    existing_plugins.append(str(value).strip())
                    config[section_name][str(key)] = ",".join(existing_plugins)
                    #p rint(config[section_name][str(key)])
            else:
                config[section_name][str(key)] = str(value).strip()

        return json.dumps(config)


FORMATTERS: dict[str, type[FormatterBase]] = {formatter.alias: formatter for formatter in (
    ArgsFormatter,
    IniFormatter,
    JSONFormatter,
)}


class Configuration(_Configuration):
    """Available formatters by alias."""

    def format(self, *, do_print: bool = False, formatter: str = "ini") -> Strlist:
        """Applies formatting to configuration.

        :param do_print: Whether to print out formatted config.
        :param formatter: Formatter alias to format options. Default: ini.

        """

        formatter = FORMATTERS[formatter]
        formatted = formatter(self.sections).format()

        if do_print:
            logger.debug(formatted)

        return formatted

    def tofile(self, filepath: Union[str, Path] = None) -> str:
        """Saves configuration into a file and returns its path.

        Convenience method.

        :param filepath: Filepath to save configuration into.
            If not provided a temporary file will be automatically generated.

        """
        if filepath is None:
            with NamedTemporaryFile(prefix=f'{self.alias}_', suffix='.ini', delete=False) as f:
                filepath = f.name

        else:
            filepath = Path(filepath).absolute()

            if filepath.is_dir():
                filepath = filepath / f'{self.alias}.ini'

        filepath = str(filepath)

        with open(filepath, 'w') as target_file:
            target_file.write(self.format())
            target_file.flush()

        return filepath


class Section(_Section):

    def include(self, target: Union["Section", list["Section"], str, list[str]]) -> TypeSection:
        """Includes target contents into config.

        :param target: File path or Section to include.

        """
        for target_ in listify(target):
            if isinstance(target_, Section):
                target_ = ":" + target_.name
            self._set("ini", f"%s:{target_}", multi=True)

        return self

    def as_configuration(self, **kwargs) -> "Configuration":
        """Returns configuration object including only one (this very) section.

        :param kwargs: Configuration objects initializer arguments.
        """
        return Configuration([self], **kwargs)


"""
class ManagedServiceSection(Section):

    def __init__(self, svc_model, command: str):
        super().__init__(name="uwsgi")
        self.svc_model = svc_model
        self.command = command

        #if pre_start_section:
        #    self.include(pre_start_section)
        #executable_path, *_ = command.split(' ')
        #executable_name = Path(executable_path).stem
        #self.main_process.run_command_on_event(f"touch {pid_path}")
        #if env_vars:
        #    self._setup_environment_variables(env_vars)

        self.master_process.attach_process(
            self.command,
            pidfile=svc_model.run_dir / f"{svc_model.name}.pid",
            daemonize=True,
            uid=svc_model.uid,
            gid=svc_model.gid,
        )

        self.monitoring.set_stats_params(
            address=str(svc_model.stats_address)
        )

        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(
                filepath=str(svc_model.log_file)
            )
        )

    #def _setup_environment_variables(self, env_vars):
    #    for key, value in env_vars.items():
    #        self.env(key, value)

"""



#class CronJobSection(Section):

#    def _setup_environment_variables(self, env_vars):
#        for key, value in env_vars.items():
#            self.env(key, value)

#    def __init__(self, conf, command, env_vars=None, **kwargs):
#        super().__init__(
#            name="uwsgi",
#            runtime_dir=conf.RUN_DIR,
#            owner=f"{conf.RUN_AS_UID}:{conf.RUN_AS_GID}"
#        )
#        if env_vars is not None:
#            self._setup_environment_variables(env_vars)

        # -15 -1 -1 -1 -1 - every 15 minute (minus X means */X, minus 1 means *)
#        self.master_process.add_cron_task(
#            command,
#            **kwargs
#        )
