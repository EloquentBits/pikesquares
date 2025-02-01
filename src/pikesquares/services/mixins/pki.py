import os
import subprocess

from pikesquares.cli.console import console


class DevicePKIMixin:

    def setup_pki(self):
        if all(
            [
                self.ensure_pki(),
                self.ensure_build_ca(),
                self.ensure_csr(),
                self.ensure_sign_req(),
            ]
        ):
            console.success("Wildcard certificate created.")

    def ensure_pki(self):
        try:
            if self.conf.pki_dir.exists() and next(self.conf.pki_dir.iterdir()):
                return
        except StopIteration:
            # need to remove the pki root dir. it should be empty.
            # easyrsa does not have --no-input option and will try to recreate the directory.
            os.rmdir(self.conf.pki_dir)

        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "init-pki",
            ],
            cwd=str(self.conf.data_dir),
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to initialize PKI")
        else:
            print(f"Initialized PKI @ {self.conf.pki_dir}")
        # set(compl.stdout.decode().split("\n"))

    def ensure_build_ca(self):
        if (self.conf.pki_dir / "ca.crt").exists():
            return

        print("building CA")

        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                '--req-cn=PikeSquares Proxy',
                "--batch",
                "--no-pass",
                "build-ca",
            ],
            cwd=self.conf.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print("unable to build CA")
            print(compl.stderr.decode())
        elif (self.conf.pki_dir / "ca.crt").exists():
            print("CA cert created")
            print(compl.stdout.decode())

        # set(compl.stdout.decode().split("\n"))

    def ensure_csr(self):
        if not (self.conf.pki_dir / "ca.crt").exists():
            print("Unable to create a CSR. CA was not located.")
            return

        if (self.conf.pki_dir / "reqs" / f"{self.cert_name}.req").exists():
            return

        print("generating CSR")
        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "--batch",
                "--no-pass",
                "--silent",
                "--subject-alt-name=DNS:*.pikesquares.dev",
                "gen-req",
                self.cert_name,
            ],
            cwd=self.conf.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to generate csr")
            print(compl.stderr.decode())
        else:  # (Path(conf.pki_dir) / "ca.crt").exists():
            print(f"csr created")
            print(compl.stdout.decode())

    def ensure_sign_req(self):
        if not all(
            [
                self.conf.pki_dir.exists(),
                (self.conf.pki_dir / "ca.crt").exists(),
                (self.conf.pki_dir / "reqs" / f"{self.cert_name}.req").exists(),
            ]
        ):
            return

        if (self.conf.pki_dir / "issued" / f"{self.cert_name}.crt").exists():
            return

        print("Signing CSR")
        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "--batch",
                "--no-pass",
                "sign-req",
                "server",
                self.cert_name,
            ],
            cwd=self.conf.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to sign csr")
            print(compl.stderr.decode())
        else:  # (Path(conf.pki_dir) / "ca.crt").exists():
            print(f"csr signed")
            print(compl.stdout.decode())
