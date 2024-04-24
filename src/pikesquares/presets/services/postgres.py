from .. import ManagedServiceSection, Section, Configuration


class PostgresPreStartSection(Section):
    
    def __init__(self, pgsql_root, pgsql_db):
        super().__init__(name="check_db_initialized")
        
        self._set("if-not-dir", f"{pgsql_db}")
        self.main_process.run_command_on_event(f"{pgsql_root}/bin/initdb -A md5 -U %U -W -D %(_) -E UTF-8")
        self._set("end-if", "")



class PostgresMainSection(ManagedServiceSection):
    """
    Postgres consists of two sections

    Example configuration:

    {
        "uwsgi": {
            "uid": "postgres",
            "gid": "postgres",
            "show-config": true,
            "strict": false,
            "json": "%s:check_db_initialized",
            "env": [
                "PGPORT=6677"
            ],
            "exec-asap": "touch /usr/local/pgsql/postmaster.pid",
            "smart-attach-daemon": "/usr/local/pgsql/data/postmaster.pid /usr/local/pgsql/bin/postgres -D /usr/local/pgsql/data"
        },
        "check_db_initialized": {
            "if-not-dir": "/usr/local/pgsql/data",
            "exec-asap": "/usr/local/pgsql/bin/initdb -A md5 -U %U -W -D %(_) -E UTF-8",
            "endif": ""
        }
    }
    """
    command = (
        # "{pgsql_db}/postmaster.pid",
        "{pgsql_root}/bin/postgres",
        "-D",
        "{pgsql_db}",
        "-c",
        "unix_socket_directories={pgsql_socket_dir}"
    )
    supported_env_vars = {
        'PGHOST': "127.0.0.1",
        'PGPORT': "6677"
    }

    def setup_virtual_hosts(self, virtual_hosts):
        for vhost in virtual_hosts:
            if vhost.static_files_mapping:
                for mountpoint, target in vhost.static_files_mapping.items():
                    self.statics.register_static_map(mountpoint, target)
            
            for name in vhost.server_names:
                self.set_domain_name(
                    address=vhost.address,
                    domain_name=name,
                )

    def __init__(
        self,
        client_config,
        project_id,
        service_id,
        env_vars=None,
        pgsql_root="/usr/local/pgsql",
        pgsql_db="/usr/local/pgsql/data",
        virtual_hosts=None
    ):
        if not env_vars:
            env_vars = self.supported_env_vars
        super().__init__(
            client_config,
            project_id,
            service_id,
            pre_start_section=PostgresPreStartSection(pgsql_root, pgsql_db),
            command=" ".join(self.command).format(
                pgsql_root=pgsql_root,
                pgsql_db=pgsql_db,
                pgsql_socket_dir=f"/run/user/1000/vconf"
            ),
            env_vars=env_vars
        )
        self.main_process.set_owner_params(uid="postgres", gid="postgres")
        if virtual_hosts:
            self.setup_virtual_hosts(virtual_hosts)


class PostgresqlConfiguration(Configuration):
    
    def __init__(
            self,
            client_config,
            project_id,
            service_id,
            *args,
            env_vars=None,
            virtual_hosts=None,
            pgsql_root="/usr/local/pgsql",
            pgsql_db="/usr/local/pgsql/data",
            **kwargs
        ):
        super().__init__(
            [
                PostgresMainSection(
                    client_config,
                    project_id,
                    service_id,
                    env_vars,
                    pgsql_root,
                    pgsql_db,
                    virtual_hosts=virtual_hosts
                ),
                PostgresPreStartSection(
                    pgsql_root,
                    pgsql_db
                )
            ],
            *args,
            **kwargs
        )
