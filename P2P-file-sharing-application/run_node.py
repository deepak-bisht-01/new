# run_node.py
import argparse
import asyncio
from src.p2p.node import P2PNode

async def main():
    parser = argparse.ArgumentParser(description="Run a P2P File Sharing Node")
    parser.add_argument("--peer-id", required=True, help="Unique ID for this peer")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (use LAN IP for multi-device)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--share", default="./shared", help="Directory to share files from")
    parser.add_argument("--connect", help="Optional peer to connect to (host:port)")
    args = parser.parse_args()

    node = P2PNode(peer_id=args.peer_id, host=args.host, port=args.port, shared_folder=args.share)

    await node.start()

    # If connect argument provided, connect to an existing peer
    if args.connect:
        host, port = args.connect.split(":")
        await node.connect_to_peer(host, int(port))

    print("\n🌐 Node is running. Type commands below (list, peers, exit)\n")

    while True:
        cmd = input(f"[{args.peer_id}]> ").strip().lower()
        if cmd == "exit":
            print("🛑 Shutting down node...")
            await node.stop()
            break
        elif cmd == "list":
            files = node.file_manager.list_shared_files()
            if not files:
                print("No files shared.")
            else:
                print("\n📂 Shared Files:")
                for f in files:
                    print(f" - {f['filename']} ({f['size']} bytes)")
        elif cmd == "peers":
            print("\n🤝 Connected Peers:")
            for p in node.peer_manager.peers.values():
                print(f" - {p.host}:{p.port}")
        else:
            print("❓ Commands: list | peers | exit")

if __name__ == "__main__":
    asyncio.run(main())
