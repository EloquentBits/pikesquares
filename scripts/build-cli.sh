#!/bin/bash
set -euo pipefail

#python -m pip install -U build pex
#curl -Lo "science" https://github.com/a-scie/lift/releases/download/latest/science-$(uname -o)-$(uname -m)
#chmod +x science

#CIBW_BUILD='cp311-manylinux_x86_64' \
#CIBW_ENVIRONMENT='APPEND_VERSION=".post0" UWSGI_PROFILE=pikesquares' \
#CIBW_BEFORE_BUILD_LINUX="find . -name '*.o' -delete && (yum install -y openssl-devel zlib-devel zeromq-devel libsqlite3x-devel.x86_64 pcre-devel jansson-devel)" \
#CIBW_BEFORE_ALL='./scripts/patch-uwsgi-packaging.sh uwsgi' \
#CIBW_REPAIR_WHEEL_COMMAND='auditwheel repair -w {dest_dir} {wheel}' \
#CIBW_TEST_COMMAND="pyuwsgi --help" \
#CIBW_BEFORE_BUILD_MACOS="find . -name '*.o' -delete && IS_MACOS=1 ./pre_build.sh" \
#cibuildwheel --platform linux --output-dir wheelhouse uwsgi

#CFLAGS = "-Wl,-strip-all"
#CXXFLAGS = "-Wl,-strip-all"
#export CIBW_ENVIRONMENT_PASS_LINUX=''
#CIBW_ENVIRONMENT_LINUX: BUILD_TIME="$(date)" SAMPLE_TEXT="sample text"
#export manylinux-x86_64-image = "manylinux2014"

#python -m build . --wheel

#"wheelhouse/pikesquares_binary-0.3.22-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
#PEX_TOOLS=1 \
#--include-tools \
# "wheelhouse/pikesquares_binary-0.3.22-py3-none-any.whl" \
# "wheelhouse/pyuwsgi-2.1.dev0+bb5392fb-py3-none-any.whl" \

#--runtime-pex-root "/home/pk/dev/eqb/pikesquares/runtime-pex-root" \

pex -v \
    -r requirements.txt \
     "/home/pk/dev/pyproj/pyuwsgi-wheels/wheelhouse/pyuwsgi-2.0.23-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
    "dist/pikesquares-0.4.0-py3-none-any.whl" \
    --venv prepend \
    --seed verbose \
    --no-strip-pex-env \
    --compile \
    --python "$(which python)" \
    --entry-point pikesquares.cli.cli:app \
    --no-emit-warnings \
    -o pikesquares-bundle.pex

#pex -v \
#    -r requirements.txt \
#     "/home/pk/dev/pyproj/pyuwsgi-wheels/wheelhouse/pyuwsgi-2.0.23-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl" \
#    "dist/pikesquares-0.4.0-py3-none-any.whl" \
#    --venv prepend \
#    --seed verbose \
#    --no-strip-pex-env \
#    --compile \
#    --python "$(which python)" \
#    --entry-point pikesquares.cli.cli:app \
#    --no-emit-warnings \
#    -o pikesquares-bundle.pex

#~/.local/bin/science lift \
#  --file pikesquares-pex=pikesquares-bundle.pex \
#  --file entrypoint.py=entrypoint.py build \
#  --use-platform-suffix \
#  --hash sha256 \
#  pikesquares.toml


#science lift \
#    --file pikesquares=pikesquares-cli.pex build \
#    --use-platform-suffix \
#    --hash sha256 \
#    pikesquares.toml

#rm science
