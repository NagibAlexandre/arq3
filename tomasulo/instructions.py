from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class InstructionType(Enum):
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    LD = "LD"  # Load
    ST = "ST"  # Store
    BEQ = "BEQ"  # Branch if equal
    BNE = "BNE"  # Branch if not equal
    J = "J"    # Jump

@dataclass
class Instruction:
    type: InstructionType
    dest: Optional[str] = None  # Registrador de destino
    src1: Optional[str] = None  # Primeiro registrador fonte
    src2: Optional[str] = None  # Segundo registrador fonte
    immediate: Optional[int] = None  # Valor imediato
    address: Optional[int] = None  # Endereço para load/store
    latency: int = 1  # Latência da instrução em ciclos
    
    def __str__(self) -> str:
        if self.type in [InstructionType.ADD, InstructionType.SUB, InstructionType.MUL, InstructionType.DIV]:
            return f"{self.type.value} {self.dest}, {self.src1}, {self.src2}"
        elif self.type in [InstructionType.LD, InstructionType.ST]:
            return f"{self.type.value} {self.dest}, {self.immediate}({self.src1})"
        elif self.type in [InstructionType.BEQ, InstructionType.BNE]:
            return f"{self.type.value} {self.src1}, {self.src2}, {self.immediate}"
        elif self.type == InstructionType.J:
            return f"{self.type.value} {self.immediate}"
        return ""

class InstructionFactory:
    @staticmethod
    def create_instruction(instruction_str: str, latencies: dict = None) -> Instruction:
        parts = instruction_str.strip().split()
        op = parts[0].upper()
        latencies = latencies or {}
        
        if op in ["ADD", "SUB", "MUL", "DIV"]:
            latency = latencies.get(op, 2 if op in ["MUL", "DIV"] else 1)
            return Instruction(
                type=InstructionType[op],
                dest=parts[1].strip(','),
                src1=parts[2].strip(','),
                src2=parts[3],
                latency=latency
            )
        elif op in ["LD", "ST"]:
            # Formato: LD/ST rd, offset(rs)
            dest = parts[1].strip(',')
            offset_rs = parts[2].strip('()').split('(')
            latency = latencies.get(op, 2)
            return Instruction(
                type=InstructionType[op],
                dest=dest,
                src1=offset_rs[1],
                immediate=int(offset_rs[0]),
                latency=latency
            )
        elif op in ["BEQ", "BNE"]:
            latency = latencies.get(op, 1)
            return Instruction(
                type=InstructionType[op],
                src1=parts[1].strip(','),
                src2=parts[2].strip(','),
                immediate=int(parts[3]),
                latency=latency
            )
        elif op == "J":
            latency = latencies.get(op, 1)
            return Instruction(
                type=InstructionType.J,
                immediate=int(parts[1]),
                latency=latency
            )
        raise ValueError(f"Instrução não reconhecida: {instruction_str}") 