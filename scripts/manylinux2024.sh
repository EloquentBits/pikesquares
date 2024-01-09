#!/bin/bash
#
install_deps() {
  if [ "$1" = "general" ]; then
    git config --global --add safe.directory '*'
    yum install -y curl zip unzip tar

  elif [ "$1" = "openssl" ]; then
    yum install -y perl-IPC-Cmd

  elif [ "$1" = "libsqlite3" ]; then
    yum install -y libsqlite3x-devel.x86_64

  elif [ "$1" = "zeromq" ]; then
    yum install -y zeromq-devel 

  elif [ "$1" = "ccache" ]; then
    yum -y install ccache

  elif [ "$1" = "python_alias" ]; then
    ln -fs /usr/local/bin/python3.9 /usr/local/bin/python3

  else
      >&2 echo "unknown input for manylinux2014.sh: '$1'"
      exit $exit_code
  fi
}

for var in "$@"
do
    install_deps "$var"
done


