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
    speculation_level: int = 1  # Nível de especulação

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
        print(f"=== INICIANDO ESPECULAÇÃO ===")
        print(f"Branch PC: {branch_pc}, Target predito: {predicted_target}")
        print(f"Nível anterior: {self.speculation_level}")
        
        self.speculation_level += 1
        self.branch_stack.append(branch_pc)
        
        print(f"Novo nível de especulação: {self.speculation_level}")
        print(f"Branch stack: {self.branch_stack}")
        print(f"Modo especulativo ATIVO - próximas instruções serão especulativas")
        
        if self.speculation_level > self.stats['max_speculation_level']:
            self.stats['max_speculation_level'] = self.speculation_level
        
        return predicted_target

    def add_speculative_instruction(self, instruction: Instruction, pc: int, rob_index: int) -> bool:
        """Adiciona uma instrução especulativa"""
        # CORREÇÃO: Permite adicionar mesmo sem especulação ativa
        if self.speculation_level == 0:
            print(f"AVISO: Adicionando instrução especulativa PC {pc} sem especulação ativa")
            branch_pc = -1  # Indica que não há branch específico
            spec_level = 1  # Nível mínimo
        else:
            branch_pc = self.branch_stack[-1] if self.branch_stack else -1
            spec_level = self.speculation_level

        spec_instr = SpeculativeInstruction(
            instruction=instruction,
            pc=pc,
            rob_index=rob_index,
            branch_pc=branch_pc,
            speculation_level=spec_level
        )

        self.speculative_instructions.append(spec_instr)
        self.stats['speculative_instructions_issued'] += 1
        
        print(f">>> Instrução especulativa adicionada: PC {pc}, ROB {rob_index}, Branch PC {branch_pc}")
        print(f">>> Total de instruções especulativas: {len(self.speculative_instructions)}")
        
        return True

    def resolve_branch(self, branch_pc: int, actual_taken: bool, actual_target: int, 
                    predicted_taken: bool, predicted_target: int) -> bool:
        """Resolve um desvio e verifica se houve misprediction"""
        
        print(f"=== RESOLVENDO BRANCH PC {branch_pc} ===")
        print(f"Real: tomado={actual_taken}, target={actual_target}")
        print(f"Predito: tomado={predicted_taken}, target={predicted_target}")
        
        # Verificação de misprediction
        mispredicted = False
        
        if actual_taken != predicted_taken:
            mispredicted = True
            print("Misprediction: direção diferente")
        elif actual_taken and actual_target != predicted_target:
            mispredicted = True
            print("Misprediction: target diferente")
        
        if mispredicted:
            self.stats['misprediction_recoveries'] += 1
            self.recovery_pc = actual_target
            print(f"*** MISPREDICTION DETECTADA ***")
            return True
        else:
            # Predição correta - limpar especulação deste branch
            if self.branch_stack and branch_pc in self.branch_stack:
                # Remove este branch da stack
                while self.branch_stack and self.branch_stack[-1] != branch_pc:
                    self.branch_stack.pop()
                if self.branch_stack:
                    self.branch_stack.pop()
                
                self.speculation_level = len(self.branch_stack)
                print(f"Predição correta - nível de especulação: {self.speculation_level}")
            
            return False

    def flush_speculative_instructions(self, branch_pc: int) -> List[int]:
        """Flush instruções especulativas após misprediction"""
        print(f"=== FLUSH ESPECULATIVO ===")
        print(f"Branch PC: {branch_pc}")
        print(f"Instruções especulativas antes: {len(self.speculative_instructions)}")
        
        flushed_rob_indices = []
        instructions_to_remove = []
        
        for i, spec_instr in enumerate(self.speculative_instructions):
            print(f"Verificando instrução especulativa: PC {spec_instr.pc}, Branch PC {spec_instr.branch_pc}")
            
            # Flush instruções que dependem deste branch ou vieram depois
            if spec_instr.branch_pc == branch_pc or spec_instr.pc > branch_pc:
                flushed_rob_indices.append(spec_instr.rob_index)
                instructions_to_remove.append(i)
                self.stats['speculative_instructions_flushed'] += 1
                print(f">>> FLUSHING instrução especulativa PC {spec_instr.pc}")
        
        # Remove instruções flushed
        for i in reversed(instructions_to_remove):
            del self.speculative_instructions[i]
        
        # Reset do estado especulativo
        if self.branch_stack and branch_pc in self.branch_stack:
            # Remove este branch e todos os posteriores
            while self.branch_stack and self.branch_stack[-1] != branch_pc:
                self.branch_stack.pop()
            if self.branch_stack:
                self.branch_stack.pop()
            
            self.speculation_level = len(self.branch_stack)
        
        print(f"Instruções especulativas após flush: {len(self.speculative_instructions)}")
        print(f"Novo nível de especulação: {self.speculation_level}")
        print(f"ROB indices flushed: {flushed_rob_indices}")
        
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

    def clear_all_speculation(self):
        """Limpa toda especulação (para reset)"""
        self.speculative_instructions.clear()
        self.branch_stack.clear()
        self.speculation_level = 0
        self.recovery_pc = None
        print("Especulação completamente limpa")