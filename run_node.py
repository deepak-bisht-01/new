import argparse
import asyncio
import socket
from src.p2p.node import P2PNode
  


# ------------------------------------------------------------
# 🧩 Utility: Detect actual LAN IP address
# ------------------------------------------------------------
def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ------------------------------------------------------------
# 🚀 Entry Point
# ------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing Node")
    parser.add_argument("--peer-id", required=True, help="Unique ID for this peer")
    parser.add_argument("--port", type=int, default=6000, help="Port to listen on")
    parser.add_argument("--share", default="./shared", help="Folder to share files from")
    args = parser.parse_args()

    # Detect LAN IP dynamically
    host = get_lan_ip()

    print(f"\nDetected LAN IP: {host}")
    print(f"Peer ID        : {args.peer_id}")
    print(f"Port           : {args.port}")
    print(f"Shared Folder  : {args.share}")

    # Create node
    node = P2PNode(
        peer_id=args.peer_id,
        host=host,
        port=args.port,
        shared_folder=args.share
    )

    # Start node
    try:
        await node.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
        if node.server:
            node.server.close()
            await node.server.wait_closed()
        print("✅ Node stopped.")


# ------------------------------------------------------------
# 🏁 Program Launcher
# ------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
