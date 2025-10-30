import asyncio
import json
from pathlib import Path
from typing import Optional, List
from .protocol import P2PProtocol, MessageType
from .file_manager import FileManager
from .peer_manager import PeerManager


class P2PNode:
    def __init__(self, peer_id, host="127.0.0.1", port=6000, shared_folder="./shared"):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.shared_folder = shared_folder

        # Initialize managers
        from .file_manager import FileManager
        from .peer_manager import PeerManager

        self.file_manager = FileManager(shared_folder)
        self.peer_manager = PeerManager(self)

        self.server = None
        self.running = False

    async def start(self):
        """Start the P2P node"""
        print(f"\n{'='*60}")
        print(f"🚀 Starting P2P File Sharing Node")
        print(f"{'='*60}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Listening on: {self.host}:{self.port}")
        print(f"{'='*60}\n")

        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )

        print(f"✓ Server started on {self.host}:{self.port}")
        print(f"✓ Shared files: {len(self.file_manager.shared_files)}")

        async with self.server:
            await self.server.serve_forever()

    async def _handle_connection(self, reader, writer):
        """Handle incoming connection"""
        addr = writer.get_extra_info('peername')
        print(f"[CONNECTION] New connection from {addr}")

        protocol = P2PProtocol(
            self.peer_id,
            self.file_manager,
            self.peer_manager
        )

        transport = self._AsyncioTransport(reader, writer)
        protocol.connection_made(transport)

        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                protocol.data_received(data)
        except Exception as e:
            print(f"[ERROR] Connection error: {e}")
        finally:
            protocol.connection_lost(None)
            writer.close()
            await writer.wait_closed()

    def _AsyncioTransport(self, reader, writer):
        raise NotImplementedError

    async def connect_to_peer(self, host: str, port: int):
        """Connect to another peer"""
        try:
            print(f"[CONNECT] Connecting to {host}:{port}")
            reader, writer = await asyncio.open_connection(host, port)

            protocol = P2PProtocol(
                self.peer_id,
                self.file_manager,
                self.peer_manager
            )

            transport = self._AsyncioTransport(reader, writer)
            protocol.connection_made(transport)

            asyncio.create_task(self._handle_peer_data(reader, protocol))

            print(f"✓ Connected to {host}:{port}")
            return protocol

        except Exception as e:
            print(f"[ERROR] Failed to connect to {host}:{port}: {e}")
            return None

    async def _handle_peer_data(self, reader, protocol):
        """Handle data from connected peer"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                protocol.data_received(data)
        except Exception as e:
            print(f"[ERROR] Peer data error: {e}")
        finally:
            protocol.connection_lost(None)

    def share_file(self, filepath: str):
    
     metadata = self.file_manager.add_shared_file(filepath)
     if metadata:
        from .protocol import FileMetadata

        # Remove keys not accepted by FileMetadata
        metadata.pop("filepath", None)

        file_meta = FileMetadata(**metadata)

        for peer_id, protocol in self.peer_manager.peers.items():
            protocol.announce_file(file_meta)

        print(f"✓ File shared and announced: {metadata['filename']}")
        return metadata
     return None


    async def download_file(self, file_hash: str):
        """Download a file from peers"""
        metadata = self.file_manager.get_file_metadata(file_hash)
        if not metadata:
            print(f"[ERROR] No metadata for file {file_hash}")
            return False

        print(f"\n{'='*60}")
        print(f"📥 Starting download: {metadata['filename']}")
        print(f"{'='*60}")
        print(f"File size: {metadata['file_size']:,} bytes")
        print(f"Total chunks: {metadata['total_chunks']}")
        print(f"{'='*60}\n")

        if not self.file_manager.start_download(file_hash):
            return False

        task = asyncio.create_task(self._download_chunks(file_hash))
        self.download_tasks[file_hash] = task

        await task
        return True

    async def _download_chunks(self, file_hash: str):
        """Download all chunks for a file"""
        while True:
            missing_chunks = self.file_manager.get_missing_chunks(file_hash)

            if not missing_chunks:
                print(f"\n✓ Download complete!")
                break

            requested_count = 0
            for chunk_index in missing_chunks[:10]:
                peer_id = self.peer_manager.get_best_peer_for_chunk(file_hash, chunk_index)
                if peer_id:
                    protocol = self.peer_manager.get_peer(peer_id)
                    if protocol:
                        protocol.request_chunk(file_hash, chunk_index)
                        requested_count += 1

            if requested_count == 0:
                print(f"[WARNING] No peers available for remaining chunks")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(0.5)

    def list_shared_files(self):
        """List all shared files"""
        files = self.file_manager.get_available_files()
        print(f"\n{'='*60}")
        print(f"📁 Shared Files ({len(files)})")
        print(f"{'='*60}")

        if not files:
            print("No files shared yet.")
        else:
            for i, file_info in enumerate(files, 1):
                print(f"\n{i}. {file_info['filename']}")
                print(f"   Hash: {file_info['file_hash'][:32]}...")
                print(f"   Size: {file_info['file_size']:,} bytes")
                print(f"   Chunks: {file_info['total_chunks']}")

        print(f"\n{'='*60}\n")

    def list_available_files(self):
        """List files available from peers"""
        print(f"\n{'='*60}")
        print(f"🌐 Available Files from Peers")
        print(f"{'='*60}")

        available_files = {}
        for peer_id in self.peer_manager.get_all_peers():
            file_hashes = self.peer_manager.get_peer_files(peer_id)
            for file_hash in file_hashes:
                if file_hash not in available_files:
                    metadata = self.file_manager.get_file_metadata(file_hash)
                    if metadata:
                        available_files[file_hash] = {
                            "metadata": metadata,
                            "peer_count": 0
                        }
                available_files[file_hash]["peer_count"] += 1

        if not available_files:
            print("No files available from peers.")
        else:
            for i, (file_hash, info) in enumerate(available_files.items(), 1):
                metadata = info["metadata"]
                print(f"\n{i}. {metadata['filename']}")
                print(f"   Hash: {file_hash[:32]}...")
                print(f"   Size: {metadata['file_size']:,} bytes")
                print(f"   Peers: {info['peer_count']}")

        print(f"\n{'='*60}\n")

    def get_status(self):
        """Get node status"""
        print(f"\n{'='*60}")
        print(f"📊 Node Status")
        print(f"{'='*60}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Connected Peers: {self.peer_manager.get_peer_count()}")
        print(f"Shared Files: {len(self.file_manager.shared_files)}")
        print(f"Active Downloads: {len(self.download_tasks)}")
        print(f"{'='*60}\n")
