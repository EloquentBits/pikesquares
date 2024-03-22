#import re
from pathlib import Path

import questionary
from giturlparse import validate as giturlparse_validate



class NameValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )


#def get_repo_name_from_url(repo_url):
#    str_pattern = ["([^/]+)\\.git$"]
#    for i in range(len(str_pattern)):
#        pattern = re.compile(str_pattern[i])
#        matcher = pattern.search(repo_url)
#        if matcher:
#            return matcher.group(1)


class RepoAddressValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a repo url",
                cursor_position=len(document.text),
            )

        if not giturlparse_validate(document.text):
            raise questionary.ValidationError(
                message="Please enter a valid repo url",
                cursor_position=len(document.text),
            )


class PathValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )
        if not Path(document.text).exists():
            raise questionary.ValidationError(
                message="Please enter an existing directory to clone your git repository into",
                cursor_position=len(document.text),
            )

