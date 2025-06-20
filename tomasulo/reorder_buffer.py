from dataclasses import dataclass
from typing import Optional, List
from .instructions import Instruction

@dataclass
class ROBEntry:
    instruction: Instruction
    state: str = "ISSUE"
    destination: Optional[str] = None
    value: Optional[int] = None
    ready: bool = False
    branch_mispredicted: bool = False
    speculative: bool = False  

class ReorderBuffer:
    def __init__(self, size: int = 8):
        self.size = size
        self.entries: List[Optional[ROBEntry]] = [None] * size
        self.head = 0
        self.tail = 0
        self.count = 0

    def is_full(self) -> bool:
        return self.count == self.size

    def is_empty(self) -> bool:
        return self.count == 0

    def add_entry(self, instruction: Instruction, destination: Optional[str] = None, speculative: bool = False) -> int:
        if self.is_full():
            raise Exception("Buffer de reordenamento cheio")
        entry = ROBEntry(
            instruction=instruction,
            destination=destination,
            speculative=speculative
        )
        self.entries[self.tail] = entry
        index = self.tail
        self.tail = (self.tail + 1) % self.size
        self.count += 1
        return index

    def commit(self) -> Optional[ROBEntry]:
        if self.is_empty():
            return None
        entry = self.entries[self.head]
        if entry is None or not entry.ready:
            return None
        self.entries[self.head] = None
        self.head = (self.head + 1) % self.size
        self.count -= 1
        return entry

    def update_entry(self, index: int, value: int):
        if 0 <= index < self.size and self.entries[index] is not None:
            self.entries[index].value = value
            self.entries[index].ready = True
            self.entries[index].state = "WRITE_RESULT"

    def mark_mispredicted(self, index: int):
        if 0 <= index < self.size and self.entries[index] is not None:
            self.entries[index].branch_mispredicted = True

    def flush_after(self, index: int):
        current = (index + 1) % self.size
        while current != self.tail:
            self.entries[current] = None
            current = (current + 1) % self.size
        self.tail = (index + 1) % self.size
        self.count = (self.tail - self.head) % self.size

    def get_entry(self, index: int) -> Optional[ROBEntry]:
        if 0 <= index < self.size:
            return self.entries[index]
        return None

    def get_all_entries(self) -> List[Optional[ROBEntry]]:
        return self.entries