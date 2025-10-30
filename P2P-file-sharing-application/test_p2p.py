#!/usr/bin/env python3
"""
Quick test script for P2P file sharing
Creates a test file and demonstrates file sharing between two peers
"""

import asyncio
import sys
import os
from pathlib import Path


# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from p2p.node import P2PNode

async def create_test_file(filepath: str, size_mb: int = 1):
    """Create a test file with random data"""
    print(f"Creating test file: {filepath} ({size_mb}MB)")
    
    # Create shared directory if it doesn't exist
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate random data
    import random
    data = bytes(random.getrandbits(8) for _ in range(size_mb * 1024 * 1024))
    
    with open(filepath, 'wb') as f:
        f.write(data)
    
    print(f"✓ Test file created: {filepath}")

async def test_two_peers():
    """Test file sharing between two peers"""
    print("\n" + "="*70)
    print("🧪 P2P File Sharing Test")
    print("="*70 + "\n")
    
    # Create test file
    test_file = "./shared/test_file.dat"
    await create_test_file(test_file, size_mb=1)
    
    # Create two peers
    print("\n📍 Starting Peer 1 (Seeder)...")
    peer1 = P2PNode("peer1-test-node", "127.0.0.1", 6001)
    
    print("📍 Starting Peer 2 (Leecher)...")
    peer2 = P2PNode("peer2-test-node", "127.0.0.1", 6002)
    
    # Start both servers
    server1_task = asyncio.create_task(peer1.start())
    await asyncio.sleep(1)
    
    server2_task = asyncio.create_task(peer2.start())
    await asyncio.sleep(1)
    
    try:
        # Peer 1 shares the file
        print("\n📤 Peer 1: Sharing test file...")
        metadata = peer1.share_file(test_file)
        
        if not metadata:
            print("❌ Failed to share file")
            return
        
        file_hash = metadata['file_hash']
        print(f"✓ File shared with hash: {file_hash[:32]}...")
        
        # Peer 2 connects to Peer 1
        print("\n🔗 Peer 2: Connecting to Peer 1...")
        await peer2.connect_to_peer("127.0.0.1", 6001)
        await asyncio.sleep(2)  # Wait for handshake
        
        # Check if Peer 2 sees the file
        print("\n📋 Peer 2: Checking available files...")
        peer2.list_available_files()
        
        # Peer 2 downloads the file
        print(f"\n📥 Peer 2: Starting download...")
        await peer2.download_file(file_hash)
        
        # Verify download
        downloaded_file = Path(f"./downloads/test_file.dat")
        if downloaded_file.exists():
            print(f"\n✅ SUCCESS! File downloaded to: {downloaded_file}")
            
            # Compare file sizes
            original_size = Path(test_file).stat().st_size
            downloaded_size = downloaded_file.stat().st_size
            
            if original_size == downloaded_size:
                print(f"✓ File size matches: {original_size:,} bytes")
            else:
                print(f"⚠️  Size mismatch! Original: {original_size}, Downloaded: {downloaded_size}")
        else:
            print("\n❌ Download failed - file not found")
        
        # Show final status
        print("\n" + "="*70)
        print("📊 Final Status")
        print("="*70)
        peer1.get_status()
        peer2.get_status()
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        server1_task.cancel()
        server2_task.cancel()
        
        try:
            await asyncio.gather(server1_task, server2_task, return_exceptions=True)
        except:
            pass

async def interactive_demo():
    """Interactive demo mode"""
    print("\n" + "="*70)
    print("🎮 P2P Interactive Demo")
    print("="*70)
    print("\nThis will start a single peer that you can interact with.")
    print("You can start another instance in a different terminal to test P2P.\n")
    
    port = int(input("Enter port (default 5001): ") or "5001")
    
    peer = P2PNode(f"demo-peer-{port}", "0.0.0.0", port)
    
    print(f"\n🚀 Starting peer on port {port}...")
    print(f"To connect from another peer, use: connect localhost {port}\n")
    
    server_task = asyncio.create_task(peer.start())
    
    try:
        print("\nCommands:")
        print("  share <file>     - Share a file")
        print("  list             - List shared files")
        print("  status           - Show status")
        print("  quit             - Exit\n")
        
        while True:
            command = await asyncio.get_event_loop().run_in_executor(
                None, input, "demo> "
            )
            
            cmd_parts = command.strip().split(maxsplit=1)
            if not cmd_parts:
                continue
            
            cmd = cmd_parts[0].lower()
            
            if cmd == "quit":
                break
            elif cmd == "share" and len(cmd_parts) > 1:
                peer.share_file(cmd_parts[1])
            elif cmd == "list":
                peer.list_shared_files()
            elif cmd == "status":
                peer.get_status()
            else:
                print("Unknown command")
    
    except KeyboardInterrupt:
        print("\n\nExiting...")
    finally:
        server_task.cancel()

def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "demo":
            asyncio.run(interactive_demo())
        elif sys.argv[1] == "test":
            asyncio.run(test_two_peers())
        else:
            print("Usage: python test_p2p.py [test|demo]")
    else:
        # Default to test mode
        asyncio.run(test_two_peers())

if __name__ == "__main__":
    main()