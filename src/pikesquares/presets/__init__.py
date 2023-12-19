from typing import Dict, List, Type
from pathlib import Path
import json
from typing import Union

from uwsgiconf.config import (
    Section as _Section, 
    TypeSection, 
    Configuration as _Configuration,
)
from uwsgiconf.typehints import Strlist
from uwsgiconf.utils import listify
from uwsgiconf.formatters import (
    FORMATTERS, 
    FormatterBase, 
    ArgsFormatter,
    IniFormatter,
)


class JSONFormatter(FormatterBase):
    """Translates a configuration as JSON file."""

    alias: str = 'json'

    def format(self) -> str:
        config = {}
        for section_name, key, value in self.iter_options():
            if key == 'plugin':
                continue
            if not section_name in config:
                config[section_name] = {}
            if isinstance(key, tuple):
                _, key = key
            config[section_name][str(key)] =  str(value).strip()
        return json.dumps(config)

FORMATTERS: Dict[str, Type[FormatterBase]] = {formatter.alias: formatter for formatter in (
    ArgsFormatter,
    IniFormatter,
    JSONFormatter,
)}
"""Available formatters by alias."""
class Configuration(_Configuration):

    def format(self, *, do_print: bool = False, formatter: str = 'ini') -> Strlist:
        """Applies formatting to configuration.

        :param do_print: Whether to print out formatted config.
        :param formatter: Formatter alias to format options. Default: ini.

        """

        formatter = FORMATTERS[formatter]
        formatted = formatter(self.sections).format()

        if do_print:
            print(formatted)

        return formatted


class Section(_Section):

    def include(self, target: Union['Section', List['Section'], str, List[str]]) -> TypeSection:
        """Includes target contents into config.

        :param target: File path or Section to include.

        """
        for target_ in listify(target):
            if isinstance(target_, Section):
                target_ = ':' + target_.name
            self._set('ini', f"%s:{target_}", multi=True)

        return self


    def as_configuration(self, **kwargs) -> 'Configuration':
        """Returns configuration object including only one (this very) section.

        :param kwargs: Configuration objects initializer arguments.
        
        """
        return Configuration([self], **kwargs)




class ManagedServiceSection(Section):

    def __init__(self, client_config, project_id, service_id, command, pre_start_section=None, env_vars=None):
        super().__init__(
            name="uwsgi",
            runtime_dir=client_config.RUN_DIR,
            owner=f"{client_config.RUN_AS_UID}:{client_config.RUN_AS_GID}",
            touch_reload=str(
                (Path(client_config.CONFIG_DIR) / f"{project_id}" / "apps" / f"{service_id}.json").resolve()
            )
        )
        self.project_id = project_id
        self.service_id = service_id

        self.client_config = client_config

        if pre_start_section:
            self.include(pre_start_section)

        executable_path, *_ = command.split(' ')
        executable_name = Path(executable_path).stem
        pid_path = Path(client_config.RUN_DIR) / f"{executable_name}.pid"
        self.main_process.run_command_on_event(f"touch {pid_path}")

        if env_vars:
            self._setup_environment_variables(env_vars)

        self.master_process.attach_process_classic(
            f"{pid_path} {command}",
            background=True
            # pidfile=pid_path,
            # daemonize=True
        )

        self.monitoring.set_stats_params(
            address=str(Path(client_config.RUN_DIR) / f"{service_id}-stats.sock"),
        )
        self.setup_loggers()

    def setup_loggers(self):
        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.client_config.LOG_DIR) / f"{self.service_id}.log"))
        )

    def _setup_environment_variables(self, env_vars):
        for key, value in env_vars.items():
            self.env(key, value)



class CronJobSection(Section):

    def _setup_environment_variables(self, env_vars):
        for key, value in env_vars.items():
            self.env(key, value)

    def __init__(self, client_config, command, env_vars=None, **kwargs):
        super().__init__(
            name="uwsgi",
            runtime_dir=client_config.RUN_DIR,
            owner=f"{client_config.RUN_AS_UID}:{client_config.RUN_AS_GID}"
        )
        if env_vars is not None:
            self._setup_environment_variables(env_vars)

        # -15 -1 -1 -1 -1 - every 15 minute (minus X means */X, minus 1 means *)
        self.master_process.add_cron_task(
            command,
            **kwargs
        )
