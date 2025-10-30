"""Interactive CLI for P2P file sharing application"""
import asyncio
import click
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from p2p.node import P2PNode

class P2PClient:
    """Interactive P2P file sharing client"""
    
    def __init__(self, node: P2PNode):
        self.node = node
        self.running = True
    
    async def run_interactive(self):
        """Run interactive command loop"""
        print("\n" + "="*60)
        print("🎯 P2P File Sharing - Interactive Mode")
        print("="*60)
        print("\nType 'help' for available commands\n")
        
        while self.running:
            try:
                command = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    input, 
                    "p2p> "
                )
                
                await self.handle_command(command.strip())
                
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                self.running = False
            except Exception as e:
                print(f"[ERROR] {e}")
    
    async def handle_command(self, command: str):
        """Handle user commands"""
        if not command:
            return
        
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        commands = {
            "help": self.cmd_help,
            "share": self.cmd_share,
            "list": self.cmd_list,
            "available": self.cmd_available,
            "download": self.cmd_download,
            "connect": self.cmd_connect,
            "status": self.cmd_status,
            "peers": self.cmd_peers,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
        }
        
        handler = commands.get(cmd)
        if handler:
            await handler(args)
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")
    
    async def cmd_help(self, args: str):
        """Show help message"""
        print("""
Available Commands:
-------------------
  share <filepath>          Share a file with the network
  list                      List your shared files
  available                 List files available from peers
  download <file_hash>      Download a file
  connect <host> <port>     Connect to a peer
  status                    Show node status
  peers                     List connected peers
  exit/quit                 Exit the application

Examples:
---------
  share /path/to/file.txt
  connect 192.168.1.100 5002
  download a1b2c3d4...
        """)
    
    async def cmd_share(self, args: str):
        """Share a file"""
        if not args:
            print("Usage: share <filepath>")
            return
        
        filepath = args.strip()
        if not Path(filepath).exists():
            print(f"Error: File not found: {filepath}")
            return
        
        metadata = self.node.share_file(filepath)
        if metadata:
            print(f"\n✓ File shared successfully!")
            print(f"  Filename: {metadata['filename']}")
            print(f"  Hash: {metadata['file_hash']}")
            print(f"  Size: {metadata['file_size']:,} bytes")
    
    async def cmd_list(self, args: str):
        """List shared files"""
        self.node.list_shared_files()
    
    async def cmd_available(self, args: str):
        """List available files from peers"""
        self.node.list_available_files()
    
    async def cmd_download(self, args: str):
        """Download a file"""
        if not args:
            print("Usage: download <file_hash>")
            return
        
        file_hash = args.strip()
        await self.node.download_file(file_hash)
    
    async def cmd_connect(self, args: str):
        """Connect to a peer"""
        parts = args.split()
        if len(parts) != 2:
            print("Usage: connect <host> <port>")
            return
        
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            print("Error: Port must be a number")
            return
        
        await self.node.connect_to_peer(host, port)
    
    async def cmd_status(self, args: str):
        """Show node status"""
        self.node.get_status()
    
    async def cmd_peers(self, args: str):
        """List connected peers"""
        peers = self.node.peer_manager.get_all_peers()
        
        print(f"\n{'='*60}")
        print(f"👥 Connected Peers ({len(peers)})")
        print(f"{'='*60}")
        
        if not peers:
            print("No peers connected.")
        else:
            for i, peer_id in enumerate(peers, 1):
                files = self.node.peer_manager.get_peer_files(peer_id)
                print(f"\n{i}. {peer_id[:32]}...")
                print(f"   Files: {len(files)}")
        
        print(f"\n{'='*60}\n")
    
    async def cmd_exit(self, args: str):
        """Exit the application"""
        print("\nGoodbye! 👋")
        self.running = False


def load_peer_identity(identity_file: str = "peer_identity.json") -> str:
    """Load peer ID from identity file"""
    try:
        with open(identity_file, 'r') as f:
            identity = json.load(f)
            return identity['peer_id']
    except FileNotFoundError:
        print(f"[WARNING] Identity file not found: {identity_file}")
        # Generate a simple peer ID
        import uuid
        peer_id = str(uuid.uuid4())
        print(f"[INFO] Generated new peer ID: {peer_id}")
        return peer_id


@click.command()
@click.option('--port', default=5001, help='Port to listen on')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--identity', default='peer_identity.json', help='Path to identity file')
@click.option('--connect-to', multiple=True, help='Peers to connect to (format: host:port)')
def main(port: int, host: str, identity: str, connect_to: tuple):
    """
    P2P File Sharing Application
    
    A BitTorrent-like file sharing system with:
    - Decentralized peer-to-peer file transfer
    - Chunk-based downloads
    - Multiple simultaneous downloads
    - File integrity verification
    """
    
    # Load peer identity
    peer_id = load_peer_identity(identity)
    
    # Create P2P node
    node = P2PNode(peer_id, host, port)
    
    # Create client
    client = P2PClient(node)
    
    async def run():
        # Start node server
        server_task = asyncio.create_task(node.start())
        
        # Wait a bit for server to start
        await asyncio.sleep(1)
        
        # Connect to initial peers
        for peer_addr in connect_to:
            try:
                peer_host, peer_port = peer_addr.split(':')
                await node.connect_to_peer(peer_host, int(peer_port))
            except Exception as e:
                print(f"[ERROR] Failed to connect to {peer_addr}: {e}")
        
        # Run interactive client
        await client.run_interactive()
        
        # Cancel server
        server_task.cancel()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n\nShutdown complete.")


if __name__ == '__main__':
    main()