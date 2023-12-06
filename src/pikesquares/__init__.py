
try:
    import urllib2
except ImportError:
    pass

import socket
import json
import errno
import os
import sys
import shutil
from pathlib import Path
from urllib.parse import urlparse
from typing import Protocol, Optional
from abc import abstractmethod
import socket
import subprocess

from pikesquares.presets.services.postgres import PostgresqlConfiguration

from pikesquares.data import VirtualHost

import zmq
from uwsgiconf import uwsgi

from .conf import ClientConfig
from .presets import (
    MainEmperorSection, 
    SubEmperorSection,
    WsgiAppSection,
    ManagedServiceSection,
    CronJobSection,
)

from typing import TypeVar, Union

PathLike = TypeVar("PathLike", str, Path, None)


def get_first_available_port(port=5500):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            return get_first_available_port(port=port + 1)
        else:
            return port

def inet_addr(arg):
    sfamily = socket.AF_INET
    host, port = arg.rsplit(':', 1)
    addr = (host, int(port))
    return sfamily, addr, host

def unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = arg
    return sfamily, addr, socket.gethostname()

def abstract_unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = '\0' + arg[1:]
    return sfamily, addr, socket.gethostname()

def read_stats(stats_addr):
    js = ''
    http_stats = False
    #stats_addr = args.address

    if stats_addr.startswith('http://'):
        http_stats = True
        addr = stats_addr
        host = addr.split('//')[1].split(':')[0]
    elif ':' in stats_addr:
        sfamily, addr, host = inet_addr(stats_addr)
    elif stats_addr.startswith('@'):
        sfamily, addr, host = abstract_unix_addr(stats_addr)
    else:
        sfamily, addr, host = unix_addr(stats_addr)

    try:
        s = None
        if http_stats:
            r = urllib2.urlopen(addr)
            js = r.read().decode('utf8', 'ignore')
        else:
            s = socket.socket(sfamily, socket.SOCK_STREAM)
            s.connect(addr)
        while True:
            data = s.recv(4096)
            if len(data) < 1:
                break
            js += data.decode('utf8', 'ignore')
        if s:
            s.close()
    except ConnectionRefusedError as e:
        uwsgi.log('[emperor-stats-client] connection refused')
    except FileNotFoundError as e:
        uwsgi.log(f"[emperor-stats-client] socket @ {addr} not available")
    except IOError as e:
        if e.errno != errno.EINTR:
            uwsgi.log(f"[emperor-stats-client] socket @ {addr} not available")
    except:
        uwsgi.log("[emperor-stats-client] unable to get uWSGI statistics")
    else:
        try:
            return json.loads(js)
        except json.JSONDecodeError:
            pass

def get_service_status(service_id, client_config):
    if service_id.startswith("project_"):
        service_id += "-emperor"
    stats_socket = (Path(client_config.RUN_DIR) / f"{service_id}-stats.sock")
    socket_started = None
    if stats_socket.exists() and stats_socket.is_socket():
        socket_path = str(stats_socket.resolve())
        socket_started = read_stats(socket_path)
    return 'running' if socket_started else 'stopped'



class Handler(Protocol):

    service_id:str = ""
    client_config: ClientConfig
    service_config:PathLike = None
    cache:str = "vconf-settings"
    config_name: str = ""
    hc_ping_url:str = ""
    parent_service_id:str = ""
    address: str = None

    def __init__(self,
            service_id:str, 
            client_config: Union[ClientConfig, None]=None, 
            service_config:PathLike = None,
            hc_ping_url:str = "",
            parent_service_id:str = "",
        ):
        self.client_config = client_config
        self.service_id = service_id
        self.service_config = service_config
        self.hc_ping_url = hc_ping_url
        self.parent_service_id = parent_service_id
        self.config_name = f"{self.service_id}.json"

    #def ping(self, fail=False):
    #    hc_ping(self.hc_ping_url, ping_fail=fail)

    def setup_address(self):
        if not self.address:
            self.address = f"127.0.0.1:{get_first_available_port()}"
    
    def is_started(self):
        return get_service_status(self.service_id, self.client_config) == "running"

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def prepare_service_config(self, service_config:PathLike=None):
        raise NotImplementedError

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError
    
    @property
    def default_options(self):
        return {}

    @property
    def handler_name(self):
        return self.__class__.__name__
    
    def __repr__(self):
        return self.handler_name
    
    def __str__(self):
        return self.handler_name

    def log(self, message):
        uwsgi.log(f"[vconf-services] : {self.handler_name}] {message}")


class HandlerFactory:
    handlers = {}

    @classmethod
    def service_handlers(cls):
        return {
            k
            for k in cls.handlers
            if k not in ("Main-Emperor", "Sub-Emperor")
        }

    @classmethod
    def make_handler(cls, version):
        try:
            retval = cls.handlers[version]
        except KeyError as err:
            raise NotImplementedError(f"{version=} doesn't exist") from err
        return retval

    @classmethod
    def register(cls, type_name):
        def deco(deco_cls):
            cls.handlers[type_name] = deco_cls
            return deco_cls
        return deco

#@HandlerFactory.register('WSGI-App')
#class WSGIAppHandler(Handler):

#@HandlerFactory.register('Managed-Service')
#class WSGIAppHandler(Handler):


@HandlerFactory.register('Main-Emperor')
class DeviceService(Handler):

        #for k in config.keys():
        #    if k.endswith("_DIR"):
        #        dir = Path(config[k])
        #        if dir and not dir.exists():
        #            dir.mkdir(parents=True, exist_ok=True)

        #emperor_wrapper = Path(config.get("VENV_DIR", "")) / "bin/uwsgi"
        #if not emperor_wrapper.exists():
            #parser.exit(1, message=f"unable to locate VConf binary wrapper @ {emperor_wrapper}.")
        #    return

    def prepare_service_config(self, service_config:PathLike=None):
        self.service_config = service_config
        if service_config:
            if isinstance(service_config, str):
                self.service_config = Path(service_config)
        else:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.service_id}.json"
            # TODO  self.service_config.tofile()
            empjs = json.loads(
                MainEmperorSection(
                    self.client_config,
                    self.service_id,
                ).as_configuration().format(formatter="json")
            )
            empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}"
            # empjs["uwsgi"]["emperor"] = f"{self.client_config.CONFIG_DIR}/project_clo7af2mb0000nldcne2ssmrv/apps"
            empjs["uwsgi"]["show-config"] = True
            empjs["uwsgi"]["strict"] = False
            #empjs["uwsgi"]["plugin"] = "emperor_zeromq"
            empjs["uwsgi"]["emperor-wrapper"] = str((Path(self.client_config.VENV_DIR) / "bin/uwsgi").resolve())
            self.service_config.write_text(json.dumps(empjs))

    def connect(self):
        pass

    def start(self):
        # we import `vconf` with `dlopen` flags set to `os.RTLD_GLOBAL` such that
        # uwsgi plugins can discover uwsgi's globals (notably `extern ... uwsgi`)
        if hasattr(sys, 'setdlopenflags'):
            orig = sys.getdlopenflags()
            try:
                sys.setdlopenflags(orig | os.RTLD_GLOBAL)
                import vconf
            finally:
                sys.setdlopenflags(orig)
        else:  # ah well, can't control how dlopen works here
            import vconf

        vconf.run([
            "--json",
            f"{str(self.service_config.resolve())}"
        ])

    def stop(self):
        pass


@HandlerFactory.register('Sub-Emperor')
class ProjectService(Handler):

    zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)
    config_json = {}

    def prepare_service_config(self, service_config:PathLike=None):
        self.service_config = service_config
        if isinstance(self.service_config, str):
            self.service_config = Path(self.service_config)

        if not self.service_config:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.service_id}.json"

        if not self.service_config.exists():
            empjs = json.loads(SubEmperorSection(
                    client_config=self.client_config,
                    service_id=self.service_id,
                ).as_configuration().format(formatter="json"))
            self.service_config.write_text(json.dumps(empjs))

        self.config_json = json.loads(self.service_config.read_text())
        # print(f"{self.config_json=}")

        stats_addr_key = f"{self.service_id}-stats-addr"

        #zmq_addr_key = f"{self.service_id}-zmq-addr"
        #zmq_port = get_first_available_port()
        #zmq_addr = f"zmq://tcp://127.0.0.1:{zmq_port}"
        #uwsgi.cache_update(zmq_addr_key, zmq_addr, 0, self.cache)
        
        stats_addr = self.config_json["uwsgi"]["emperor-stats-server"]

        #self.config_json["uwsgi"]["emperor"] = zmq_addr #uwsgi.cache_get(zmq_addr_key, self.cache).decode()

        apps_dir = Path(self.client_config.CONFIG_DIR) / f"{self.service_id}" / "apps"
        if apps_dir and not apps_dir.exists():
            apps_dir.mkdir(parents=True, exist_ok=True)
        self.config_json["uwsgi"]["emperor"] = str(apps_dir.resolve())

        uwsgi.cache_update(stats_addr_key, str(stats_addr), 0, self.cache)
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False
        # self.config_json["uwsgi"]["plugin"] = "logfile"


        #if "logfile" in config_json["uwsgi"].get("plugin", ""):
        #    config_json["uwsgi"].pop("plugin")

        self.service_config.write_text(json.dumps(self.config_json))
    
    def connect(self):
        #emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        #zmq_port = emperor_zmq_opt.split(":")[-1]
        zmq_port = "5250"
        addr = f"tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}"
        # print(f"Sub-Emperor: Connecting to ZMQ @ {addr}")
        self.zmq_socket.connect(addr)

    def start(self):
        if all([
            self.service_config, 
            isinstance(self.service_config, Path), 
            self.service_config.exists()]):
            msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()
            # print(f"Sub-Emperor: TOUCH command {self.config_name} with config:\n{msg}")

            self.zmq_socket.send_multipart(
                [
                    b"touch", 
                    self.config_name.encode(), 
                    msg,
                ]
            )
            #hc_ping(self.hc_ping_url)

    def stop(self):
        # print(f"Send to Sub-Emperor emperor_zeromq: DESTROY command {self.config_name}")
        self.zmq_socket.send_multipart([
            b"destroy",
            self.config_name.encode(),
        ])
        #hc_ping(self.hc_ping_url, ping_fail=True)


@HandlerFactory.register('WSGI-App')
class WsgiAppService(Handler):

        #for k in config.keys():
        #    if k.endswith("_DIR"):
        #        dir = Path(config[k])
        #        if dir and not dir.exists():
        #            dir.mkdir(parents=True, exist_ok=True)

        #emperor_wrapper = Path(config.get("VENV_DIR", "")) / "bin/uwsgi"
        #if not emperor_wrapper.exists():
            #parser.exit(1, message=f"unable to locate VConf binary wrapper @ {emperor_wrapper}.")
        #    return
    name: str = ""
    project_id: str = ""
    project_name: str = ""
    wsgi_file: str = ""
    wsgi_module: str = ""
    root_dir: str = ""
    pyvenv_dir: str = "" 
    virtual_hosts: list[VirtualHost] = []

    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    config_json = None

    @property
    def default_options(self):
        """
        Mapping of option key and its defaults
        """
        return {
            "root_dir": "",
            "pyvenv_dir": "{root_dir}/.venv",
            "wsgi_file": "{root_dir}/wsgi.py",
            "wsgi_module": "application",
            "python_version": "3.11"
        }

    def prepare_virtual_hosts(self, include_proj_in_url: bool=False):
        # if not self.virtual_hosts:
        self.setup_address()
        server_names = [
            # f"{self.service_id}-{self.project_id}-vconf.local",
            # f"{self.name}-{self.project_name}-vconf.local",
             f"{self.name}.{self.project_name}.pikesquares.dev" \
                if include_proj_in_url else f"{self.name}.pikesquares.dev",
        ]
        self.virtual_hosts = [
            VirtualHost(
                address=self.address,
                certificate_path=self.client_config.CERT,
                certificate_key=self.client_config.CERT_KEY,
                server_names=[sn for sn in server_names if "--" not in sn]
            )
        ]
            # print(f"Prepared: {self.virtual_hosts=}")

    def prepare_pex_config(self, name, **options):
        # load all values from dotenv
        service_env_file = (Path(self.client_config.CONFIG_DIR) / f"{name}.env")
        if not service_env_file.exists():
            # call it once to create
            import subprocess
            args = [os.environ.get('SCIE'), name]
            # print(f"prog args: {args}")
            subprocess.run(args)
        env_vars = json.loads(service_env_file.read_text())
        if env_vars.get('VENV_DIR'):
            self.root_dir = env_vars.get('VENV_DIR')
            self.pyvenv_dir = env_vars.get('VENV_DIR')
            site_pkgs_dir = Path(self.root_dir) / "lib" / env_vars.get('PYTHON_VERSION') / "site-packages"
            # hc/wsgi.py
            self.wsgi_file = options.get('wsgi_file', "").format(root_dir=site_pkgs_dir)
            # application
            self.wsgi_module = options.get('wsgi_module', "")
            self.virtual_hosts = options.get('virtual_hosts', [])

    def prepare_service_config(
        self,
        service_config: PathLike = None,
        name: str = "",
        project_id: str = "",
        project_name: str = "",
        root_dir: str = "",
        **options
    ):
        self.service_config = service_config
        self.name = name
        self.project_id = project_id
        self.project_name = project_name
        self.root_dir = root_dir

        if service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.project_id}" / "apps" / f"{self.service_id}.json"
        else:
            self.service_config = Path(service_config)
        
        # if options.pop('variant', "") == "Self-Hosted":
        #     self.prepare_pex_config(name=name, **options)
        # else:
        # options.update(self.default_options)
        # print(f"{self.root_dir=}")

        wsgi_app_opts = dict(
            pyvenv_dir=options.get('pyvenv_dir', self.default_options.get('pyvenv_dir')).format(root_dir=self.root_dir),
            wsgi_file=options.get('wsgi_file', self.default_options.get('wsgi_file')).format(root_dir=self.root_dir),
            wsgi_module=options.get('wsgi_module', self.default_options.get('wsgi_module')),
        )

        self.prepare_virtual_hosts()

        section = WsgiAppSection(
            service_id=self.service_id,
            client_config=self.client_config,
            app_name=self.name,
            project_id=self.project_id,
            virtual_hosts=self.virtual_hosts,
            root_dir=self.root_dir,
            **wsgi_app_opts
        ).as_configuration().format(formatter="json")
        self.config_json = json.loads(section)

        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False
        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        #empjs["uwsgi"]["plugin"] = "emperor_zeromq"
    
    def fetch(self, source: Optional[dict] = None):
        """
        Example:

        source = {
            "url": "ssh://git@eloquentbits.com/EloquentBits/sample-flask-app.git",
            "options": [
                "-b",
                "v0.6.0",
            ],
            "env": {
                "GIT_SSL_NO_VERIFY": "true"
            }
        }
        """
        if not source:
            # Do nothing
            return
        url = source.get('uri')
        scheme = urlparse(url).scheme
        executable, subcommand = "/usr/bin/git", "clone"
        options = []
        if scheme == "rsync":
            executable, subcommand = "/usr/bin/rsync", ""
            options.append('--rsh=ssh')

        # check if root dir is not exists
        # if self.root_dir and not Path(self.root_dir).exists():
        target = self.root_dir
        source_options = source.get("options", [])
        if source_options:
            options.extend(source_options)
        subprocess_cmd_args = [executable, subcommand, url, target, *set(options)]
        # print(f"{subprocess_cmd_args=}")
        subprocess.run(
            subprocess_cmd_args,
            env=source.get('env', {})
        )
        # else:
        #     print(f"{self.root_dir} exists!")

    def connect(self):
        pass
        #emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        #zmq_port = emperor_zmq_opt.split(":")[-1]
        #zmq_port = "5500"
        #self.zmq_socket.connect(f'tcp://127.0.0.1:{zmq_port}')

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                self.service_config,
                self.service_config.removesuffix(".stopped")
            )

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

        # print(f"Written WSGI-App config to: {self.service_config}")
        # print(f"{self.project_id=}")

        """
        if all([
            self.service_config, 
            isinstance(self.service_config, Path), 
            self.service_config.exists()]):
            msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()
            print(f"WSGI-App: TOUCH command {self.config_name} with config:\n{msg}")

            self.zmq_socket.send_multipart(
                [
                    b"touch", 
                    self.config_name.encode(), 
                    msg,
                ]
            )
        else:
            print("no service config.")
        """

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


@HandlerFactory.register('Managed-Service')
class ManagedService(Handler):
    config_json = None
    root_dir = None
    virtual_hosts = tuple()
    protocol = None

    @property
    def default_options(self):
        """
        Mapping of option key and its defaults
        """
        return {
            "root_dir": "",
            "command": "/usr/local/bin/redis-server --port 6380 --replicaof 127.0.0.1 6379",
        }

    def fetch(self, source=None):
        pass
    
    def connect(self):
        pass

    def prepare_virtual_hosts(self, protocol="https"):
        if not self.protocol:
            self.protocol = protocol
        self.setup_address()
        server_names = [
            # f"{self.name}-{self.project_name}-vconf.local",
            f"{self.name}.{self.project_name}.pikesquares.dev",
            # f"{self.service_id}-{self.project_id}-vconf.local"
        ]
        self.virtual_hosts = [
            VirtualHost(
                address=self.address,
                protocol=protocol,
                certificate_path=self.client_config.CERT,
                certificate_key=self.client_config.CERT_KEY,
                server_names=[sn for sn in server_names if "--" not in sn]
            )
        ]

    def prepare_service_config(self, command, service_config: PathLike = None, **options):
        if service_config is None:
            self.root_dir = options.get('root_dir')
            self.project_id = options.get('project_id')
            self.service_id = options.get('service_id')
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.project_id}" / "apps" / f"{self.service_id}.json"

        self.prepare_virtual_hosts()

        section = ManagedServiceSection(
            project_id=self.project_id,
            service_id=self.service_id,
            client_config=self.client_config,
            command=command,
        ).as_configuration().format(formatter="json")
        self.config_json = json.loads(section)
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                self.service_config,
                self.service_config.removesuffix(".stopped")
            )

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

        # print(f"Written Managed-Service config to: {self.service_config}")
        # print(f"{self.project_id=}")

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


@HandlerFactory.register('Cron-Job')
class CronJobService(Handler):
    config_json = None
    root_dir = None
    virtual_hosts = tuple()

    @property
    def default_options(self):
        """
        Mapping of option key and its defaults
        """
        return {
            "root_dir": "",
            "command": "/usr/local/bin/sender.sh",
            "minute": "*",
            "hour": "*",
            "day": "*",
            "month": "*",
            "week": "*"
        }

    def fetch(self, source=None):
        pass
    
    def connect(self):
        pass

    def process_cron_options(self, options):
        for key, opt in options.items():
            if "*" in opt:
                opt = -1
                if '/' in opt:
                    opt *= int(opt.split('/')[1])
            options[key] = opt
        return options

    def prepare_service_config(self, command, service_config: PathLike = None, **options):
        if service_config is None:
            self.root_dir = options.pop('root_dir')
            self.project_id = options.pop('project_id')
            self.service_id = options.pop('service_id')
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.project_id}" / "apps" / f"{self.service_id}.json"

        options = self.process_cron_options(options)
        
        section = CronJobSection(
            client_config=self.client_config,
            command=command,
            **options
        ).as_configuration().format(formatter="json")
        self.config_json = json.loads(section)
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                self.service_config,
                self.service_config.removesuffix(".stopped")
            )

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

        # print(f"Written Cron-Job-Service config to: {self.service_config}")
        # print(f"{self.project_id=}")

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


@HandlerFactory.register('PostgreSQL')
class PostgresqlService(ManagedService):
    config_json = None
    root_dir = None
    virtual_hosts = tuple()

    @property
    def default_options(self):
        """
        Mapping of option key and its defaults
        """
        return {
            "root_dir": "/usr/local/pgsql",
            "data_dir": "{root_dir}/data",
        }

    # def fetch(self, source=None):
    #     pass
    
    # def connect(self):
    #     pass

    def prepare_service_config(self, service_config: PathLike = None, **options):
        if service_config is None:
            self.name = options.get('name')
            self.project_name = options.get('project_name')
            self.root_dir = options.get('root_dir')
            self.data_dir = options.get('data_dir')
            self.project_id = options.get('project_id')
            self.service_id = options.get('service_id')
            self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.project_id}" / "apps" / f"{self.service_id}.json"

        self.prepare_virtual_hosts(protocol="postgresql")
        _, port = self.address.split(':')
        section = PostgresqlConfiguration(
            project_id=self.project_id,
            service_id=self.service_id,
            client_config=self.client_config,
            pgsql_root=self.root_dir,
            pgsql_db=self.data_dir,
            env_vars={'PGPORT': port},
            virtual_hosts=self.virtual_hosts,
        ).format(formatter="json")
        self.config_json = json.loads(section)
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False

    # def start(self):
    #     if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
    #         shutil.move(
    #             self.service_config,
    #             self.service_config.removesuffix(".stopped")
    #         )

    #     Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
    #     self.service_config.write_text(json.dumps(self.config_json))

    #     print(f"Written Managed-Service config to: {self.service_config}")
    #     print(f"{self.project_id=}")

    # def stop(self):
    #     if self.service_config is None:
    #         self.service_config = Path(self.client_config.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"
    #     if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
    #         shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))

