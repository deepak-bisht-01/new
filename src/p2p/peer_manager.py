
import asyncio
from typing import Dict, Set, List, Optional
from collections import defaultdict

class PeerManager:
    """
    Manages connected peers and their available files/chunks
    Similar to BitTorrent's peer management
    """
    
    def __init__(self, node=None):
        self.node = node
        self.peers = {}  # peer_id -> protocol instance
        
        # file_hash -> set of peer_ids that have it
        self.file_availability: Dict[str, Set[str]] = defaultdict(set)
        
        # (file_hash, chunk_index) -> set of peer_ids
        self.chunk_availability: Dict[tuple, Set[str]] = defaultdict(set)
        
        # peer_id -> set of file_hashes
        self.peer_files: Dict[str, Set[str]] = defaultdict(set)
    
    def add_peer(self, peer_id: str, protocol):
        """Register a connected peer"""
        self.peers[peer_id] = protocol
        print(f"[PEER] Added peer: {peer_id}")
    
    def remove_peer(self, peer_id: str):
        """Remove a disconnected peer"""
        if peer_id in self.peers:
            del self.peers[peer_id]
            
            # Clean up file availability
            for file_hash in self.peer_files[peer_id]:
                self.file_availability[file_hash].discard(peer_id)
            
            del self.peer_files[peer_id]
            
            print(f"[PEER] Removed peer: {peer_id}")
    
    def get_peer(self, peer_id: str):
        """Get protocol instance for a peer"""
        return self.peers.get(peer_id)
    
    def get_all_peers(self) -> List[str]:
        """Get list of all connected peer IDs"""
        return list(self.peers.keys())
    
    def add_peer_file(self, peer_id: str, file_hash: str):
        """Record that a peer has a complete file"""
        self.peer_files[peer_id].add(file_hash)
        self.file_availability[file_hash].add(peer_id)
    
    def add_peer_chunk(self, peer_id: str, file_hash: str, chunk_index: int):
        """Record that a peer has a specific chunk"""
        self.chunk_availability[(file_hash, chunk_index)].add(peer_id)
    
    def get_peers_with_file(self, file_hash: str) -> List[str]:
        """Get list of peers that have a complete file"""
        return list(self.file_availability.get(file_hash, set()))
    
    def get_peers_with_chunk(self, file_hash: str, chunk_index: int) -> List[str]:
        """Get list of peers that have a specific chunk"""
        return list(self.chunk_availability.get((file_hash, chunk_index), set()))
    
    def get_peer_files(self, peer_id: str) -> Set[str]:
        """Get all files available from a peer"""
        return self.peer_files.get(peer_id, set())
    
    def get_best_peer_for_chunk(self, file_hash: str, chunk_index: int) -> Optional[str]:
        """
        Get the best peer to request a chunk from
        Could implement load balancing, fastest peer selection, etc.
        """
        peers = self.get_peers_with_chunk(file_hash, chunk_index)
        if not peers:
            # Try peers with complete file
            peers = self.get_peers_with_file(file_hash)
        
        if peers:
            # Simple strategy: return first available peer
            # Could be improved with peer performance tracking
            return peers[0]
        
        return None
    
    def broadcast_to_all(self, message_type, payload):
        """Send a message to all connected peers"""
        for peer_id, protocol in self.peers.items():
            try:
                protocol.send_message(message_type, payload)
            except Exception as e:
                print(f"[ERROR] Failed to send to {peer_id}: {e}")
    
    def get_peer_count(self) -> int:
        """Get number of connected peers"""
        return len(self.peers)
    
    def get_file_availability_info(self, file_hash: str) -> dict:
        """Get detailed availability info for a file"""
        peers_with_file = self.get_peers_with_file(file_hash)
        
        # Count chunk availability
        chunk_peer_counts = defaultdict(int)
        for (fh, chunk_idx), peer_set in self.chunk_availability.items():
            if fh == file_hash:
                chunk_peer_counts[chunk_idx] = len(peer_set)
        
        return {
            "peers_with_complete_file": len(peers_with_file),
            "chunk_availability": dict(chunk_peer_counts),
            "total_peer_count": self.get_peer_count()
        }