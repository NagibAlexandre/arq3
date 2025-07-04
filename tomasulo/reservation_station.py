from dataclasses import dataclass
from typing import Optional, Dict
from .instructions import Instruction, InstructionType

@dataclass
class ReservationStation:
    name: str
    busy: bool = False
    op: Optional[InstructionType] = None
    vj: Optional[int] = None
    vk: Optional[int] = None
    
    # Armazena o índice do ROB que produzirá os operandos.
    qj: Optional[int] = None
    qk: Optional[int] = None
    
    a: Optional[int] = None
    instruction: Optional[Instruction] = None
    remaining_cycles: int = 0
    rob_index: Optional[int] = None

class ReservationStations:
    def __init__(self, n_add=3, n_mul=3, n_mem=2):
        # ... (nenhuma mudança no __init__)
        self.add_stations: Dict[str, ReservationStation] = { f"Add{i}": ReservationStation(f"Add{i}") for i in range(n_add) }
        self.mul_stations: Dict[str, ReservationStation] = { f"Mul{i}": ReservationStation(f"Mul{i}") for i in range(n_mul) }
        self.mem_stations: Dict[str, ReservationStation] = { f"Mem{i}": ReservationStation(f"Mem{i}") for i in range(n_mem) }

    def get_available_station(self, instruction: Instruction) -> Optional[ReservationStation]:
        # ... (nenhuma mudança aqui)
        if instruction.type in [InstructionType.ADD, InstructionType.SUB]:
            for station in self.add_stations.values():
                if not station.busy: return station
        elif instruction.type in [InstructionType.MUL, InstructionType.DIV]:
            for station in self.mul_stations.values():
                if not station.busy: return station
        elif instruction.type in [InstructionType.LD, InstructionType.ST]:
            for station in self.mem_stations.values():
                if not station.busy: return station
        return None

    # --- ALTERADO ---
    def update_stations(self, rob_index: int, value: int):
        """Atualiza as estações de reserva usando o índice do ROB como tag."""
        for stations in [self.add_stations, self.mul_stations, self.mem_stations]:
            for station in stations.values():
                if station.qj == rob_index:
                    station.vj = value
                    station.qj = None
                if station.qk == rob_index:
                    station.vk = value
                    station.qk = None

    def is_ready(self, station: ReservationStation) -> bool:
        # Uma estação está pronta quando está ocupada, tem todos os operandos
        # e completou sua latência
        return (station.busy and 
                station.qj is None and 
                station.qk is None and 
                station.remaining_cycles == 0)

    def get_all_stations(self) -> Dict[str, ReservationStation]:
        """Retorna todas as estações de reserva em um único dicionário"""
        return {
            **self.add_stations,
            **self.mul_stations,
            **self.mem_stations
        } 