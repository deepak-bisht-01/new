import asyncio
import json
import hashlib
import base64
from typing import Dict, Set
from dataclasses import dataclass, asdict
from enum import Enum

# ==========================================================
# ENUMS & DATA STRUCTURES
# ==========================================================

class MessageType(Enum):
    """P2P Protocol message types"""
    HANDSHAKE = "handshake"
    FILE_ANNOUNCE = "file_announce"
    FILE_REQUEST = "file_request"
    FILE_CHUNK = "file_chunk"
    CHUNK_REQUEST = "chunk_request"
    PEER_LIST = "peer_list"
    HAVE = "have"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    PING = "ping"
    PONG = "pong"

@dataclass
class FileMetadata:
    """Metadata for a shared file"""
    file_hash: str
    filename: str
    file_size: int
    chunk_size: int
    total_chunks: int
    piece_hashes: list  # Hash of each chunk for verification

@dataclass
class ChunkInfo:
    """Information about a file chunk"""
    file_hash: str
    chunk_index: int
    data: bytes
    chunk_hash: str

# ==========================================================
# P2P PROTOCOL IMPLEMENTATION
# ==========================================================

class P2PProtocol(asyncio.Protocol):
    """
    Enhanced BitTorrent-like P2P protocol
    - Handshake exchange
    - File announce/request
    - Chunk-based transfer
    - Peer discovery
    """

    CHUNK_SIZE = 256 * 1024  # 256 KB

    def __init__(self, peer_id: str, file_manager, peer_manager):
        self.peer_id = peer_id
        self.file_manager = file_manager
        self.peer_manager = peer_manager
        self.transport = None
        self.remote_peer_id = None
        self.buffer = b""

        # State trackers
        self.downloading: Dict[str, Set[int]] = {}
        self.uploading: Dict[str, Set[int]] = {}
        self.interested_files: Set[str] = set()

    # ======================================================
    # CONNECTION MANAGEMENT
    # ======================================================

    def connection_made(self, transport):
        """When a connection is established"""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        print(f"[PROTOCOL] ✅ Connection established with {peername}")
        self.send_handshake()

    def data_received(self, data: bytes):
        """Handle incoming data and parse messages"""
        print(f"[RECV RAW] {data!r}")
        self.buffer += data

        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if line.strip():
                try:
                    self.handle_message(line)
                except Exception as e:
                    print(f"[ERROR] Failed to handle message: {e}")

    def connection_lost(self, exc):
        """When the connection is closed"""
        print(f"[PROTOCOL] ❌ Connection lost with {self.remote_peer_id or 'unknown'}")
        if self.remote_peer_id:
            self.peer_manager.remove_peer(self.remote_peer_id)

    # ======================================================
    # MESSAGE UTILITIES
    # ======================================================

    def send_message(self, msg_type: MessageType, payload: dict):
        """Serialize and send a message"""
        message = {
            "type": msg_type.value,
            "peer_id": self.peer_id,
            "payload": payload,
        }
        data = json.dumps(message).encode() + b"\n"

        if self.transport:
            self.transport.write(data)
            print(f"[SEND] {msg_type.value} → {self.remote_peer_id or 'pending'}")

    def handle_message(self, data: bytes):
        """Decode and route message"""
        message = json.loads(data.decode())
        msg_type = MessageType(message["type"])
        peer_id = message["peer_id"]
        payload = message["payload"]

        # Store peer ID if new
        if not self.remote_peer_id:
            self.remote_peer_id = peer_id
            self.peer_manager.add_peer(peer_id, self)
            print(f"[LINKED] Protocol linked with peer ID: {peer_id}")

        handlers = {
            MessageType.HANDSHAKE: self.handle_handshake,
            MessageType.FILE_ANNOUNCE: self.handle_file_announce,
            MessageType.FILE_REQUEST: self.handle_file_request,
            MessageType.CHUNK_REQUEST: self.handle_chunk_request,
            MessageType.FILE_CHUNK: self.handle_file_chunk,
            MessageType.HAVE: self.handle_have,
            MessageType.INTERESTED: self.handle_interested,
            MessageType.PEER_LIST: self.handle_peer_list,
            MessageType.PING: self.handle_ping,
            MessageType.PONG: lambda p, _: print(f"[PONG] ← {p}"),
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(peer_id, payload)
        else:
            print(f"[WARN] No handler for message type: {msg_type.value}")

    # ======================================================
    # HANDSHAKE
    # ======================================================

    def send_handshake(self):
        """Send handshake with available file list"""
        files = self.file_manager.get_available_files()
        print(f"[HANDSHAKE] → Sending {len(files)} files in handshake")
        self.send_message(MessageType.HANDSHAKE, {"files": files})

    def handle_handshake(self, peer_id: str, payload: dict):
        """Respond to handshake"""
        print(f"[HANDSHAKE] ← Received from {peer_id}")
        files = payload.get("files", [])

        for f in files:
            self.peer_manager.add_peer_file(peer_id, f["file_hash"])

        # Only send back if not already sent
        if not getattr(self, "_handshake_replied", False):
            self._handshake_replied = True
            self.send_handshake()

    # ======================================================
    # FILE SHARING
    # ======================================================

    def announce_file(self, metadata: FileMetadata):
        """Announce a file to connected peers"""
        print(f"[ANNOUNCE] Broadcasting {metadata.filename}")
        self.send_message(MessageType.FILE_ANNOUNCE, asdict(metadata))

    def handle_file_announce(self, peer_id: str, payload: dict):
        """Receive a new file announcement"""
        metadata = FileMetadata(**payload)
        print(f"[ANNOUNCE] ← Peer {peer_id} shared {metadata.filename}")
        self.peer_manager.add_peer_file(peer_id, metadata.file_hash)
        self.file_manager.add_remote_file(metadata)

    def request_file(self, file_hash: str):
        """Request metadata and chunks of a file"""
        print(f"[REQUEST] → Requesting file {file_hash}")
        self.send_message(MessageType.FILE_REQUEST, {"file_hash": file_hash})
        self.interested_files.add(file_hash)

    def handle_file_request(self, peer_id: str, payload: dict):
        """Send metadata when a peer requests a file"""
        file_hash = payload["file_hash"]
        metadata = self.file_manager.get_file_metadata(file_hash)

        if metadata:
            print(f"[REQUEST] ← Peer {peer_id} requested {metadata.filename}")
            self.send_message(MessageType.FILE_ANNOUNCE, asdict(metadata))
        else:
            print(f"[WARN] Requested file {file_hash} not found locally")

    # ======================================================
    # CHUNK HANDLING
    # ======================================================

    def request_chunk(self, file_hash: str, chunk_index: int):
        """Ask for a specific chunk"""
        print(f"[CHUNK REQUEST] → {file_hash}:{chunk_index}")
        self.send_message(MessageType.CHUNK_REQUEST, {
            "file_hash": file_hash,
            "chunk_index": chunk_index
        })

    def handle_chunk_request(self, peer_id: str, payload: dict):
        """Send the requested chunk"""
        file_hash = payload["file_hash"]
        chunk_index = payload["chunk_index"]

        print(f"[CHUNK REQUEST] ← {peer_id} wants chunk {chunk_index} of {file_hash}")
        chunk_data = self.file_manager.read_chunk(file_hash, chunk_index)

        if chunk_data:
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            encoded = base64.b64encode(chunk_data).decode()
            self.send_message(MessageType.FILE_CHUNK, {
                "file_hash": file_hash,
                "chunk_index": chunk_index,
                "data": encoded,
                "chunk_hash": chunk_hash
            })
        else:
            print(f"[ERROR] Missing chunk {chunk_index} for {file_hash}")

    def handle_file_chunk(self, peer_id: str, payload: dict):
        """Handle received chunk data"""
        file_hash = payload["file_hash"]
        chunk_index = payload["chunk_index"]
        chunk_data = base64.b64decode(payload["data"])
        chunk_hash = payload["chunk_hash"]

        if hashlib.sha256(chunk_data).hexdigest() != chunk_hash:
            print(f"[ERROR] Hash mismatch for chunk {chunk_index}!")
            return

        success = self.file_manager.write_chunk(file_hash, chunk_index, chunk_data)
        if success:
            print(f"[DOWNLOAD] ✅ Chunk {chunk_index} from {peer_id}")
            self.send_message(MessageType.HAVE, {
                "file_hash": file_hash,
                "chunk_index": chunk_index
            })
            if self.file_manager.is_download_complete(file_hash):
                print(f"[COMPLETE] 🎉 File {file_hash} download finished!")

    # ======================================================
    # OTHER MESSAGES
    # ======================================================

    def handle_have(self, peer_id: str, payload: dict):
        self.peer_manager.add_peer_chunk(peer_id, payload["file_hash"], payload["chunk_index"])
        print(f"[HAVE] ← {peer_id} has chunk {payload['chunk_index']}")

    def handle_interested(self, peer_id: str, payload: dict):
        print(f"[INTERESTED] ← {peer_id} interested in {payload['file_hash']}")


    
    def handle_peer_list(self, peer_id: str, payload: dict):
        """Handle peer list for peer discovery"""
        peers = payload.get("peers", [])
        print(f"[PEERS] Received {len(peers)} peer addresses")
        # Could connect to new peers here
    
    def handle_ping(self, peer_id: str, payload: dict):
        """Handle ping message"""
        self.send_message(MessageType.PONG, {})