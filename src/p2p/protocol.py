import asyncio
import json
import hashlib
import os
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

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

class P2PProtocol(asyncio.Protocol):
    """
    BitTorrent-like P2P file transfer protocol
    Features:
    - Chunk-based file transfer
    - Multiple simultaneous downloads
    - Piece verification
    - Peer discovery
    """
    
    CHUNK_SIZE = 256 * 1024  # 256KB chunks
    
    def __init__(self, peer_id: str, file_manager, peer_manager):
        self.peer_id = peer_id
        self.file_manager = file_manager
        self.peer_manager = peer_manager
        self.transport = None
        self.remote_peer_id = None
        self.buffer = b""
        
        # Download/upload state
        self.downloading: Dict[str, Set[int]] = {}  # file_hash -> set of chunk indices
        self.uploading: Dict[str, Set[int]] = {}
        self.interested_files: Set[str] = set()
        
    def connection_made(self, transport):
        """Called when connection is established"""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        print(f"[PROTOCOL] Connection established with {peername}")
        
        # Send handshake
        self.send_handshake()
    
    def data_received(self, data: bytes):
        """Called when data is received"""
        self.buffer += data
        
        # Process complete messages
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if line:
                try:
                    self.handle_message(line)
                except Exception as e:
                    print(f"[ERROR] Failed to handle message: {e}")
    
    def connection_lost(self, exc):
        """Called when connection is lost"""
        print(f"[PROTOCOL] Connection lost with {self.remote_peer_id}")
        if self.remote_peer_id:
            self.peer_manager.remove_peer(self.remote_peer_id)
    
    def send_message(self, msg_type: MessageType, payload: dict):
        """Send a protocol message"""
        message = {
            "type": msg_type.value,
            "peer_id": self.peer_id,
            "payload": payload
        }
        data = json.dumps(message).encode() + b'\n'
        
        if self.transport:
            self.transport.write(data)
    
    def handle_message(self, data: bytes):
        """Handle incoming protocol message"""
        try:
            message = json.loads(data.decode())
            msg_type = MessageType(message["type"])
            peer_id = message["peer_id"]
            payload = message["payload"]
            
            # Update remote peer ID
            if not self.remote_peer_id:
                self.remote_peer_id = peer_id
                self.peer_manager.add_peer(peer_id, self)
            
            # Route to handler
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
            }
            
            handler = handlers.get(msg_type)
            if handler:
                handler(peer_id, payload)
                
        except Exception as e:
            print(f"[ERROR] Message handling failed: {e}")
    
    def send_handshake(self):
        """Send handshake with available files"""
        files = self.file_manager.get_available_files()
        self.send_message(MessageType.HANDSHAKE, {"files": files})
    
    def handle_handshake(self, peer_id: str, payload: dict):
        """Handle handshake from peer"""
        print(f"[HANDSHAKE] Received from {peer_id}")
        files = payload.get("files", [])
        
        # Update peer's available files
        for file_info in files:
            self.peer_manager.add_peer_file(peer_id, file_info["file_hash"])
        
        # Send our files back
        self.send_handshake()
    
    def announce_file(self, metadata: FileMetadata):
        """Announce a new file to connected peers"""
        self.send_message(MessageType.FILE_ANNOUNCE, asdict(metadata))
    
    def handle_file_announce(self, peer_id: str, payload: dict):
        """Handle file announcement from peer"""
        file_hash = payload["file_hash"]
        print(f"[ANNOUNCE] Peer {peer_id} has file {payload['filename']}")
        
        # Add to peer's file list
        self.peer_manager.add_peer_file(peer_id, file_hash)
        
        # Store metadata
            # ✅ Create metadata object and store it locally for future downloads
        metadata = FileMetadata(**payload)
        self.file_manager.add_remote_file(metadata)

    
    def request_file(self, file_hash: str):
        """Request to download a file"""
        self.send_message(MessageType.FILE_REQUEST, {"file_hash": file_hash})
        self.interested_files.add(file_hash)
        self.send_message(MessageType.INTERESTED, {"file_hash": file_hash})
    
    def handle_file_request(self, peer_id: str, payload: dict):
        """Handle file download request"""
        file_hash = payload["file_hash"]
        print(f"[REQUEST] Peer {peer_id} wants file {file_hash}")
        
        # Send file metadata
        metadata = self.file_manager.get_file_metadata(file_hash)
        if metadata:
            self.send_message(MessageType.FILE_ANNOUNCE, asdict(metadata))
    
    def request_chunk(self, file_hash: str, chunk_index: int):
        """Request a specific chunk"""
        self.send_message(MessageType.CHUNK_REQUEST, {
            "file_hash": file_hash,
            "chunk_index": chunk_index
        })
    
    def handle_chunk_request(self, peer_id: str, payload: dict):
    
        file_hash = payload["file_hash"]
        chunk_index = payload["chunk_index"]

        print(f"[CHUNK REQUEST] Peer {peer_id} wants chunk {chunk_index} of {file_hash}")

    # Read and send chunk
        chunk_data = self.file_manager.read_chunk(file_hash, chunk_index)
        if chunk_data:
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()

        # Send chunk (encode binary data as base64 for JSON)
            import base64
            self.send_message(MessageType.FILE_CHUNK, {
                "file_hash": file_hash,
                "chunk_index": chunk_index,
                "data": base64.b64encode(chunk_data).decode(),
                "chunk_hash": chunk_hash
        })
        else:
            print(f"[ERROR] Could not find chunk {chunk_index} for {file_hash}")

    
    def handle_file_chunk(self, peer_id: str, payload: dict):
        """Handle received file chunk"""
        import base64
        
        file_hash = payload["file_hash"]
        chunk_index = payload["chunk_index"]
        chunk_data = base64.b64decode(payload["data"])
        chunk_hash = payload["chunk_hash"]
        
        # Verify chunk hash
        calculated_hash = hashlib.sha256(chunk_data).hexdigest()
        if calculated_hash != chunk_hash:
            print(f"[ERROR] Chunk {chunk_index} hash mismatch!")
            return
        
        # Save chunk
        success = self.file_manager.write_chunk(file_hash, chunk_index, chunk_data)
        if success:
            print(f"[DOWNLOAD] Received chunk {chunk_index} from {peer_id}")
            
            # Announce we have this chunk
            self.send_message(MessageType.HAVE, {
                "file_hash": file_hash,
                "chunk_index": chunk_index
            })
            
            # Check if download is complete
            if self.file_manager.is_download_complete(file_hash):
                print(f"[COMPLETE] File {file_hash} download finished!")
    
    def handle_have(self, peer_id: str, payload: dict):
        """Handle 'have' message - peer has a chunk"""
        file_hash = payload["file_hash"]
        chunk_index = payload["chunk_index"]
        
        # Update peer's chunk availability
        self.peer_manager.add_peer_chunk(peer_id, file_hash, chunk_index)
    
    def handle_interested(self, peer_id: str, payload: dict):
        """Handle 'interested' message"""
        file_hash = payload["file_hash"]
        print(f"[INTERESTED] Peer {peer_id} is interested in {file_hash}")
    
    def handle_peer_list(self, peer_id: str, payload: dict):
        """Handle peer list for peer discovery"""
        peers = payload.get("peers", [])
        print(f"[PEERS] Received {len(peers)} peer addresses")
        # Could connect to new peers here
    
    def handle_ping(self, peer_id: str, payload: dict):
        """Handle ping message"""
        self.send_message(MessageType.PONG, {})