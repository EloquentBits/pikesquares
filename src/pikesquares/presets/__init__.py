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
