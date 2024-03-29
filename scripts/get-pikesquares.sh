#!/usr/bin/env bash

set -euo pipefail

COLOR_RED="\x1b[31m"
COLOR_GREEN="\x1b[32m"
COLOR_YELLOW="\x1b[33m"
COLOR_RESET="\x1b[0m"
NO_COLOR="$(tput sgr0 2>/dev/null || printf '')"

function log() {
  echo -e "$@" 1>&2
}

function die() {
  (($# > 0)) && log "${COLOR_RED}$*${COLOR_RESET}"
  exit 1
}

function green() {
  (($# > 0)) && log "${COLOR_GREEN}$*${COLOR_RESET}"
}

function warn() {
  (($# > 0)) && log "${COLOR_YELLOW}$*${COLOR_RESET}"
}

function check_cmd() {
  local cmd="$1"
  command -v "$cmd" > /dev/null || die "This script requires the ${cmd} binary to be on the PATH."
}

help_url="https://pikesquares.com/docs/getting-help"

_GC=()

function gc() {
  if (($# > 0)); then
    check_cmd rm
    _GC+=("$@")
  else
    rm -rf "${_GC[@]}"
  fi
}

trap gc EXIT

check_cmd uname

function calculate_os() {
  local os

  os="$(uname -s)"
  if [[ "${os}" =~ [Ll]inux ]]; then
    echo linux
  elif [[ "${os}" =~ [Dd]arwin ]]; then
    echo macos
  else
    die "PikeSquares is not supported on this operating system (${os}). Please reach out to us at ${help_url} for help."
  fi
}

OS="$(calculate_os)"

check_cmd basename
check_cmd curl

function fetch() {
  local url="$1"
  local dest_dir="$2"

  local dest
  dest="${dest_dir}/$(basename "${url}")"

  curl --proto '=https' --tlsv1.2 -sSfL -o "${dest}" "${url}"
}

if [[ "${OS}" == "macos" ]]; then
  check_cmd shasum
else
  check_cmd sha256sum
fi

function sha256() {
  if [[ "${OS}" == "macos" ]]; then
    shasum --algorithm 256 "$@"
  else
    sha256sum "$@"
  fi
}

check_cmd mktemp

function install_from_url() {
  local url="$1"
  local dest="$2"

  local workdir
  workdir="$(mktemp -d)"
  gc "${workdir}"

  fetch "${url}.sha256" "${workdir}"
  fetch "${url}" "${workdir}"
  (
    cd "${workdir}"
    sha256 -c --status ./*.sha256 ||
      die "Download from ${url} did not match the fingerprint at ${url}.sha256"
  )
  rm "${workdir}/"*.sha256
  if [[ "${OS}" == "macos" ]]; then
    mkdir -p "$(dirname "${dest}")"
    install -m 755 "${workdir}/"* "${dest}"
  else
    install -D -m 755 "${workdir}/"* "${dest}"
  fi
}

function calculate_arch() {
  local arch

  arch="$(uname -m)"
  if [[ "${arch}" =~ x86[_-]64 ]]; then
    echo x86_64
  elif [[ "${arch}" =~ arm64|aarch64 ]]; then
    echo aarch64
  else
    die "PikeSquares is not supported for this chip architecture (${arch}). Please reach out to us at ${help_url} for help."
  fi
}

printf '\n'

function img_ascii(){
printf "$COLOR_GREEN"
  cat <<'EOF'
                            ++                                      
                          +++++                                     
                         +++++++                                    
                         +++++++                                    
                         +++++++                                    
                         +++++++                                    
                       +++++++++++++                                
                    ++++++++++++++++++                              
                    +++++++++++++++++++                             
                    +++++++++++++++++++                             
                    ++++++++++++++++++++++                          
                    ++++++++++++++++++++++                          
                    ++++++++++++++++++++++                          
                   +++++++++++++++++++++++         PikeSquares is now installed        
                   +++++++++++++++++++++++                          
                   +++++++++++++++++++++++              
                   +++++++++++++++  ++++++             Run `pikesquares up` to launch              
                   +++++++++++++++++++++++                       
                  ++++++++++++++++++++++++                      or    
                  ++++++++++++++++++++++++                  
                  +++++++++++++++++++ ++++                 `pikesquares --help` for commands
                 +++++++++++++++++++++ ++                           
                 +++++++++++++++++++++  +                           
                +++ ++++++++++++++++++                              
              +++   +++++++++++++++++++                             
             ++     +++++++++++++++++ +                             
           +++      +++++++++++++++++ +                             
          ++        ++++++++++++++++++ +                            
        +++         ++++++++++++++++++ +                            
       ++           +++++++++++++++++++++                           
     ++             +++++++++++++++++++++                           
    ++                  ++++++    +++++++                           
  ++                     ++++      +++++ +                          
 +                       ++++       ++++++                          
                         ++++        ++++                           
                        +++++        ++++                           
                      +++++++        ++++                           
                   ++++++++++        +++++                          
EOF
printf "$NO_COLOR"
}

check_cmd cat

function usage() {
  cat << EOF
Usage: $0

Installs the pikesquares launcher binary.

You only need to run this once on a machine when you do not have "pikesquares"
available to run yet.

The pikesquares binary takes care of managing and running the underlying
PikeSquares version.

Once installed, if you want to update your "pikesquares" launcher binary, use
"SCIE_BOOT=update pikesquares" to get the latest release or
"SCIE_BOOT=update pikesquares --help" to learn more options.

-h | --help: Print this help message.

-d | --bin-dir:
  The directory to install the scie-pikesquares binary in, "~/.local/bin" by default.

-b | --base-name:
  The name to use for the scie-pikesquares binary, "pikesquares" by default.

-V | --version:
  The version of the scie-pikesquares binary to install, the latest version by default.
  The available versions can be seen at:
    https://github.com/EloquentBits/scie-pikesquares/releases

EOF
}

bin_dir="${HOME}/.local/bin"
base_name="pikesquares"
version="latest/download"
while (($# > 0)); do
  case "$1" in
    --help | -h)
      usage
      exit 0
      ;;
    --bin-dir | -d)
      bin_dir="$2"
      shift
      ;;
    --base-name | -b)
      base_name="$2"
      shift
      ;;
    --version | -V)
      version="download/v$2"
      shift
      ;;
    *)
      usage
      die "Unexpected argument $1\n"
      ;;
  esac
  shift
done

ARCH="$(calculate_arch)"
URL="https://github.com/EloquentBits/scie-pikesquares/releases/${version}/scie-pikesquares-${OS}-${ARCH}"
dest="${bin_dir}/${base_name}"

log "Downloading and installing the pikesquares launcher ..."
install_from_url "${URL}" "${dest}"
green "Installed the pikesquares launcher from ${URL} to ${dest}"
if ! command -v "${base_name}" > /dev/null; then
  warn "${dest} is not on the PATH."
  log "You'll either need to invoke ${dest} explicitly or else add ${bin_dir} to your shell's PATH."
fi

img_ascii

#green "\nRunning \`pants\` in a Pants-enabled repo will use the version of Pants configured for that repo."
#green "In a repo not yet Pants-enabled, it will prompt you to set up Pants for that repo."
