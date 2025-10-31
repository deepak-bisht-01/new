import asyncio
import socket
from pathlib import Path
from typing import Optional, List
from .protocol import P2PProtocol, MessageType
from .file_manager import FileManager
from .peer_manager import PeerManager


class P2PNode:
    def __init__(
        self,
        peer_id: str,
        host: str = "0.0.0.0",
        port: int = 5001,
<<<<<<< HEAD
        shared_folder: Optional[str] = None,
=======
        shared_folder: str = "./shared",
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
    ):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        if not shared_folder:
            user_input = input("Enter the directory to share (default = ./shared): ").strip()
            shared_folder = user_input if user_input else "./shared"

        self.shared_folder = shared_folder

        # Create folder if not exist
        Path(self.shared_folder).mkdir(parents=True, exist_ok=True)

        self.file_manager = FileManager(shared_dir = self.shared_folder)

        
        self.peer_manager = PeerManager(self)

        self.server: Optional[asyncio.AbstractServer] = None
        self.download_tasks = {}

    # ------------------------------------------------------------
    # 🟢 START NODE
    # ------------------------------------------------------------
    async def start(self):
        print(f"\n{'='*60}")
        print(f"🚀 Starting P2P File Sharing Node")
        print(f"{'='*60}")
        print(f"Peer ID      : {self.peer_id}")

<<<<<<< HEAD
        # Detect actual LAN IP for display
=======
        # Detect actual LAN IP for display (works even if hostname doesn't resolve)
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
<<<<<<< HEAD
        except Exception:
            lan_ip = "127.0.0.1"
        finally:
            s.close()
=======
            s.close()
        except Exception:
            lan_ip = "127.0.0.1"
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41

        print(f"Listening on : {lan_ip}:{self.port}")
        print(f"Shared Folder: {self.shared_folder}")
        print(f"{'='*60}\n")

<<<<<<< HEAD
        # Start the server
        self.server = await asyncio.start_server(self._handle_connection, self.host, self.port)
=======
        # Start server (binds to self.host, default 0.0.0.0 for LAN)
        self.server = await asyncio.start_server(self._handle_connection, self.host, self.port)

>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        print(f"✅ Server running on {lan_ip}:{self.port}")
        print(f"✅ Shared files: {len(self.file_manager.shared_files)}")
        print(f"\n✅ Node is ready! Listening on {lan_ip}:{self.port}\n")

<<<<<<< HEAD
        # Keep program alive with CLI menu
        await self.run_menu()

    # ------------------------------------------------------------
    # 🟣 HANDLE INCOMING CONNECTIONS
=======
        # Run the interactive CLI menu (keeps program alive)
        await self.run_menu()

    # ------------------------------------------------------------
    # 🟣 CONNECTION HANDLING (incoming)
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
    # ------------------------------------------------------------
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        print(f"\n[PEER] New connection from {addr}")

<<<<<<< HEAD
=======
        # Create protocol instance and wire it to the transport wrapper
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        protocol = P2PProtocol(self.peer_id, self.file_manager, self.peer_manager)
        transport = self._AsyncioTransport(reader, writer)
        protocol.connection_made(transport)

        # Read loop for this connection
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                protocol.data_received(data)
        except Exception as e:
            print(f"[ERROR] Connection error: {e}")
        finally:
            try:
                protocol.connection_lost(None)
            except Exception:
                pass
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _AsyncioTransport(self, reader, writer):
<<<<<<< HEAD
        """Wrapper to let P2PProtocol call write/get_extra_info/close."""
=======
        """A small transport wrapper so P2PProtocol can call write/get_extra_info/close"""
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        class Transport:
            def write(self_inner, data: bytes):
                try:
                    writer.write(data)
                except Exception:
                    pass

            def close(self_inner):
                try:
                    writer.close()
                except Exception:
                    pass

            def get_extra_info(self_inner, name: str):
                return writer.get_extra_info(name)

        return Transport()

    # ------------------------------------------------------------
<<<<<<< HEAD
    #  CONNECT TO ANOTHER PEER
    # ------------------------------------------------------------
    async def connect_to_peer(self, host: str, port: int, handshake_wait: float = 15.0):
        """Connects to another peer and waits for handshake."""
=======
    # 🟢 CONNECT TO ANOTHER PEER (outgoing)
    # ------------------------------------------------------------
    async def connect_to_peer(self, host: str, port: int, handshake_wait: float = 3.0):
        """
        Connect to another peer. After opening the TCP connection we:
         - create a P2PProtocol
         - call connection_made (which triggers a handshake from our side)
         - start a reader task to feed incoming data to the protocol
         - wait up to `handshake_wait` seconds for the protocol to report remote_peer_id
           and ensure peer_manager has the peer registered.
        Returns the protocol on success, or None on failure.
        """
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        try:
            print(f"[CONNECT] Connecting to {host}:{port} ...")
            reader, writer = await asyncio.open_connection(host, port)
        except Exception as e:
            print(f"[ERROR] Failed to connect to {host}:{port}: {e}")
            return None

<<<<<<< HEAD
=======
        # Create protocol and attach transport
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        protocol = P2PProtocol(self.peer_id, self.file_manager, self.peer_manager)
        transport = self._AsyncioTransport(reader, writer)
        protocol.connection_made(transport)

<<<<<<< HEAD
        asyncio.create_task(self._handle_peer_data(reader, protocol))

        waited = 0.0
        while waited < handshake_wait:
            remote_id = getattr(protocol, "remote_peer_id", None)
            if remote_id:
                try:
                    if self.peer_manager.get_peer(remote_id) is None:
                        self.peer_manager.add_peer(remote_id, protocol)
=======
        # Start background task to read from the socket and feed protocol.data_received
        asyncio.create_task(self._handle_peer_data(reader, protocol))

        # Wait briefly for the handshake to complete (protocol should set remote_peer_id)
        waited = 0.0
        interval = 0.1
        while waited < handshake_wait:
            remote_id = getattr(protocol, "remote_peer_id", None)
            if remote_id:
                # ensure peer_manager has it (some implementations add within protocol; do it here if not)
                try:
                    if self.peer_manager.get_peer(remote_id) is None:
                        # peer_manager.add_peer expects (peer_id, protocol) usually — adapt safely
                        try:
                            self.peer_manager.add_peer(remote_id, protocol)
                        except TypeError:
                            # fallback if signature differs
                            self.peer_manager.peers[remote_id] = protocol
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
                    print(f"✅ Connected to {host}:{port} as {remote_id}")
                except Exception:
                    print(f"✅ Connected to {host}:{port} (peer id: {remote_id})")
                return protocol

<<<<<<< HEAD
            await asyncio.sleep(0.1)
            waited += 0.1

        print(f"[WARN] Connected to socket at {host}:{port} but handshake didn't finish within {handshake_wait}s.")
        temp_key = f"{host}:{port}"
        try:
            if self.peer_manager.get_peer(temp_key) is None:
                self.peer_manager.add_peer(temp_key, protocol)
        except Exception:
            pass
        return protocol

    async def _handle_peer_data(self, reader: asyncio.StreamReader, protocol: P2PProtocol):
        """Background reader for outgoing peer connection."""
=======
            await asyncio.sleep(interval)
            waited += interval

        # If we get here, handshake didn't complete in time. Still return protocol (but warn).
        print(f"[WARN] Connected to socket at {host}:{port} but handshake didn't finish within {handshake_wait}s.")
        # Register protocol anyway under a temporary key (so it doesn't get lost) — optional
        temp_key = f"{host}:{port}"
        try:
            if self.peer_manager.get_peer(temp_key) is None:
                try:
                    self.peer_manager.add_peer(temp_key, protocol)
                except Exception:
                    self.peer_manager.peers[temp_key] = protocol
        except Exception:
            pass

        return protocol

    async def _handle_peer_data(self, reader: asyncio.StreamReader, protocol: P2PProtocol):
        """Background reader for an outgoing connection's incoming data"""
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                protocol.data_received(data)
        except Exception as e:
            print(f"[ERROR] Peer data error: {e}")
        finally:
            try:
                protocol.connection_lost(None)
            except Exception:
                pass

    # ------------------------------------------------------------
    # FILE SHARING
    # ------------------------------------------------------------
    def share_file(self, filepath: str):
        metadata = self.file_manager.add_shared_file(filepath)
        if metadata:
            from .protocol import FileMetadata
            metadata.pop("filepath", None)
            file_meta = FileMetadata(**metadata)

            # announce to connected peers
            for peer_id, protocol in self.peer_manager.peers.items():
                try:
                    protocol.announce_file(file_meta)
                except Exception:
                    pass

            print(f"✓ File shared and announced: {metadata['filename']}")
            print(f"   Hash: {metadata['file_hash']}")
            return metadata
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
                        try:
                            protocol.request_chunk(file_hash, chunk_index)
                            requested_count += 1
                        except Exception:
                            pass

            if requested_count == 0:
                print(f"[WAIT] No peers available for remaining chunks.")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(0.5)

    # ------------------------------------------------------------
    # 🟢 CLI MENU (single loop)
    # ------------------------------------------------------------
    async def run_menu(self):
        print(f"\n✅ Node is ready! Listening on {self.host}:{self.port}\n")
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

            choice = input("👉 Enter your choice (1–6): ").strip()

            if choice == "1":
                self.list_shared_files()
            elif choice == "2":
                self.list_available_files()
            elif choice == "3":
                host = input("Enter peer host: ").strip()
                try:
                    port = int(input("Enter peer port: ").strip())
                except ValueError:
                    print("[ERROR] Invalid port number.")
                    continue
                await self.connect_to_peer(host, port)
            elif choice == "4":
                file_hash = input("Enter file hash: ").strip()
                await self.download_file(file_hash)
            elif choice == "5":
                self.get_status()
            elif choice == "6":
                print("Exiting node...")
                if self.server:
                    self.server.close()
                    try:
                        await self.server.wait_closed()
                    except Exception:
                        pass
                break
            else:
                print("Invalid choice. Please enter a number 1–6.")

    # ------------------------------------------------------------
    # 🟢 UTILS / DISPLAY
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
                        available_files[file_hash] = {"metadata": metadata, "peer_count": 0}
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
        try:
            peer_count = self.peer_manager.get_peer_count()
        except Exception:
<<<<<<< HEAD
            peer_count = len(getattr(self.peer_manager, 'peers', {}))
=======
            # fallback: length of underlying dict if available
            peer_count = len(getattr(self.peer_manager, "peers", {}))
>>>>>>> 4cfd505efb7f490d2ceb0558cdee33d445bbeb41
        print(f"Peer ID: {self.peer_id}")
        print(f"Connected Peers: {peer_count}")
        print(f"Shared Files: {len(self.file_manager.shared_files)}")
        print(f"Active Downloads: {len(self.download_tasks)}")
        print(f"{'='*60}\n")
