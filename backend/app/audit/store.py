"""Tamper-evident hash-chained audit log for AgentVault.

Implements sequential SHA-256 hash chaining over all critical lifecycle events:
- Mandate creation and revocation
- Requirement recording
- Optimizer execution
- Verifier approval and rejection
- Contract transaction execution
- Administrative actions (pause, unpause, kill switch)
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple


class AuditLog:
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self._genesis_hash = "0" * 64
        # Add genesis entry
        self._record_raw("GENESIS", {"system": "AgentVault", "version": "1.0.0"}, prev_hash=self._genesis_hash)

    def _compute_hash(self, index: int, timestamp: float, event_type: str, prev_hash: str, payload: Dict[str, Any]) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        blob = f"{index}|{timestamp}|{event_type}|{prev_hash}|{canonical_payload}".encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _record_raw(self, event_type: str, payload: Dict[str, Any], prev_hash: Optional[str] = None) -> Dict[str, Any]:
        idx = len(self.entries)
        now = time.time()
        p_hash = prev_hash if prev_hash is not None else self.entries[-1]["hash"]
        entry_hash = self._compute_hash(idx, now, event_type, p_hash, payload)
        
        entry = {
            "index": idx,
            "timestamp": now,
            "eventType": event_type,
            "prevHash": p_hash,
            "hash": entry_hash,
            "payload": payload,
        }
        self.entries.append(entry)
        return entry

    def record_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Record a new event with automatic hash chaining."""
        return self._record_raw(event_type, payload)

    def get_entries(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve recent entries."""
        return list(reversed(self.entries[offset : offset + limit]))

    def get_entry_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None

    def verify_chain(self) -> Tuple[bool, Optional[str], Optional[int]]:
        """Recompute every hash link and verify unbroken continuity.
        
        Returns (is_valid, error_detail, broken_index).
        """
        for i, entry in enumerate(self.entries):
            expected_prev = self._genesis_hash if i == 0 else self.entries[i - 1]["hash"]
            if entry["prevHash"] != expected_prev:
                return False, f"Broken link at index {i}: prevHash mismatch", i
            
            recomputed = self._compute_hash(
                entry["index"],
                entry["timestamp"],
                entry["eventType"],
                entry["prevHash"],
                entry["payload"]
            )
            if entry["hash"] != recomputed:
                return False, f"Tampered entry at index {i}: stored hash {entry['hash']} != recomputed {recomputed}", i
                
        return True, "Audit chain integrity verified. All links valid.", None

    def tamper_for_testing(self, index: int, new_payload: Dict[str, Any]):
        """Deliberately modify a payload without recomputing hash to test tamper detection."""
        if 0 <= index < len(self.entries):
            self.entries[index]["payload"] = new_payload


# Singleton audit log instance
global_audit_log = AuditLog()
