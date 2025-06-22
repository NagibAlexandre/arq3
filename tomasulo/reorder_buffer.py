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
    flushed: bool = False  # Nova flag

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
    
    def add_entry(self, instruction: Instruction, destination: Optional[str] = None, 
              speculative: bool = False) -> int:
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
        if entry is None or not entry.ready or entry.flushed:
            return None
            
        # Não comita instruções especulativas que foram mispredicted
        if entry.branch_mispredicted:
            # Remove entrada sem commitar
            self.entries[self.head] = None
            self.head = (self.head + 1) % self.size
            self.count -= 1
            return None
        
        entry.state = "COMMIT"
        self.entries[self.head] = None
        self.head = (self.head + 1) % self.size
        self.count -= 1
        return entry

    def update_entry(self, index: int, value: int):
        if 0 <= index < self.size and self.entries[index] is not None:
            entry = self.entries[index]
            if not entry.flushed:  # Só atualiza se não foi flushed
                entry.value = value
                entry.ready = True
                entry.state = "WRITE_RESULT"

    def mark_mispredicted(self, index: int):
        if 0 <= index < self.size and self.entries[index] is not None:
            self.entries[index].branch_mispredicted = True

    def flush_entry(self, index: int):
        """Marca uma entrada como flushed"""
        if 0 <= index < self.size and self.entries[index] is not None:
            self.entries[index].flushed = True
            self.entries[index].branch_mispredicted = True

    def flush_after(self, index: int):
        """Flush todas as instruções após um índice específico"""
        current = (index + 1) % self.size
        flushed_count = 0
        
        while current != self.tail:
            if self.entries[current] is not None:
                self.entries[current].flushed = True
                self.entries[current].branch_mispredicted = True
                flushed_count += 1
            current = (current + 1) % self.size
            
        return flushed_count

    def cleanup_flushed(self):
        """Remove entradas flushed do buffer"""
        # Remove entradas flushed a partir do head
        while not self.is_empty():
            entry = self.entries[self.head]
            if entry is None or entry.flushed:
                self.entries[self.head] = None
                self.head = (self.head + 1) % self.size
                self.count -= 1
            else:
                break

    def get_entry(self, index: int) -> Optional[ROBEntry]:
        if 0 <= index < self.size:
            return self.entries[index]
        return None

    def get_all_entries(self) -> List[Optional[ROBEntry]]:
        return self.entries

    def get_speculative_count(self) -> int:
        """Retorna número de instruções especulativas no buffer"""
        count = 0
        for entry in self.entries:
            if entry and entry.speculative and not entry.flushed:
                count += 1
        return count