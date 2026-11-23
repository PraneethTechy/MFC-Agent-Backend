"""
Manufacturing Cost Agent - Checksum & Hash Verification
Handles SHA-256 calculation, verification, and file registry lookup for idempotency.
"""

import hashlib
import os
from typing import BinaryIO
from .config import EXPECTED_CHECKSUMS


class ChecksumVerifier:
    """Calculates and verifies SHA-256 hashes of ingestion files."""

    @staticmethod
    def calculate_sha256(file_path_or_stream: str | BinaryIO) -> str:
        """Computes the SHA-256 hex digest of a file path or binary stream."""
        hasher = hashlib.sha256()

        if isinstance(file_path_or_stream, str):
            with open(file_path_or_stream, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
        else:
            current_pos = file_path_or_stream.tell() if hasattr(file_path_or_stream, "tell") else None
            try:
                if hasattr(file_path_or_stream, "seek"):
                    file_path_or_stream.seek(0)
                while chunk := file_path_or_stream.read(65536):
                    hasher.update(chunk)
            finally:
                if current_pos is not None and hasattr(file_path_or_stream, "seek"):
                    file_path_or_stream.seek(current_pos)

        return hasher.hexdigest()

    @classmethod
    def verify_source_file(cls, file_path: str) -> tuple[bool, str, str | None]:
        """
        Verifies that the file exists and matches the approved SHA-256 checksum.
        Returns: (is_valid, computed_hash, expected_hash)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found at: {file_path}")

        file_name = os.path.basename(file_path)
        computed_hash = cls.calculate_sha256(file_path)
        expected_hash = EXPECTED_CHECKSUMS.get(file_name)

        if expected_hash is None:
            # Not one of the 4 strict files, return computed hash without strict match failure
            return True, computed_hash, None

        is_match = (computed_hash == expected_hash)
        return is_match, computed_hash, expected_hash

