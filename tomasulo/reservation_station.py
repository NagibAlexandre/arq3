from dataclasses import dataclass
from typing import Optional, Dict
from .instructions import Instruction, InstructionType
from .branch_predictor import BranchPrediction

@dataclass
class ReservationStation:
    name: str
    busy: bool = False
    op: Optional[InstructionType] = None
    vj: Optional[int] = None
    vk: Optional[int] = None
    qj: Optional[str] = None
    qk: Optional[str] = None
    a: Optional[int] = None
    instruction: Optional[Instruction] = None
    remaining_cycles: int = 0
    rob_index: Optional[int] = None

    # Novos campos para especulação
    pc: Optional[int] = None  # Program Counter da instrução
    branch_prediction: Optional[BranchPrediction] = None
    speculative: bool = False

class ReservationStations:
    def __init__(self, n_add=3, n_mul=3, n_mem=2):
        self.add_stations: Dict[str, ReservationStation] = {
            f"Add{i}": ReservationStation(f"Add{i}") for i in range(n_add)
        }
        self.mul_stations: Dict[str, ReservationStation] = {
            f"Mul{i}": ReservationStation(f"Mul{i}") for i in range(n_mul)
        }
        self.mem_stations: Dict[str, ReservationStation] = {
            f"Mem{i}": ReservationStation(f"Mem{i}") for i in range(n_mem)
        }

    def get_available_station(self, instruction: Instruction) -> Optional[ReservationStation]:
        if instruction.type in [InstructionType.ADD, InstructionType.SUB, 
                            InstructionType.BEQ, InstructionType.BNE]:  # Desvios usam estações ADD
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

    def flush_speculative_stations(self, branch_pc: int):
        """Remove instruções especulativas das estações"""
        flushed_stations = []
        for stations in [self.add_stations, self.mul_stations, self.mem_stations]:
            for station in stations.values():
                if (station.busy and hasattr(station, 'speculative') and station.speculative and 
                    hasattr(station, 'pc') and station.pc > branch_pc):
                    
                    # Salva informação da estação flushed
                    flushed_stations.append({
                        'name': station.name,
                        'instruction': str(station.instruction) if station.instruction else None,
                        'pc': station.pc
                    })
                    
                    # Limpa a estação
                    self.clear_station(station)

        return flushed_stations

    def clear_station(self, station: ReservationStation):
        """Limpa uma estação de reserva"""
        station.busy = False
        station.op = None
        station.vj = None
        station.vk = None
        station.qj = None
        station.qk = None
        station.a = None
        station.instruction = None
        station.remaining_cycles = 0
        station.rob_index = None
        station.pc = None
        station.branch_prediction = None
        station.speculative = False

    def is_ready(self, station: ReservationStation) -> bool:
        return (station.busy and 
                station.qj is None and 
                station.qk is None and 
                station.remaining_cycles == 0)

    def get_all_stations(self) -> Dict[str, ReservationStation]:
        return {
            **self.add_stations,
            **self.mul_stations,
            **self.mem_stations
        }

    def get_speculative_count(self) -> int:
        """Retorna número de estações com instruções especulativas"""
        count = 0
        for station in self.get_all_stations().values():
            if station.busy and station.speculative:
                count += 1
        return count