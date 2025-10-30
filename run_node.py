import asyncio
import argparse
from src.p2p.node import P2PNode

async def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing Node")
    
    # Defaults to '0.0.0.0' to be accessible on the LAN
    parser.add_argument("--host", default="0.0.0.0", help="Host IP address to listen on")
    
    parser.add_argument("--peer-id", required=True, help="Unique ID of this peer")
    parser.add_argument("--port", type=int, required=True, help="Port number for this peer")
    parser.add_argument("--share", default="./shared", help="Folder to share files from")
    parser.add_argument("--connect", help="Optional: connect to another peer on start (host:port)")
    
    args = parser.parse_args()

    # Create the node instance
    node = P2PNode(
        peer_id=args.peer_id,
        host=args.host,
        port=args.port,
        shared_folder=args.share
    )

    try:
        # Start the server as a background task
        server_task = asyncio.create_task(node.start_server())
        await asyncio.sleep(0.1) # Give server a moment to initialize
        
        # Auto-connect if the --connect argument is used
        if args.connect:
            host, port_str = args.connect.split(":")
            print(f"[AUTO-CONNECT] Attempting to connect to {host}:{port_str}...")
            await node.connect_to_peer(host, int(port_str))
            
        # Run the main user menu (this will block until the user exits)
        await node.run_menu()

    finally:
        # Cleanly shut down the server when the menu exits
        if node.server and not node.server.is_serving():
            node.server.close()
            await node.server.wait_closed()
        print("[MAIN] Node has been shut down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting application.")