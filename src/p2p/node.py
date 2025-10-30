import asyncio
from typing import Optional

# Imports moved to the top for best practice
from .protocol import P2PProtocol, FileMetadata
from .file_manager import FileManager
from .peer_manager import PeerManager


class P2PNode:
    def __init__(self, peer_id: str, host: str = "0.0.0.0", port: int = 5001, shared_folder: str = "./shared"):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.shared_folder = shared_folder

        self.file_manager = FileManager(shared_folder)
        self.peer_manager = PeerManager(self)

        self.server = None
        self.running = False
        self.download_tasks = {}

    # ------------------------------------------------------------
    # 🟢 START NODE
    # ------------------------------------------------------------
    async def start(self):
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

        await self.run_menu()

    # ------------------------------------------------------------
    # 🟣 CONNECTION HANDLING
    # ------------------------------------------------------------
    async def _handle_connection(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"\n[PEER] New connection from {addr}")

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
        class Transport:
            def write(self, data):
                writer.write(data)
            def close(self):
                writer.close()
            def get_extra_info(self, name):
                return writer.get_extra_info(name)
        return Transport()

    # ------------------------------------------------------------
    # 🟢 CONNECT TO ANOTHER PEER
    # ------------------------------------------------------------
    async def connect_to_peer(self, host: str, port: int):
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

    # ------------------------------------------------------------
    # 🟢 FILE SHARING
    # ------------------------------------------------------------
    def share_file(self, filepath: str):
        metadata_dict = self.file_manager.add_shared_file(filepath)
        if metadata_dict:
            metadata_dict.pop("filepath", None)
            file_meta = FileMetadata(**metadata_dict)

            for peer_id, protocol in self.peer_manager.peers.items():
                protocol.announce_file(file_meta)

            print(f"✓ File shared and announced: {metadata_dict['filename']}")
            print(f"   Hash: {metadata_dict['file_hash']}")
            return metadata_dict
        return None

    # ------------------------------------------------------------
    # 🟢 FILE DOWNLOAD
    # ------------------------------------------------------------
    async def download_file(self, file_hash: str):
        metadata = self.file_manager.get_file_metadata(file_hash)
        if not metadata:
            print(f"[ERROR] No metadata for file {file_hash}")
            return False

        print(f"\n{'='*60}")
        print(f"📥 Starting download: {metadata['filename']}")
        print(f"{'='*60}")
        print(f"Hash: {file_hash}")
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
                print(f"[WAIT] No peers available for remaining chunks.")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(0.5)

    # ------------------------------------------------------------
    # 🟢 CLI MENU (Corrected with non-blocking input)
    # ------------------------------------------------------------
    async def run_menu(self):
        loop = asyncio.get_running_loop()
        while True:
            print(f"\n📡 P2P Node Menu ({self.peer_id})")
            print("=" * 60)
            print("1. List my shared files")
            print("2. List available files from peers")
            print("3. Connect to another peer")
            print("4. Download a file by hash")
            print("5. Show node status")
            print("6. Exit")
            print("=" * 60)

            # Use run_in_executor to avoid blocking the event loop
            prompt = "Enter your choice (1–6): "
            choice = await loop.run_in_executor(None, input, prompt)
            choice = choice.strip()

            if choice == "1":
                self.list_shared_files()

            elif choice == "2":
                self.list_available_files()

            elif choice == "3":
                host_prompt = "Enter peer host: "
                port_prompt = "Enter peer port: "
                host = await loop.run_in_executor(None, input, host_prompt)
                port_str = await loop.run_in_executor(None, input, port_prompt)
                await self.connect_to_peer(host.strip(), int(port_str.strip()))

            elif choice == "4":
                hash_prompt = "Enter file hash: "
                file_hash = await loop.run_in_executor(None, input, hash_prompt)
                await self.download_file(file_hash.strip())

            elif choice == "5":
                self.get_status()

            elif choice == "6":
                print("Exiting node...")
                if self.server:
                    self.server.close()
                for task in self.download_tasks.values():
                    task.cancel()
                break

            else:
                print("Invalid choice. Please enter a number 1–6.")

    # ------------------------------------------------------------
    # 🟢 UTILS
    # ------------------------------------------------------------
    def list_shared_files(self):
        files = self.file_manager.get_available_files()
        print(f"\n{'='*60}")
        print(f"📁 Shared Files ({len(files)})")
        print(f"{'='*60}")
        if not files:
            print("No files shared yet.")
        else:
            for i, file_info in enumerate(files, 1):
                print(f"\n{i}. {file_info['filename']}")
                print(f"   Hash: {file_info['file_hash']}")
                print(f"   Size: {file_info['file_size']:,} bytes")
                print(f"   Chunks: {file_info['total_chunks']}")
        print(f"\n{'='*60}\n")

    def list_available_files(self):
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
                if file_hash in available_files:
                     available_files[file_hash]["peer_count"] += 1

        if not available_files:
            print("No files available from peers.")
        else:
            for i, (file_hash, info) in enumerate(available_files.items(), 1):
                metadata = info["metadata"]
                print(f"\n{i}. {metadata['filename']}")
                print(f"   Hash: {file_hash}")
                print(f"   Size: {metadata['file_size']:,} bytes")
                print(f"   Peers: {info['peer_count']}")
        print(f"\n{'='*60}\n")

    def get_status(self):
        print(f"\n{'='*60}")
        print(f"📊 Node Status")
        print(f"{'='*60}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Connected Peers: {self.peer_manager.get_peer_count()}")
        print(f"Shared Files: {len(self.file_manager.shared_files)}")
        print(f"Active Downloads: {len(self.download_tasks)}")
        print(f"{'='*60}\n")