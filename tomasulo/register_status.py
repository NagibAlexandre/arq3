from typing import Dict, Optional

class RegisterStatus:
    def __init__(self):
        # Registradores MIPS (R0-R31 e F0-F31)
        self.registers: Dict[str, int] = {f"R{i}": 0 for i in range(32)}
        self.registers.update({f"F{i}": 0 for i in range(32)})
 
        self.status: Dict[str, Optional[int]] = {f"R{i}": None for i in range(32)}
        self.status.update({f"F{i}": None for i in range(32)})
        
        self.values: Dict[str, int] = {f"R{i}": 0 for i in range(32)}
        self.values.update({f"F{i}": 0 for i in range(32)})

    def get_value(self, register: str) -> int:
        """Retorna o valor atual do registrador"""
        return self.values[register]

    def set_value(self, register: str, value: int):
        """Atualiza o valor do registrador"""
        self.values[register] = value
        self.status[register] = None

    def get_status(self, register: str) -> Optional[int]:
        """Retorna o índice do ROB que está produzindo o valor do registrador"""
        return self.status[register]

    def set_status(self, register: str, rob_index: Optional[int]):
        """Atualiza o status do registrador com o índice do ROB"""
        self.status[register] = rob_index

    def is_ready(self, register: str) -> bool:
        return self.status[register] is None

    def update_on_commit(self, register: str, value: int, rob_index: int):
        """Atualiza o valor do registrador e o status no commit."""
        self.values[register] = value
        # Só limpa o status se o commit atual corresponder à última instrução
        # que foi emitida para este registrador.
        if self.status.get(register) == rob_index:
            self.status[register] = None

    def get_all_registers(self) -> Dict[str, Dict]:
        return {
            reg: {
                "value": self.values[reg],
                "status": self.status[reg]
            }
            for reg in self.registers.keys()
        }