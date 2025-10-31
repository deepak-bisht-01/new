import os
import hashlib
import json
from typing import Dict, Optional, List
from pathlib import Path
from dataclasses import asdict


class FileManager:
    """
    Manages file storage, chunking, and metadata
    Similar to BitTorrent's piece management
    """

    CHUNK_SIZE = 256 * 1024  # 256KB chunks

    def __init__(self, download_dir: str = "./downloads", shared_dir: str = "./shared"):
        self.download_dir = Path(download_dir)
        self.shared_dir = Path(shared_dir)
        self.metadata_dir = Path(download_dir) / ".metadata"

        # Create directories
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Track files
        self.shared_files: Dict[str, dict] = {}
        self.downloading_files: Dict[str, dict] = {}
        self.file_metadata: Dict[str, dict] = {}

        # Load existing shared files
        self.scan_shared_directory()

    # ----------------------------------------------------------------------
    # 🔹 Hashing Utilities
    # ----------------------------------------------------------------------
    def calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA-256 hash of entire file"""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(self.CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()

    def calculate_chunk_hashes(self, filepath: Path, total_chunks: int) -> List[str]:
        """Calculate hash for each chunk"""
        chunk_hashes = []
        with open(filepath, "rb") as f:
            for _ in range(total_chunks):
                chunk_data = f.read(self.CHUNK_SIZE)
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                chunk_hashes.append(chunk_hash)
        return chunk_hashes

    # ----------------------------------------------------------------------
    # 🔹 Shared Files Handling
    # ----------------------------------------------------------------------
    def add_shared_file(self, filepath: str) -> Optional[dict]:
        """Add a file to shared files and create metadata"""
        filepath = Path(filepath)
        if not filepath.exists():
            print(f"[ERROR] File not found: {filepath}")
            return None

        file_size = filepath.stat().st_size
        total_chunks = (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE

        print(f"[FILE] Processing {filepath.name} ({file_size} bytes, {total_chunks} chunks)")

        # Calculate hashes
        file_hash = self.calculate_file_hash(filepath)
        chunk_hashes = self.calculate_chunk_hashes(filepath, total_chunks)

        # Create metadata
        metadata = {
            "file_hash": file_hash,
            "filename": filepath.name,
            "file_size": file_size,
            "chunk_size": self.CHUNK_SIZE,
            "total_chunks": total_chunks,
            "piece_hashes": chunk_hashes,
            "filepath": str(filepath.absolute()),
        }

        self.shared_files[file_hash] = metadata
        self.file_metadata[file_hash] = metadata
        self.save_metadata(file_hash, metadata)

        print(f"[SHARED] File added: {filepath.name} (hash: {file_hash[:16]}...)")
        return metadata

    def scan_shared_directory(self):
        """Scan shared directory for files"""
        if not self.shared_dir.exists():
            return

        print(f"[SCAN] Scanning {self.shared_dir} for shared files...")
        for filepath in self.shared_dir.iterdir():
            if filepath.is_file():
                self.add_shared_file(str(filepath))

    async def rescan_shared_files(self):
        """Rescan shared folder and rebuild shared_files list"""
        new_files = self.scan_shared_directory()
        self.shared_files = new_files or {}
        print(f"[SCAN] Re-indexed {len(self.shared_files)} files in {self.shared_dir}")

    # ----------------------------------------------------------------------
    # 🔹 Metadata Management
    # ----------------------------------------------------------------------
    def get_available_files(self) -> List[dict]:
        """Get list of all available files"""
        files = []
        for file_hash, metadata in self.shared_files.items():
            files.append(
                {
                    "file_hash": file_hash,
                    "filename": metadata["filename"],
                    "file_size": metadata["file_size"],
                    "total_chunks": metadata["total_chunks"],
                }
            )
        return files

    def get_file_metadata(self, file_hash: str) -> Optional[dict]:
        """Get metadata for a specific file"""
        return self.file_metadata.get(file_hash)

    def store_metadata(self, metadata: dict):
        """Store metadata for a file being downloaded"""
        if isinstance(metadata, dict):
            file_hash = metadata["file_hash"]
        else:
            file_hash = metadata.file_hash
            metadata = asdict(metadata)

        self.file_metadata[file_hash] = metadata
        self.save_metadata(file_hash, metadata)

    def save_metadata(self, file_hash: str, metadata: dict):
        """Save metadata to disk"""
        metadata_file = self.metadata_dir / f"{file_hash}.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def load_metadata(self, file_hash: str) -> Optional[dict]:
        """Load metadata from disk"""
        metadata_file = self.metadata_dir / f"{file_hash}.json"
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                return json.load(f)
        return None

    # ----------------------------------------------------------------------
    # 🔹 Download Management
    # ----------------------------------------------------------------------
    def start_download(self, file_hash: str) -> bool:
        """Initialize a new download"""
        metadata = self.file_metadata.get(file_hash)
        if not metadata:
            print(f"[ERROR] No metadata for {file_hash}")
            return False

        download_path = self.download_dir / metadata["filename"]
        temp_path = self.download_dir / f".{metadata['filename']}.part"

        with open(temp_path, "wb") as f:
            f.seek(metadata["file_size"] - 1)
            f.write(b"\0")

        self.downloading_files[file_hash] = {
            "metadata": metadata,
            "temp_path": str(temp_path),
            "final_path": str(download_path),
            "downloaded_chunks": set(),
            "total_chunks": metadata["total_chunks"],
        }

        print(f"[DOWNLOAD] Started: {metadata['filename']}")
        return True

    def read_chunk(self, file_hash: str, chunk_index: int) -> Optional[bytes]:
    
        metadata = self.shared_files.get(file_hash)
        if not metadata:
            print(f"[ERROR] No metadata for hash {file_hash[:16]}")
            return None

        filepath = Path(metadata.get("filepath", ""))
        if not filepath.exists():
            print(f"[ERROR] File not found on disk: {filepath}")
            return None

        offset = chunk_index * self.CHUNK_SIZE
        try:
            with open(filepath, "rb") as f:
                f.seek(offset)
                data = f.read(self.CHUNK_SIZE)
                if not data:
                    print(f"[WARN] Empty chunk read at index {chunk_index}")
                    return None
                return data
        except Exception as e:
            print(f"[ERROR] Failed to read chunk {chunk_index}: {e}")
            return None


    def write_chunk(self, file_hash: str, chunk_index: int, data: bytes) -> bool:
        """Write a downloaded chunk to disk"""
        download_info = self.downloading_files.get(file_hash)
        if not download_info:
            if not self.start_download(file_hash):
                return False
            download_info = self.downloading_files[file_hash]

        temp_path = Path(download_info["temp_path"])
        offset = chunk_index * self.CHUNK_SIZE

        with open(temp_path, "r+b") as f:
            f.seek(offset)
            f.write(data)

        download_info["downloaded_chunks"].add(chunk_index)
        progress = len(download_info["downloaded_chunks"]) / download_info["total_chunks"] * 100
        print(f"[PROGRESS] {download_info['metadata']['filename']}: {progress:.1f}%")

        return True

    def is_download_complete(self, file_hash: str) -> bool:
        """Check if download is complete"""
        download_info = self.downloading_files.get(file_hash)
        if not download_info:
            return False

        if len(download_info["downloaded_chunks"]) == download_info["total_chunks"]:
            self.finalize_download(file_hash)
            return True
        return False

    def finalize_download(self, file_hash: str):
        """Verify and finalize a completed download"""
        download_info = self.downloading_files[file_hash]
        temp_path = Path(download_info["temp_path"])
        final_path = Path(download_info["final_path"])

        calculated_hash = self.calculate_file_hash(temp_path)
        if calculated_hash == file_hash:
            temp_path.rename(final_path)
            print(f"[COMPLETE] Download verified and saved: {final_path}")

            self.shared_files[file_hash] = download_info["metadata"]
            self.shared_files[file_hash]["filepath"] = str(final_path)
            del self.downloading_files[file_hash]
        else:
            print(f"[ERROR] Hash mismatch! Expected {file_hash}, got {calculated_hash}")

    def get_missing_chunks(self, file_hash: str) -> List[int]:
        """Get list of chunks still needed for a download"""
        download_info = self.downloading_files.get(file_hash)
        if not download_info:
            metadata = self.file_metadata.get(file_hash)
            if metadata:
                return list(range(metadata["total_chunks"]))
            return []

        all_chunks = set(range(download_info["total_chunks"]))
        missing = all_chunks - download_info["downloaded_chunks"]
        return list(missing)

    def get_download_progress(self, file_hash: str) -> float:
        """Get download progress percentage"""
        download_info = self.downloading_files.get(file_hash)
        if not download_info:
            return 0.0

        return len(download_info["downloaded_chunks"]) / download_info["total_chunks"] * 100

    # ----------------------------------------------------------------------
    # 🔹 Remote Metadata Handling (Fixed)
    # ----------------------------------------------------------------------
    def add_remote_file(self, metadata):
        """Add metadata for a remote file announced by another peer"""
        if hasattr(metadata, "file_hash"):
            file_hash = metadata.file_hash
            entry = {
                "filename": getattr(metadata, "filename", None),
                "file_hash": file_hash,
                "file_size": getattr(metadata, "file_size", None),
                "chunk_size": getattr(metadata, "chunk_size", self.CHUNK_SIZE),
                "total_chunks": getattr(metadata, "total_chunks", None),
                "piece_hashes": getattr(metadata, "piece_hashes", []),
            }
        elif isinstance(metadata, dict):
            file_hash = metadata.get("file_hash")
            entry = {
                "filename": metadata.get("filename"),
                "file_hash": file_hash,
                "file_size": metadata.get("file_size"),
                "chunk_size": metadata.get("chunk_size", self.CHUNK_SIZE),
                "total_chunks": metadata.get("total_chunks"),
                "piece_hashes": metadata.get("piece_hashes", []),
            }
        else:
            print(f"[WARN] Unsupported metadata type: {type(metadata)}")
            return

        if file_hash and file_hash not in self.shared_files:
            self.shared_files[file_hash] = entry.copy()
            self.file_metadata[file_hash] = entry.copy()
            print(f"[REMOTE FILE] Added metadata for {entry.get('filename') or file_hash[:8]}")
