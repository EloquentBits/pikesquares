import uwsgi

"""
loaders
    uwsgi_dyn_loader

    uwsgi_uwsgi_loader
        {"module", required_argument,'w', "load a WSGI module", uwsgi_opt_set_str, &up.wsgi_config, 0},
        {"wsgi", required_argument, 'w', "load a WSGI module", uwsgi_opt_set_str, &up.wsgi_config, 0},

    uwsgi_file_loader
        {"wsgi-file", required_argument, 0, "load .wsgi file", uwsgi_opt_set_str, &up.file_config, 0},
        {"file", required_argument, 0, "load .wsgi file", uwsgi_opt_set_str, &up.file_config, 0},

    uwsgi_pecan_loader
    uwsgi_paste_loader
    uwsgi_eval_loader
    uwsgi_mount_loader
    uwsgi_callable_loader
    uwsgi_string_callable_loader

	{"callable", required_argument, 0, "set default WSGI callable name", uwsgi_opt_set_str, &up.callable, 0},

section


    virtualenv = /home/pk/dev/vconf-test-wsgiapp/venv

    callable = simple_wsgi_app.simple_app:application

    // flask
    wsgi-file myflaskapp.py 
    callable app

    // django

    module = django.core.handlers.wsgi:WSGIHandler()

    wsgi-file = myproject/wsgi.py
    wsgi-file = foobar.py
    wsgi-file = /path/to/wsgi.py



"""
import ast, os, pwd
from pathlib import Path

class WsgiAppValidationError(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


def is_file_readable(file_path):
    return os.access(file_path, os.R_OK)


def get_current_user():
    return pwd.getpwuid(os.getuid()).pw_name


def validate_wsgi_file(config):
    wsgi_file_path = Path(config.get('wsgi-file'))
    if not wsgi_file_path.exists() or not wsgi_file_path.is_file():
        raise WsgiAppValidationError(f"Wsgi file '{wsgi_file_path}' is not exists")
    if not is_file_readable(wsgi_file_path):
        user = get_current_user()        
        raise WsgiAppValidationError(f"User '{user}' do not have access to read wsgi file '{wsgi_file_path}'")
    return wsgi_file_path


def check_callable_exists(wsgi_file, callable_):
    wsgi_file = Path(wsgi_file)
    if Path(wsgi_file).suffix != ".py":
        raise NotImplementedError("Only python files support this check yet")
    tree = ast.parse(wsgi_file.read_text())
    assignments = [t for t in tree.body if isinstance(t, ast.Assign)]
    variables_names = [v.id for a in assignments for v in a.targets]
    if callable_ not in variables_names:
        raise WsgiAppValidationError(f"Wsgi module '{callable_}' not found in wsgi file '{wsgi_file}'")
    return callable_


def validate_wsgi_module(config):
    wsgi_file = config.get('wsgi-file')
    callable_ = config.get('callable')
    check_callable_exists(wsgi_file, callable_)
    return config.get('callable')


def validate_venv_dir(config):
    venv_dir = config.get('virtualenv')
    if not Path(venv_dir).exists():
        raise WsgiAppValidationError(f"Virtual env dir '{venv_dir}' is not exists'")
    venv_python_interpreter = Path(venv_dir) / "bin" / "python"
    if not venv_python_interpreter.exists() or not venv_python_interpreter.is_file():
        raise WsgiAppValidationError(f"Virtual env {venv_dir} installed incorrectly")
    return venv_dir

def validate_plugins_dir(config):
    plugins = config.get('plugin').split(',')
    plugins_dir = Path(config.get('plugins-dir'))
    if not any(plugins_dir.iterdir()):
        raise WsgiAppValidationError(f"Plugin dir '{plugins_dir}' is empty")
    plugin_files = [f.stem for f in plugins_dir.iterdir()]
    for plugin in plugins:
        if f"{plugin}_plugin" not in plugin_files:
            raise WsgiAppValidationError(f"Plugin '{plugin}' does not exists in plugin dir '{plugins_dir}'")
    return plugins_dir

def validate(config, fake=False):
    uwsgi.log("[wsgi-apps-validate] validating wsgi app")
    if fake:
        return True
    app_config = config["uwsgi"]

    validate_venv_dir(app_config)
    validate_wsgi_file(app_config)
    validate_wsgi_module(app_config)
    if 'plugins-dir' in app_config:
        validate_plugins_dir(app_config)

    return True
