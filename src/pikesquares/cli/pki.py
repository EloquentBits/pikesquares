import subprocess
from pathlib import Path

import structlog

from .console import console

logger = structlog.get_logger()

CERT_NAME = "_wildcard_pikesquares_dev"


def ensure_pki(conf):
    if Path(conf.PKI_DIR).exists():
        return

    compl = subprocess.run(
        args=[str(conf.EASYRSA_BIN), "init-pki"],
        cwd=conf.data_dir,
        capture_output=True,
        check=True,
    )
    if compl.returncode != 0:
        console.warning(f"unable to initialize PKI")
    else:
        console.info(f"Initialized PKI @ {conf.PKI_DIR}")
    #set(compl.stdout.decode().split("\n"))

def ensure_build_ca(conf):
    if not Path(conf.PKI_DIR).exists():
        console.warning(f"Unable to create CA. PKI was not located.")
        return

    if (Path(conf.PKI_DIR) / "ca.crt").exists():
        return

    console.info("building CA")

    compl = subprocess.run(
        args=[
            str(conf.EASYRSA_BIN),
            '--req-cn=PikeSquares Proxy',
            "--batch",
            "--no-pass",
            "build-ca",
        ],
        cwd=conf.data_dir,
        capture_output=True,
        check=True,
    )
    if compl.returncode != 0:
        console.warning(f"unable to build CA")
        console.warning(compl.stderr.decode())
    elif (Path(conf.PKI_DIR) / "ca.crt").exists(): 
        console.info(f"CA cert created")
        console.info(compl.stdout.decode())

    #set(compl.stdout.decode().split("\n"))

def ensure_csr(conf):
    if not Path(conf.PKI_DIR).exists():
        console.warning("Unable to create a CSR. PKI was not located.")
        return

    if not (Path(conf.PKI_DIR) / "ca.crt").exists():
        console.warning("Unable to create a CSR. CA was not located.")
        return

    if (Path(conf.PKI_DIR) / "reqs" / f"{CERT_NAME}.req").exists():
        return

    console.info("generating CSR")
    compl = subprocess.run(
        args=[
            str(conf.EASYRSA_BIN),
            "--batch",
            "--no-pass",
            "--silent",
            "--subject-alt-name=DNS:*.pikesquares.dev",
            "gen-req",
            CERT_NAME,
        ],
        cwd=conf.data_dir,
        capture_output=True,
        check=True,
    )
    if compl.returncode != 0:
        console.warning(f"unable to generate csr")
        console.warning(compl.stderr.decode())
    else: # (Path(conf.PKI_DIR) / "ca.crt").exists(): 
        console.info(f"csr created")
        console.info(compl.stdout.decode())

def ensure_sign_req(conf):
    if not all([Path(conf.PKI_DIR).exists(),
                (Path(conf.PKI_DIR) / "ca.crt").exists(),
                (Path(conf.PKI_DIR) / "reqs" / f"{}.req").exists()]):
        return

    if (Path(conf.PKI_DIR) / "issued" / "_wildcard_pikesquares_dev.crt").exists():
        return

    console.info("Signing CSR")
    compl = subprocess.run(
        args=[
            str(conf.EASYRSA_BIN),
            "--batch",
            "--no-pass",
            "sign-req",
            "server",
            "_wildcard_pikesquares_dev",
        ],
        cwd=conf.data_dir,
        capture_output=True,
        check=True,
    )
    if compl.returncode != 0:
        console.warning(f"unable to sign csr")
        console.warning(compl.stderr.decode())
    else: # (Path(conf.PKI_DIR) / "ca.crt").exists(): 
        console.info(f"csr signed")
        console.info(compl.stdout.decode())

# easyrsa init-pki
# easyrsa build-ca
# easyrsa gen-req "*.pikesquares.dev"
# easyrsa sign-req server *.pikesquares.dev

