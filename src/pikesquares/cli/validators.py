from string import punctuation
from pathlib import Path

from pydantic import validate_email


class Validator:
    value: str = ""


class PasswordValidator(Validator):
    min_length: int = 6
    prev_password: str = ""

    @classmethod
    def __call__(cls, value):
        if len(value) < cls.min_length:
            raise ValueError(f"Password length should be greater than {cls.min_length} symbols!")
        if not cls.prev_password:
            cls.prev_password = value
        else:
            if cls.prev_password != value:
                cls.prev_password = None
                value = None
                raise ValueError("Passwords doesn't match!")
        return value


class EmailValidator(Validator):

    @classmethod
    def __call__(cls, value):
        _, email = validate_email(value)
        return email


class ServicePathValidator(Validator):

    @classmethod
    def __call__(cls, path):
        try:
            p = Path(path)
            if not p.exists():
                raise ValueError(f"File or directory on path '{path}' does not exist!")
        except PermissionError:
            raise ValueError(f"Insufficient rights to access the path '{path}'!")
        return path


class ServiceNameValidator(Validator):
    restricted_chars = "".join([
        c
        for c in punctuation
        if c not in " .-_"
    ])
    min_length = 2
    max_length = 32
    
    @classmethod
    def __call__(cls, value):
        restricted = ", ".join({
            f"\'{c}\'"
            for c in value
            if c in cls.restricted_chars
        })
        if any(restricted):
            raise ValueError(
                "\n".join([
                    f"Name contains restricted characters: {restricted}",
                    f"All restricted chars: {cls.restricted_chars}"
                ])
            )
        if not value.strip():
            raise ValueError("Name could not have space chars only!")
        if len(value) < cls.min_length:
            raise ValueError(f"Name should be more than {cls.min_length} chars!")
        if len(value) >= cls.max_length:
            raise ValueError(f"Name should be less than {cls.max_length} chars!")
        return value.strip()
