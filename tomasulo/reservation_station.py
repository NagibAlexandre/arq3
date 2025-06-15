from dataclasses import dataclass
from typing import Optional, Dict
from .instructions import Instruction, InstructionType

@dataclass
class ReservationStation:
    name: str
    busy: bool = False
    op: Optional[InstructionType] = None
    vj: Optional[int] = None  # Valor do primeiro operando
    vk: Optional[int] = None  # Valor do segundo operando
    qj: Optional[str] = None  # Estação de reserva que produzirá vj
    qk: Optional[str] = None  # Estação de reserva que produzirá vk
    a: Optional[int] = None   # Endereço para load/store
    instruction: Optional[Instruction] = None
    remaining_cycles: int = 0
    rob_index: Optional[int] = None  # Índice do ROB associado

class ReservationStations:
    def __init__(self, n_add=3, n_mul=3, n_mem=2):
        # Estações de reserva para operações aritméticas
        self.add_stations: Dict[str, ReservationStation] = {
            f"Add{i}": ReservationStation(f"Add{i}") for i in range(n_add)
        }
        self.mul_stations: Dict[str, ReservationStation] = {
            f"Mul{i}": ReservationStation(f"Mul{i}") for i in range(n_mul)
        }
        # Estações de reserva para load/store unificadas
        self.mem_stations: Dict[str, ReservationStation] = {
            f"Mem{i}": ReservationStation(f"Mem{i}") for i in range(n_mem)
        }

    def get_available_station(self, instruction: Instruction) -> Optional[ReservationStation]:
        if instruction.type in [InstructionType.ADD, InstructionType.SUB]:
            for station in self.add_stations.values():
                if not station.busy:
                    return station
        elif instruction.type in [InstructionType.MUL, InstructionType.DIV]:
            for station in self.mul_stations.values():
                if not station.busy:
                    return station
        elif instruction.type in [InstructionType.LD, InstructionType.ST]:
            for station in self.mem_stations.values():
                if not station.busy:
                    return station
        return None

    def update_stations(self, tag: str, value: int):
        """Atualiza as estações de reserva quando um resultado está disponível"""
        for stations in [self.add_stations, self.mul_stations, self.mem_stations]:
            for station in stations.values():
                if station.qj == tag:
                    station.vj = value
                    station.qj = None
                if station.qk == tag:
                    station.vk = value
                    station.qk = None

    def is_ready(self, station: ReservationStation) -> bool:
        # Para LD/ST, basta estar ocupada e ter ciclos restantes
        if station.op in [InstructionType.LD, InstructionType.ST]:
            return station.busy and station.remaining_cycles > 0
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