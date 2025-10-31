import asyncio
import json
import hashlib
import base64
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class MessageType(Enum):
    HANDSHAKE = "handshake"
    FILE_ANNOUNCE = "file_announce"
    FILE_REQUEST = "file_request"
    FILE_CHUNK = "file_chunk"
    CHUNK_REQUEST = "chunk_request"
    CHUNK_NOT_FOUND = "chunk_not_found"
    PEER_LIST = "peer_list"
    HAVE = "have"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    PING = "ping"
    PONG = "pong"


@dataclass
class FileMetadata:
    file_hash: str
    filename: str
    file_size: int
    total_chunks: int
    chunk_size: int = 256 * 1024
    piece_hashes: List[str] = field(default_factory=list)


@dataclass
class ChunkInfo:
    file_hash: str
    chunk_index: int
    data: bytes
    chunk_hash: str


class P2PProtocol(asyncio.Protocol):
    CHUNK_SIZE = 256 * 1024  # 256KB
    HANDSHAKE_TIMEOUT = 15.0
    MAX_CHUNK_RETRIES = 5

    def __init__(self, peer_id: str, file_manager, peer_manager):
        self.peer_id = peer_id
        self.file_manager = file_manager
        self.peer_manager = peer_manager
        self.transport = None
        self.remote_peer_id: Optional[str] = None
        self.buffer = b""
        self.handshake_done = asyncio.get_event_loop().create_future()
        self.retry_counts: Dict[str, int] = {}
        self.handshake_replied = False

    # -------------------------
    # CONNECTION LIFECYCLE
    # -------------------------
    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info("peername")
        print(f"[PROTOCOL] ✅ Connected to {peername}")
        try:
            self.send_handshake()
        except Exception as e:
            print(f"[ERROR] Failed to send handshake: {e}")
        asyncio.create_task(self._wait_for_handshake())

    async def _wait_for_handshake(self):
        try:
            await asyncio.wait_for(self.handshake_done, timeout=self.HANDSHAKE_TIMEOUT)
        except asyncio.TimeoutError:
            print(f"[WARN] Handshake timeout ({self.HANDSHAKE_TIMEOUT}s) — closing transport")
            if self.transport:
                self.transport.close()

    def data_received(self, data: bytes):
        self.buffer += data
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line:
                continue
            try:
                self.handle_message(line)
            except Exception as e:
                print(f"[ERROR] Failed to handle message: {e}")

    def connection_lost(self, exc):
        print(f"[PROTOCOL] ⚠️ Connection lost with {self.remote_peer_id}")
        if self.remote_peer_id:
            try:
                self.peer_manager.remove_peer(self.remote_peer_id)
            except Exception:
                pass

    # -------------------------
    # MESSAGE HANDLING
    # -------------------------
    def send_message(self, msg_type: MessageType, payload: dict):
        try:
            message = {"type": msg_type.value, "peer_id": self.peer_id, "payload": payload}
            data = json.dumps(message).encode() + b"\n"
            if self.transport:
                self.transport.write(data)
        except Exception as e:
            print(f"[ERROR] Could not send message {msg_type.value}: {e}")

    def handle_message(self, raw: bytes):
        message = json.loads(raw.decode())
        msg_type = MessageType(message["type"])
        peer_id = message["peer_id"]
        payload = message["payload"]

        if not self.remote_peer_id:
            self.remote_peer_id = peer_id
            try:
                self.peer_manager.add_peer(peer_id, self)
            except Exception:
                self.peer_manager.peers[peer_id] = self

        handlers = {
            MessageType.HANDSHAKE: self.handle_handshake,
            MessageType.FILE_ANNOUNCE: self.handle_file_announce,
            MessageType.FILE_REQUEST: self.handle_file_request,
            MessageType.CHUNK_REQUEST: self.handle_chunk_request,
            MessageType.FILE_CHUNK: self.handle_file_chunk,
            MessageType.CHUNK_NOT_FOUND: self.handle_chunk_not_found,
            MessageType.PING: self.handle_ping,
            MessageType.PONG: self.handle_pong,
        }

        handler = handlers.get(msg_type)
        if handler:
            try:
                handler(peer_id, payload)
            except Exception as e:
                print(f"[ERROR] Exception in handler for {msg_type.value}: {e}")

    # -------------------------
    # HANDSHAKE
    # -------------------------
    def send_handshake(self):
        files = self.file_manager.get_available_files()
        print(f"[HANDSHAKE] Sending handshake with {len(files)} files")
        self.send_message(MessageType.HANDSHAKE, {"files": files})

    def handle_handshake(self, peer_id: str, payload: dict):
        print(f"[HANDSHAKE] 🤝 Received handshake from {peer_id}")
        files = payload.get("files", [])
        valid_files = 0

        for f in files:
            required = ["file_hash", "filename", "file_size", "total_chunks"]
            if not all(k in f for k in required):
                continue

            f.setdefault("piece_hashes", [])
            f.setdefault("chunk_size", self.CHUNK_SIZE)

            try:
                metadata = FileMetadata(**f)
                self.peer_manager.add_peer_file(peer_id, metadata.file_hash)
                self.file_manager.add_remote_file(metadata)
                valid_files += 1
            except Exception as e:
                print(f"[WARN] Invalid file metadata from {peer_id}: {e}")

        print(f"[HANDSHAKE] ✅ Processed {valid_files}/{len(files)} files from {peer_id}")

        if not self.handshake_done.done():
            self.handshake_done.set_result(True)

        if not self.handshake_replied:
            self.handshake_replied = True
            self.send_handshake()

    # -------------------------
    # CHUNK REQUEST / RESPONSE
    # -------------------------
    def request_chunk(self, file_hash: str, chunk_index: int):
        key = f"{file_hash}:{chunk_index}"
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1
        if self.retry_counts[key] > self.MAX_CHUNK_RETRIES:
            print(f"[ERROR] ❌ Chunk {chunk_index} of {file_hash} failed after {self.MAX_CHUNK_RETRIES} retries.")
            return
        print(f"[CHUNK REQUEST] Requesting chunk {chunk_index} of {file_hash}")
        self.send_message(MessageType.CHUNK_REQUEST, {"file_hash": file_hash, "chunk_index": chunk_index})

    def handle_chunk_request(self, peer_id: str, payload: dict):
        file_hash = payload.get("file_hash")
        chunk_index = payload.get("chunk_index")
        print(f"[CHUNK REQUEST] Peer {peer_id} -> Chunk {chunk_index} of {file_hash}")

        try:
            chunk_data = self.file_manager.read_chunk(file_hash, chunk_index)
        except Exception as e:
            print(f"[ERROR] read_chunk raised: {e}")
            chunk_data = None

        if chunk_data:
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            encoded_data = base64.b64encode(chunk_data).decode()
            self.send_message(
                MessageType.FILE_CHUNK,
                {"file_hash": file_hash, "chunk_index": chunk_index, "data": encoded_data, "chunk_hash": chunk_hash},
            )
            print(f"[UPLOAD] ✅ Sent chunk {chunk_index} of {file_hash[:8]} to {peer_id}")
        else:
            print(f"[WARN] Missing chunk {chunk_index} for {file_hash}")
            self.send_message(MessageType.CHUNK_NOT_FOUND, {"file_hash": file_hash, "chunk_index": chunk_index})

    def handle_file_chunk(self, peer_id: str, payload: dict):
        file_hash = payload.get("file_hash")
        chunk_index = payload.get("chunk_index")
        raw = payload.get("data")
        chunk_hash = payload.get("chunk_hash")

        if not raw:
            print(f"[ERROR] Received FILE_CHUNK with no data for {file_hash}:{chunk_index}")
            return

        try:
            data = base64.b64decode(raw)
        except Exception as e:
            print(f"[ERROR] Failed to decode chunk data: {e}")
            return

        if hashlib.sha256(data).hexdigest() != chunk_hash:
            print(f"[ERROR] ❌ Chunk {chunk_index} hash mismatch for {file_hash}")
            return

        try:
            self.file_manager.write_chunk(file_hash, chunk_index, data)
            print(f"[DOWNLOAD] ✅ Received chunk {chunk_index} from {peer_id}")
            if self.file_manager.is_download_complete(file_hash):
                meta = self.file_manager.get_file_metadata(file_hash)
                fname = meta.filename if meta else file_hash[:8]
                print(f"[SUCCESS] 🎉 File '{fname}' fully downloaded!")
        except Exception as e:
            print(f"[ERROR] write_chunk failed: {e}")

    def handle_chunk_not_found(self, peer_id: str, payload: dict):
        print(f"[INFO] Peer {peer_id} reports missing chunk {payload}")
    async def handle_file_request(self, peer_id: str, payload: dict):
        
        try:
            file_hash = payload.get("file_hash")
            chunk_index = payload.get("chunk_index", 0)
            file_path = self.file_manager.get_file_path_by_hash(file_hash)

            if not file_path or not os.path.exists(file_path):
                print(f"[ERROR] File not found for hash {file_hash}")
                return

            # Read the requested chunk (default 64 KB)
            CHUNK_SIZE = 64 * 1024
            with open(file_path, "rb") as f:
                f.seek(chunk_index * CHUNK_SIZE)
                data = f.read(CHUNK_SIZE)

            if not data:
                print(f"[WARN] Empty chunk requested from {peer_id} for {file_hash}")
                return

            # Send the chunk back
            await self.send_message(peer_id, MessageType.FILE_CHUNK, {
                "file_hash": file_hash,
                "chunk_index": chunk_index,
                "data": data.hex()
            })
            print(f"[CHUNK SEND] 📤 Sent chunk {chunk_index} of {file_hash[:8]} to {peer_id}")

        except Exception as e:
            print(f"[ERROR] Failed to handle FILE_REQUEST from {peer_id}: {e}")

    # -------------------------
    # FILE ANNOUNCE
    # -------------------------
    def handle_file_announce(self, peer_id: str, payload: dict):
        try:
            metadata = FileMetadata(**payload)
            self.peer_manager.add_peer_file(peer_id, metadata.file_hash)
            self.file_manager.add_remote_file(metadata)
            print(f"[ANNOUNCE] 📢 {peer_id} shared '{metadata.filename}' ({metadata.file_hash[:8]})")
        except Exception as e:
            print(f"[ERROR] Failed to handle FILE_ANNOUNCE: {e}")

    # -------------------------
    # PING / PONG
    # -------------------------
    def handle_ping(self, peer_id: str, payload: dict):
        self.send_message(MessageType.PONG, {})

    def handle_pong(self, peer_id: str, payload: dict):
        print(f"[PING] Pong received from {peer_id}")
