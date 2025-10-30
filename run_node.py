import asyncio
import argparse
from src.p2p.node import P2PNode

async def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing Node")
    parser.add_argument("--peer-id", required=True, help="Unique ID of this peer")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP address")
    parser.add_argument("--port", type=int, required=True, help="Port number for this peer")
    parser.add_argument("--share", default="./shared", help="Folder to share files from")
    parser.add_argument("--connect", help="Optional: connect to another peer (host:port)")
    args = parser.parse_args()

    node = P2PNode(peer_id=args.peer_id, host=args.host, port=args.port)

    # Start server in background
    asyncio.create_task(node.start())

    # Wait for the server to initialize
    await asyncio.sleep(1)

    # Optional auto-connect
    if args.connect:
        try:
            host, port = args.connect.split(":")
            await node.connect_to_peer(host, int(port))
        except Exception as e:
            print(f"[ERROR] Could not connect to peer: {e}")

    # CLI Menu
    while True:
        print("\n" + "=" * 60)
        print(f"📡 P2P Node Menu ({args.peer_id})")
        print("=" * 60)
        print("1. List my shared files")
        print("2. List available files from peers")
        print("3. Connect to another peer")
        print("4. Download a file by hash")
        print("5. Show node status")
        print("6. Exit")
        print("=" * 60)

        choice = input("Enter your choice (1–6): ").strip()

        if choice == "1":
            node.list_shared_files()

        elif choice == "2":
            node.list_available_files()

        elif choice == "3":
            host = input("Enter peer host: ").strip()
            port = int(input("Enter peer port: ").strip())
            await node.connect_to_peer(host, port)

        elif choice == "4":
            file_hash = input("Enter file hash to download: ").strip()
            await node.download_file(file_hash)

        elif choice == "5":
            node.get_status()

        elif choice == "6":
            print("👋 Exiting...")
            break

        else:
            print("❌ Invalid choice. Please enter a number from 1 to 6.")

if __name__ == "__main__":
    asyncio.run(main())
