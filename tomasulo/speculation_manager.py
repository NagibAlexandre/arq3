from typing import List, Set, Optional, Dict
from dataclasses import dataclass
from .instructions import Instruction, InstructionType

@dataclass
class SpeculativeInstruction:
    """Instrução especulativa"""
    instruction: Instruction
    pc: int
    rob_index: int
    branch_pc: int  # PC do desvio que causou a especulação
    speculation_level: int = 1  # Nível de especulação (podem ser aninhadas)

class SpeculationManager:
    """Gerenciador de execução especulativa"""

    def __init__(self):
        self.speculative_instructions: List[SpeculativeInstruction] = []
        self.branch_stack: List[int] = []  # Stack de desvios especulativos
        self.speculation_level = 0
        self.recovery_pc: Optional[int] = None
        
        # Estatísticas
        self.stats = {
            'speculative_instructions_issued': 0,
            'speculative_instructions_flushed': 0,
            'misprediction_recoveries': 0,
            'max_speculation_level': 0
        }

    def start_speculation(self, branch_pc: int, predicted_target: int) -> int:
        """Inicia especulação a partir de um desvio"""
        self.speculation_level += 1
        self.branch_stack.append(branch_pc)
        
        if self.speculation_level > self.stats['max_speculation_level']:
            self.stats['max_speculation_level'] = self.speculation_level
        
        return predicted_target

    def add_speculative_instruction(self, instruction: Instruction, pc: int, 
                                rob_index: int) -> bool:
        """Adiciona uma instrução especulativa"""
        if self.speculation_level == 0:
            return False
        
        branch_pc = self.branch_stack[-1] if self.branch_stack else -1
        spec_instr = SpeculativeInstruction(
            instruction=instruction,
            pc=pc,
            rob_index=rob_index,
            branch_pc=branch_pc,
            speculation_level=self.speculation_level
        )
        
        self.speculative_instructions.append(spec_instr)
        self.stats['speculative_instructions_issued'] += 1
        return True

    def resolve_branch(self, branch_pc: int, actual_taken: bool, 
              actual_target: int, predicted_taken: bool, 
              predicted_target: int) -> bool:
        """Resolve um desvio e verifica se houve misprediction"""

        mispredicted = (actual_taken != predicted_taken or 
                    (actual_taken and actual_target != predicted_target))

        if mispredicted:
            self.stats['misprediction_recoveries'] += 1
            self.recovery_pc = actual_target
            return True
        else:
            # Predição correta - remove do stack se for o último
            if self.branch_stack and self.branch_stack[-1] == branch_pc:
                self.branch_stack.pop()
                self.speculation_level = max(0, self.speculation_level - 1)
            return False

    def flush_speculative_instructions(self, branch_pc: int) -> List[int]:
        """Flush instruções especulativas após misprediction"""
        flushed_rob_indices = []

        # Marca instruções para flush (todas especulativas após o branch)
        instructions_to_remove = []
        for i, spec_instr in enumerate(self.speculative_instructions):
            # Flush instruções especulativas que vieram após o branch
            if spec_instr.pc > branch_pc:
                flushed_rob_indices.append(spec_instr.rob_index)
                instructions_to_remove.append(i)
                self.stats['speculative_instructions_flushed'] += 1

        # Remove instruções flushed
        for i in reversed(instructions_to_remove):
            del self.speculative_instructions[i]

        # Reset do estado especulativo
        if self.branch_stack and self.branch_stack[-1] == branch_pc:
            self.branch_stack.pop()
            self.speculation_level = max(0, self.speculation_level - 1)

        return flushed_rob_indices

    def get_recovery_pc(self) -> Optional[int]:
        """Retorna PC de recuperação após misprediction"""
        pc = self.recovery_pc
        self.recovery_pc = None
        return pc

    def is_speculative(self) -> bool:
        """Verifica se estamos em modo especulativo"""
        return self.speculation_level > 0

    def get_speculation_level(self) -> int:
        """Retorna nível atual de especulação"""
        return self.speculation_level

    def get_stats(self) -> Dict:
        """Retorna estatísticas de especulação"""
        return self.stats.copy()