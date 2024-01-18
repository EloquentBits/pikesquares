#!/bin/bash
#python -m pip install -U build pex

#curl -Lo "science" https://github.com/a-scie/lift/releases/download/latest/science-$(uname -o)-$(uname -m)
#chmod +x science

#python -m build . --wheel

#"wheelhouse/pikesquares_binary-0.3.22-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
PEX_TOOLS=1 \
pex -v \
    -r requirements.txt \
    "dist/pikesquares-0.3.4-py3-none-any.whl" \
    "wheelhouse/pikesquares_binary-0.3.21-py3-none-any.whl" \
    --venv \
    --include-tools \
    --python $(which python) \
    --entry-point pikesquares.cli.cli:app \
    --disable-cache \
    --no-emit-warnings \
    -o pikesquares-bundle.pex

#science lift \
#    --file pikesquares=pikesquares-cli.pex build \
#    --use-platform-suffix \
#    --hash sha256 \
#    pikesquares.toml

#rm science
