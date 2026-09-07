"""Headless LibreOffice PDF Conversion Service with per-run profile isolation.

Converts approved DOCX deliverables to official PDF records without network sockets.
"""

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4
import structlog

log = structlog.get_logger()


class LibreOfficeUnavailableError(RuntimeError):
    """Raised when LibreOffice binary cannot be found on the system or vendor directory."""

    def __init__(self, checked_paths: list[Path | str]) -> None:
        paths_str = "\n  - ".join(str(p) for p in checked_paths)
        message = (
            "LibreOffice binary (soffice) not found for air-gapped PDF conversion.\n"
            f"Checked paths:\n  - {paths_str}\n\n"
            "Offline Installation / Setup Instructions:\n"
            "1. Copy the offline LibreOffice bundle to 'bin/libreoffice/' in the application root, OR\n"
            "2. Install LibreOffice on the host and set the 'SOFFICE_PATH' environment variable to 'soffice.exe',\n"
            "   e.g. export SOFFICE_PATH=\"C:\\Program Files\\LibreOffice\\program\\soffice.exe\""
        )
        super().__init__(message)


class DocxToPdfConverter:
    """Converts DOCX documents to PDF using headless LibreOffice with run-isolated user profile."""

    def __init__(self, soffice_path: Path | str | None = None) -> None:
        self.custom_soffice_path = soffice_path
        self._soffice_path: Path | None = None

    def get_soffice_path(self) -> Path:
        """Resolve and cache soffice path on demand."""
        if self._soffice_path is None:
            self._soffice_path = self._resolve_soffice(self.custom_soffice_path)
        return self._soffice_path

    @staticmethod
    def _resolve_soffice(custom_path: Path | str | None = None) -> Path:
        """Resolve LibreOffice executable path with explicit search locations."""
        checked_paths: list[Path | str] = []

        # 1. Custom or environment override
        env_path = custom_path or os.getenv("SOFFICE_PATH")
        if env_path:
            p = Path(env_path)
            checked_paths.append(p)
            if p.exists() and p.is_file():
                return p

        # 2. Local vendor directory in project
        vendor_locations = [
            Path("bin/libreoffice/program/soffice.exe"),
            Path("bin/libreoffice/program/soffice"),
            Path("../bin/libreoffice/program/soffice.exe"),
            Path("../../bin/libreoffice/program/soffice.exe"),
        ]
        for v in vendor_locations:
            checked_paths.append(v.resolve())
            if v.exists() and v.is_file():
                return v.resolve()

        # 3. Standard Windows installation paths
        if os.name == "nt":
            win_paths = [
                Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
                Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
            ]
            for wp in win_paths:
                checked_paths.append(wp)
                if wp.exists() and wp.is_file():
                    return wp

        # 4. PATH lookup
        which_path = shutil.which("soffice") or shutil.which("libreoffice")
        if which_path:
            return Path(which_path)
        checked_paths.append("PATH: soffice / libreoffice")

        raise LibreOfficeUnavailableError(checked_paths)

    def convert_docx_to_pdf(
        self,
        docx_path: Path,
        output_dir: Path,
        workspace_root: Path | None = None,
        timeout_s: int = 45,
    ) -> Path:
        """Convert DOCX file to PDF using isolated user installation profile."""
        docx_path = Path(docx_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not docx_path.exists():
            raise FileNotFoundError(f"Input DOCX file not found: {docx_path}")

        # Unique run-isolated LibreOffice user profile
        run_id = uuid4().hex[:8]
        ws_base = Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()
        profile_dir = ws_base / ".swaraj" / f"lo-profile-{run_id}"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # File URI format required for LibreOffice UserInstallation
        profile_uri = profile_dir.as_uri()

        cmd = [
            str(self.get_soffice_path()),
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]

        log.info(
            "libreoffice_pdf_conversion_start",
            docx_path=str(docx_path),
            output_dir=str(output_dir),
            run_id=run_id,
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            if proc.returncode != 0:
                err_msg = proc.stderr or proc.stdout
                log.error("libreoffice_conversion_failed", returncode=proc.returncode, error=err_msg)
                raise RuntimeError(f"LibreOffice PDF conversion failed (code {proc.returncode}): {err_msg}")

            expected_pdf = output_dir / f"{docx_path.stem}.pdf"
            if not expected_pdf.exists():
                raise RuntimeError(f"Converted PDF not found at expected path: {expected_pdf}")

            log.info("libreoffice_pdf_conversion_success", pdf_path=str(expected_pdf))
            return expected_pdf

        finally:
            # Clean up run-isolated profile directory
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception as e:
                log.debug("cleanup_lo_profile_error", error=str(e), profile_dir=str(profile_dir))
