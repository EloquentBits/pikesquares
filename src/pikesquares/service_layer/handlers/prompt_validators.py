from pathlib import Path

import giturlparse
import questionary
import structlog

logger = structlog.getLogger()


class NameValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )


class RepoAddressValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a repo url",
                cursor_position=len(document.text),
            )

        if not giturlparse.validate(document.text):
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
