#!/bin/bash
set -eu -o pipefail

JANSSON_HASH=6e85f42dabe49a7831dbdd6d30dca8a966956b51a9a50ed534b82afc3fa5b2f4
JANSSON_DOWNLOAD_URL=http://www.digip.org/jansson/releases
JANSSON_ROOT=jansson-2.11

ZMQ_HASH=6e85f42dabe49a7831dbdd6d30dca8a966956b51a9a50ed534b82afc3fa5b2f4
ZMQ_DOWNLOAD_URL=https://github.com/zeromq/libzmq/releases/download/v4.3.4
ZMQ_ROOT=zeromq-4.3.4

PKG_CONFIG_HASH=6e85f42dabe49a7831dbdd6d30dca8a966956b51a9a50ed534b82afc3fa5b2f4
PKG_CONFIG_DOWNLOAD_URL=https://pkgconfig.freedesktop.org/releases/
PKG_CONFIG_ROOT=pkg-config-0.29.2

OPENSSL_HASH=6e85f42dabe49a7831dbdd6d30dca8a966956b51a9a50ed534b82afc3fa5b2f4
OPENSSL_DOWNLOAD_URL=https://github.com/openssl/openssl/releases/download/openssl-3.2.0/
OPENSSL_ROOT=openssl-3.2.0

# From Multibuild
BUILD_PREFIX="${BUILD_PREFIX:-/usr/local}"
MULTIBUILD_DIR=$(dirname "${BASH_SOURCE[0]}")
PCRE_VERSION="${PCRE_VERSION:-8.38}"
function rm_mkdir {
    # Remove directory if present, then make directory
    local path=$1
    if [ -z "$path" ]; then echo "Need not-empty path"; exit 1; fi
    if [ -d "$path" ]; then rm -rf "$path"; fi
    mkdir "$path"
}
function build_simple {
    # Example: build_simple libpng $LIBPNG_VERSION \
    #               https://download.sourceforge.net/libpng tar.gz
    local name="$1"
    local version="$2"
    local url="$3"
    local ext="${4:-tar.gz}"
    echo "building $name@$version from $3"
    if [ -e "${name}-stamp" ]; then
        return
    fi
    local name_version="${name}-${version}"
    local archive="${name_version}.${ext}"
    fetch_unpack "$url/$archive"
    (cd "$name_version" \
        && ./configure --prefix="$BUILD_PREFIX" \
        && make -j4 \
        && make install)
    touch "${name}-stamp"
}
function fetch_unpack {
    # Fetch input archive name from input URL
    # Parameters
    #    url - URL from which to fetch archive
    #    archive_fname (optional) archive name
    #
    # Echos unpacked directory and file names.
    #
    # If `archive_fname` not specified then use basename from `url`
    # If `archive_fname` already present at download location, use that instead.
    local url="$1"
    if [ -z "$url" ];then echo "url not defined"; exit 1; fi
    local archive_fname="${2:-$(basename "$url")}"
    local arch_sdir="${ARCHIVE_SDIR:-archives}"
    # Make the archive directory in case it doesn't exist
    mkdir -p "$arch_sdir"
    local out_archive="${arch_sdir}/${archive_fname}"
    # If the archive is not already in the archives directory, get it.
    if [ ! -f "$out_archive" ]; then
        # Source it from multibuild archives if available.
        local our_archive="${MULTIBUILD_DIR}/archives/${archive_fname}"
        if [ -f "$our_archive" ]; then
            ln -s "$our_archive" "$out_archive"
        else
            # Otherwise download it.
            curl -sL "$url" > "$out_archive"
        fi
    fi
    # Unpack archive, refreshing contents, echoing dir and file
    # names.
    tar xf "$out_archive" && ls -1d ./*
#    rm_mkdir arch_tmp
#    install_rsync
#    (cd arch_tmp && \
#        untar ../$out_archive && \
#        ls -1d * &&
#        rsync --delete -ah * ..)
}
function build_pcre {
    build_simple pcre "$PCRE_VERSION" https://s3.amazonaws.com/ll-share-public/pcre
}

function check_sha256sum {
    local fname=$1
    if [ -z "$fname" ]; then echo "Need path"; exit 1; fi
    local sha256=$2
    if [ -z "$sha256" ]; then echo "Need SHA256 hash"; exit 1; fi
    echo "${sha256}  ${fname}" > "${fname}.sha256"
    if [ -n "${IS_MACOS:-}" ]; then
        shasum -a 256 -c "${fname}.sha256"
    else
        sha256sum -c "${fname}.sha256"
    fi
    rm "${fname}.sha256"
}
# End from Multibuild


function build_jansson {
    if [ -e jansson-stamp ]; then return; fi
    echo "building jansson from $JANSSON_DOWNLOAD_URL"
    fetch_unpack "${JANSSON_DOWNLOAD_URL}/${JANSSON_ROOT}.tar.gz"
    check_sha256sum "${ARCHIVE_SDIR:-archives}/${JANSSON_ROOT}.tar.gz" "${JANSSON_HASH}"
    (cd "${JANSSON_ROOT}" \
        && ./configure --prefix="$BUILD_PREFIX" \
        && make -j4 \
        && make install)
    touch jansson-stamp
}

function build_zmq {
  if [ -e zmq-stamp ]; then return; fi
  echo "building zmq from $ZMQ_DOWNLOAD_URL"
  fetch_unpack "${ZMQ_DOWNLOAD_URL}/${ZMQ_ROOT}.tar.gz"
  (cd "${ZMQ_ROOT}" \
      && ./autogen.sh \
      && ./configure \
      && make -j4 \
      && make check \
      && sudo make install)
    touch zmq-stamp
}

function build_pkg_config {
  fetch_unpack "${PKG_CONFIG_DOWNLOAD_URL}/${PKG_CONFIG_ROOT}.tar.gz"
  #tar xzf pkg-config-0.23.tar.gz
  #cd pkg-config-0.23
  #./configure --prefix=/usr/local/pkg-config-0.23 --datarootdir=/usr/share
  #make
  #sudo make install
  #/usr/local/pkg-config-0.23/bin
  
  (cd "${PKG_CONFIG_ROOT}" \
    && ./configure --prefix="${BUILD_PREFIX}" --docdir="${BUILD_PREFIX}"/share/doc --datarootdir="${BUILD_PREFIX}"/share \
    && make \
    && sudo make install
   )
}

function build_openssl {
  fetch_unpack "${OPENSSL_DOWNLOAD_URL}/${OPENSSL_ROOT}.tar.gz"
  (cd "${OPENSSL_ROOT}" \
   && ./Configure darwin64-arm64-cc shared \
     enable-ec_nistp_64_gcc_128 \
     no-ssl2 no-ssl3 no-comp \
     --openssldir=/usr/local/ssl/macos-arm64 \
   && make depend -j12 \
   && sudo make install
 )
}

function pre_build {
    build_pkg_config
    build_zmq
    build_openssl
    #build_jansson
    #build_pcre
}

pre_build
