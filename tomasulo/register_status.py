from typing import Dict, Optional, List

class RegisterStatus:
    def __init__(self, n_logical=32, n_physical=64):
        # Registradores lógicos MIPS (R0-R31 e F0-F31)
        self.n_logical = n_logical
        self.n_physical = n_physical
        self.logical_registers: List[str] = [f"R{i}" for i in range(n_logical)]
        self.logical_registers += [f"F{i}" for i in range(n_logical)]
        self.physical_registers: List[str] = [f"P{i}" for i in range(n_physical*2)]

        # Banco de registradores físicos (inteiros + float)
        self.phys_values: Dict[str, int] = {p: 0 for p in self.physical_registers}
        # Mapeamento lógico → físico
        self.rename_map: Dict[str, str] = {reg: f"P{i}" for i, reg in enumerate(self.logical_registers)}
        # Lista de físicos livres
        self.free_phys: List[str] = self.physical_registers[len(self.logical_registers):].copy()
        # Status dos registradores lógicos (qual estação está produzindo o valor)
        self.status: Dict[str, Optional[str]] = {reg: None for reg in self.logical_registers}

    def get_value(self, register: str) -> int:
        """Retorna o valor atual do registrador lógico (via físico)"""
        phys = self.rename_map[register]
        return self.phys_values[phys]

    def set_value(self, register: str, value: int):
        """Atualiza o valor do registrador lógico (via físico)"""
        phys = self.rename_map[register]
        self.phys_values[phys] = value
        self.status[register] = None

    def get_status(self, register: str) -> Optional[str]:
        """Retorna a estação de reserva que está produzindo o valor do registrador lógico"""
        return self.status[register]

    def set_status(self, register: str, station: Optional[str]):
        print(f"Renomeando registrador {register} para estação {station}")
        self.status[register] = station

    def is_ready(self, register: str) -> bool:
        """Verifica se o registrador lógico está pronto (não depende de nenhuma estação)"""
        return self.status[register] is None

    def update_on_commit(self, register: str, value: int):
        """Atualiza o valor do registrador lógico no commit (via físico)"""
        phys = self.rename_map[register]
        self.phys_values[phys] = value
        self.status[register] = None

    # --- Renomeação física ---
    def allocate_physical(self, logical: str) -> str:
        """Aloca um registrador físico livre para um registrador lógico"""
        if not self.free_phys:
            raise Exception("Sem registradores físicos livres!")
        new_phys = self.free_phys.pop(0)
        old_phys = self.rename_map[logical]
        self.rename_map[logical] = new_phys
        return old_phys  # retorna o antigo para liberar depois

    def free_physical(self, phys: str):
        """Libera um registrador físico para uso futuro"""
        if phys not in self.free_phys:
            self.free_phys.append(phys)

    def get_physical(self, logical: str) -> str:
        return self.rename_map[logical]

    def get_all_registers(self) -> Dict[str, Dict]:
        """Retorna o estado atual de todos os registradores lógicos e físicos"""
        return {
            reg: {
                "physical": self.rename_map[reg],
                "value": self.phys_values[self.rename_map[reg]],
                "status": self.status[reg]
            }
            for reg in self.logical_registers
        }

    def get_all_physical(self) -> Dict[str, int]:
        return {p: self.phys_values[p] for p in self.physical_registers} 