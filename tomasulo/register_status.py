from typing import Dict, Optional

class RegisterStatus:
    def __init__(self):
        # Registradores MIPS (R0-R31 e F0-F31)
        self.registers: Dict[str, int] = {f"R{i}": 0 for i in range(32)}
        self.registers.update({f"F{i}": 0 for i in range(32)})
        # Status dos registradores (qual estação de reserva está produzindo o valor)
        self.status: Dict[str, Optional[str]] = {f"R{i}": None for i in range(32)}
        self.status.update({f"F{i}": None for i in range(32)})
        # Valores dos registradores
        self.values: Dict[str, int] = {f"R{i}": 0 for i in range(32)}
        self.values.update({f"F{i}": 0 for i in range(32)})

    def get_value(self, register: str) -> int:
        """Retorna o valor atual do registrador"""
        return self.values[register]

    def set_value(self, register: str, value: int):
        """Atualiza o valor do registrador"""
        self.values[register] = value
        self.status[register] = None

    def get_status(self, register: str) -> Optional[str]:
        """Retorna a estação de reserva que está produzindo o valor do registrador"""
        return self.status[register]

    def set_status(self, register: str, station: Optional[str]):
        print(f"Renomeando registrador {register} para estação {station}")
        """Atualiza o status do registrador"""
        print("wbrewu")
        self.status[register] = station

    def is_ready(self, register: str) -> bool:
        """Verifica se o registrador está pronto (não depende de nenhuma estação de reserva)"""
        return self.status[register] is None

    def update_on_commit(self, register: str, value: int):
        """Atualiza o valor do registrador quando uma instrução é commitada"""
        self.values[register] = value
        self.status[register] = None

    def get_all_registers(self) -> Dict[str, Dict]:
        """Retorna o estado atual de todos os registradores"""
        return {
            reg: {
                "value": self.values[reg],
                "status": self.status[reg]
            }
            for reg in self.registers.keys()
        } 