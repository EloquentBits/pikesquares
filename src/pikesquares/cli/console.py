from pathlib import Path
from rich.console import Console as BaseConsole

from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table

import questionary
# import os


def pluralize(count: int, words: list[str], show_count: bool = True):
    cases = (2, 0, 1, 1, 1, 2)
    plural_word = words[2 if 5 <= (count % 100) < 20 else cases[min(count % 10, 5)]]
    if show_count:
        return f"{count} {plural_word}"
    return plural_word


class _RenderMixin:

    def _label(self, *args, **kwargs):
        return Text(*args, **kwargs).markup

    @property
    def styles(self): 
        return {
            'header': {
                'online': {'text': ":play_button: online", 'style': "bold green"},
                'offline': {'text': ":stop_button: offline", 'style': "red"},
            },
            'subtitle': {
                'online': {'text': "online", 'style': "bold green"},
                'offline': {'text': "offline", 'style': "bold red"}
            },
            'item': {
                'online': {'text': ":play_button: {name}", 'style': "green"},
                'offline': {'text': ":stop_button: {name}", 'style': "red"},
            }
        }

    @property
    def custom_style_fancy(self):
        return questionary.Style(
        [
            ("separator", "fg:#cc5454"),
            ("qmark", "fg:#673ab7 bold"),
            ("question", ""),
            ("selected", "fg:#cc5454"),
            ("pointer", "fg:#673ab7 bold"),
            ("highlighted", "fg:#673ab7 bold"),
            ("answer", "fg:#f44336 bold"),
            ("text", "fg:#FBE9E7"),
            ("disabled", "fg:#858585 italic"),
        ]
    )

    @property
    def custom_style_dope(self):
        return questionary.Style(
        [
            ("separator", "fg:#6C6C6C"),
            ("qmark", "fg:#FF9D00 bold"),
            ("question", ""),
            ("selected", "fg:#5F819D"),
            ("pointer", "fg:#FF9D00 bold"),
            ("answer", "fg:#5F819D bold"),
        ]
    )

    @property
    def custom_style_genius(self):
        return questionary.Style(
        [
            ("qmark", "fg:#E91E63 bold"),
            ("question", ""),
            ("selected", "fg:#673AB7 bold"),
            ("answer", "fg:#2196f3 bold"),
        ]
    )

    def _item(self, entity):
        status = entity.get('status', 'offline')
        label_params = self.styles['item'].get(status)
        label_text = label_params.pop('text').format(name=entity.get('name'))
        return self._label(label_text, style=label_params.pop('style'))
    
    def _panel(self, entity, items_caption, show_id=True):
        title = "{name} (id: {id})".format(**entity)
        if not show_id:
            title = "{name}".format(**entity)

        status = entity.get('status', 'offline')
        header = list()
        header.append(self._label(**self.styles.get('header').get(status)))
        subtitle = self._label(**self.styles.get('subtitle').get(status))

        items = [
            self._item(item)
            for item in entity.get(items_caption.lower(), [])
        ]
        header.append("--- {title} ---".format(title=items_caption.capitalize()))
        if len(items) < 1:
            header.append("[i]No {title}[/i]".format(title=items_caption.capitalize()))
        content = "\n".join([*header, *items])
        return Panel(
            content,
            title=title,
            # subtitle=subtitle,
            expand=True,
            # style=style
        )

    def _get_projects_panels(self, projects, show_id=True):
        for project in projects:
            yield self._panel(project, items_caption="apps", show_id=show_id)

    def _get_envs_panels(self, envs, show_id=True):
        for env in envs:
            yield self._panel(env, items_caption="projects", show_id=show_id)


class Console(BaseConsole, _RenderMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    #def pager(self, content, *, status_bar_format=None, color=True):
    #    from click import echo_via_pager
    #    os.environ['LESS'] = " ".join([
    #        "-P{} (?pB%pB\%):lines %lt-%lb)$".format(
    #            status_bar_format
    #            .replace(':', '\:')
    #            .replace('.', '\.')
    #        ),
    #        # "-m",
    #        # "+G",
    #    ])
    #    os.environ['LESSSECURE'] = '1'
    #    return echo_via_pager(content, color=color)

    def error(self, *args, **kwargs):
        example = kwargs.pop('example', None)
        example_description = kwargs.pop('example_description', None)
        hint = kwargs.pop('hint', None)
        self.print(*args, **kwargs, style='red')
        if example:
            if example_description:
                example = ' - '.join([f"[i]{example}[/i]", f"[default]{example_description}"])
            self.info(f"It should be:\n\t{example}")
        if hint:
            self.warning(f"[i]Hint: {hint}[/i]")

    def info(self, *args, **kwargs):
        self.print(*args, **kwargs, style='blue')

    def success(self, *args, **kwargs):
        self.print(*args, **kwargs, style='green')

    def warning(self, *args, **kwargs):
        self.print(*args, **kwargs, style='yellow')

    def ask(self, *args, **kwargs):
        repeat = kwargs.pop('repeat', False)
        validators = kwargs.pop('validators', [])
        result = None
        while True:
            result = Prompt.ask(*args, **kwargs)
            for validator_cls in validators:
                try:
                    if not callable(validator_cls):
                        continue
                    validator = validator_cls()
                    result = validator(result)
                except ValueError as e:
                    self.error(f"{e}")
                    result, repeat = None, True
            if result or not repeat:
                break
        return result

    def ask_for_options(self, options, label=None, *args, **kwargs):
        options_filled = {}
        options.update(kwargs.pop('defaults', {}))
        for k, v in options.items():
            validators = []
            is_path_key = any(k.endswith(o) for o in ("_dir", "_file", "_path"))
            if is_path_key and v.startswith("/"):
                from .validators import ServicePathValidator
                validators += [ServicePathValidator]
            options_filled[k] = self.ask(label(k), *args, default=v.format(**options_filled), validators=validators, **kwargs)
            if is_path_key and options_filled.get('root_dir') and not options_filled[k].startswith("/"):
                # root_dir is filled and path DO NOT start with /
                options_filled[k] = "{root_dir}/{path}".format(
                    root_dir=options_filled.get('root_dir'),
                    path=options_filled[k]
                )
        return options_filled

    def confirm(self, *args, **kwargs):
        return Confirm.ask(*args, **kwargs)
    
    def choose(self, *args, **kwargs):
        # unsafe - do not catch KeyboardInterrupt inside, exit on it
        return questionary.select(*args, **kwargs).unsafe_ask()
    
    def choose_many(self, *args, **kwargs):
        return questionary.checkbox(*args, **kwargs).unsafe_ask()

    def choose_path(self, *args, **kwargs):
        return questionary.path(*args, **kwargs).unsafe_ask()

    def format_print(*args, **kwargs):
        title = kwargs.pop('title', "")
        fmt = kwargs.pop('format', "")
        _, value = args
        if fmt == "json":
            console.print(value)
        elif fmt == "table":
            console.print_response(results=[value], title=title)
        else:
            if title:
                console.info(title)
                console.simple_print(value)
    
    def simple_print(self, value):
        value_colors = {
            'online': "green",
            'offline': "red",
        }
        if isinstance(value, dict):
            for k, v in value.items():
                color = value_colors.get(v, 'default')
                key = (
                    k
                    .replace('service', '')
                    .replace('_', ' ')
                    .strip()
                    .capitalize()
                )
                console.print(f"{key}: [{color}]{v}")

    def render_link(self, address, port=None, desc=None, user=None, protocol="https"):
        if user:
            address = f"{user}@{address}"
        link = f"{protocol}://{address}"
        if port and port not in address:
            link += f":{port}"
        if not desc:
            desc = link
        return f"[link={link}]{desc}[/link]"


    def print_response(self, results, title: str = "", show_id: bool = False, exclude=None) -> None:
        def render_cell(key, value):
            if key == "virtual_hosts":
                lines = []
                for i in value:
                    lines.append(
                        self.render_link(address=i.get('address'), protocol=i.get('protocol'))
                    )
                    lines.extend([
                        self.render_link(
                            address=sn,
                            protocol=i.get('protocol'),
                            port=i.get('address').split(':')[1]
                        )
                        for sn in i.get('server_names')
                    ])
                return "\n".join(lines)
            elif str(value).startswith("/"):
                return str(Path(value).resolve())
            elif "/" in str(value) and not value.startswith("http"):
                return f"~/{Path(value).relative_to(Path.home())}"
            return str(value)
        
        if exclude is None:
            exclude = []
        
        if not show_id:
            exclude.append('cuid')

        table = Table(title=title)

        for r in results:
            for k in r:
                if k in exclude:
                    continue
                header = k.replace('service', '').replace('_', ' ').strip().title()
                if header not in [c.header for c in table.columns]:
                    table.add_column(header)

        for row in results:
            values = [
                render_cell(key, item)
                for key, item in row.items()
                if key not in exclude
            ]
            table.add_row(*values)

        # table.add_column("Released", justify="right", style="cyan", no_wrap=True)
        # table.add_column("Title", style="magenta")
        # table.add_column("Box Office", justify="right", style="green")

        # table.add_row("Dec 20, 2019", "Star Wars: The Rise of Skywalker", "$952,110,690")
        # table.add_row("May 25, 2018", "Solo: A Star Wars Story", "$393,151,347")
        # table.add_row("Dec 15, 2017", "Star Wars Ep. V111: The Last Jedi", "$1,332,539,889")
        # table.add_row("Dec 16, 2016", "Rogue One: A Star Wars Story", "$1,332,439,889")

        # console = Console()
        self.print(table)

    
    def show_environments(self, environments, show_count=True, show_id=True):
        if len(environments) > 0:
            if show_count:
                self.rule(
                    "My environments ({count})".format(
                        count=pluralize(len(environments), ["environment", "environments", "environments"]),
                    ),
                    characters="-"
                )
            envs_names = [e.get('name') for e in environments]
            if len(set(envs_names)) < len(envs_names):
                # always show ids when envs with same name occured
                show_id = True
            self.print(
                Columns(self._get_envs_panels(environments, show_id=show_id)),
            )
        else:
            self.print(
                Text(f"No environments were created, add one with 'vcli bootstrap'", justify="center", style="yellow"),
            )
        self.print()
    
    def show_projects(self, env_name, env_id, projects, show_count=True, show_id=False):
        if show_count:
            environment_rule = "Environment '{env_name}': {count}"
            if show_id:
                environment_rule = "Environment '{env_name}' (id: {id}): {count}"
            self.rule(
                environment_rule.format(
                    env_name=env_name,
                    id=env_id,
                    count=pluralize(len(projects), ["project", "projects", "projects"]),
                ),
                characters="-"
            )
        if len(projects) > 0:
            projs_names = [e.get('name') for e in projects]
            if len(set(projs_names)) < len(projs_names):
                # always show ids when projects with same name occured
                show_id = True
            self.print(
                Columns(self._get_projects_panels(projects, show_id=show_id)),
            )
        else:
            self.print(
                Text(f"No projects in environment '{env_name}', add one", justify="center", style="yellow"),
            )
        self.print()


console = Console()
stderr_console = Console(stderr=True)
