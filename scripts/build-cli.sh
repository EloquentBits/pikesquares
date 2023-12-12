#!/bin/bash
python -m pip install -U build pex

curl -Lo "science" https://github.com/a-scie/lift/releases/download/latest/science-$(uname -o)-$(uname -m)
chmod +x science

python -m build . --wheel

PEX_TOOLS=1 \
pex -vvv \
    dist/pikesquares-* \
    -r requirements.txt \
    --venv \
    --include-tools \
    --python $(which python) \
    --entry-point pikesquares.cli.cli:app \
    --disable-cache \
    --no-emit-warnings \
    -o pikesquares-cli.pex

science lift \
    --file pikesquares=pikesquares-cli.pex build \
    --use-platform-suffix \
    --hash sha256 \
    pikesquares.toml

rm science
