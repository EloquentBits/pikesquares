import subprocess
from pathlib import Path

from .console import console

CERT_NAME = "_wildcard_pikesquares_dev"
easyrsa = lambda dir: str(Path(dir) / "EasyRSA-3.1.7" / "easyrsa")

def ensure_pki(conf):
    if Path(conf.PKI_DIR).exists():
        return

    compl = subprocess.run(
        args=[
            easyrsa(conf.EASYRSA_DIR),
            "init-pki",
        ],
        cwd=conf.DATA_DIR,
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
            easyrsa(conf.EASYRSA_DIR),
            '--req-cn=PikeSquares Proxy',
            "--batch",
            "--no-pass",
            "build-ca",
        ],
        cwd=conf.DATA_DIR,
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
            easyrsa(conf.EASYRSA_DIR),
            "--batch",
            "--no-pass",
            "--silent",
            "--subject-alt-name=DNS:*.pikesquares.dev",
            "gen-req",
            CERT_NAME,
        ],
        cwd=conf.DATA_DIR,
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
                (Path(conf.PKI_DIR) / "reqs" / f"{CERT_NAME}.req").exists()]):
        return

    if (Path(conf.PKI_DIR) / "issued" / f"{CERT_NAME}.crt").exists():
        return

    console.info("Signing CSR")
    compl = subprocess.run(
        args=[
            easyrsa(conf.EASYRSA_DIR),
            "--batch",
            "--no-pass",
            "sign-req",
            "server",
            CERT_NAME,
        ],
        cwd=conf.DATA_DIR,
        capture_output=True,
        check=True,
    )
    if compl.returncode != 0:
        console.warning(f"unable to sign csr")
        console.warning(compl.stderr.decode())
    else: # (Path(conf.PKI_DIR) / "ca.crt").exists(): 
        console.info(f"csr signed")
        console.info(compl.stdout.decode())

