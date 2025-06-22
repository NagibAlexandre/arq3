# processor.py

from typing import List, Optional, Dict
from .instructions import Instruction, InstructionType, InstructionFactory
from .reservation_station import ReservationStations
from .register_status import RegisterStatus
from .reorder_buffer import ReorderBuffer

class TomasuloProcessor:
    def __init__(self, latencies=None, n_add=3, n_mul=3, n_mem=2):
        self.latencies = latencies or {}
        self.reservation_stations = ReservationStations(n_add=n_add, n_mul=n_mul, n_mem=n_mem)
        self.register_status = RegisterStatus()
        self.reorder_buffer = ReorderBuffer()
        self.instructions: List[Instruction] = []
        self.current_instruction = 0
        self.cycle = 0
        self.metrics = {
            "total_instructions": 0,
            "total_cycles": 0,
            "bubble_cycles": 0,
            "committed_instructions": 0
        }
        self.memory: Dict[int, int] = {}  # Memória simulada
        self.is_finished = False
        # Inicializa a memória com alguns valores para teste
        self.memory[0] = 10
        self.memory[4] = 20
        self.instruction_status = [] # Lista para rastrear o status de cada instrução

    def load_program(self, program: List[str]):
        """Carrega um programa MIPS"""
        self.instructions = [InstructionFactory.create_instruction(instr, self.latencies) for instr in program]
        # Inicializa o status das instruções com todas as instruções do programa
        self.instruction_status = [{
            'instruction': str(instr),
            'issue': False,
            'execute': False,
            'write_result': False,
            'commit': False
        } for instr in self.instructions]
        self.current_instruction = 0
        self.cycle = 0
        self.is_finished = False
        self.metrics = {
            "total_instructions": len(program),
            "total_cycles": 0,
            "bubble_cycles": 0,
            "committed_instructions": 0
        }
        # Limpa as estações de reserva e o buffer de reordenamento
        self.reservation_stations = ReservationStations(
            n_add=len(self.reservation_stations.add_stations),
            n_mul=len(self.reservation_stations.mul_stations),
            n_mem=len(self.reservation_stations.mem_stations)
        )
        self.register_status = RegisterStatus()
        self.reorder_buffer = ReorderBuffer()
        self.memory[0] = 10
        self.memory[4] = 20

    def issue(self) -> bool:
        """Tenta emitir uma nova instrução"""
        if self.current_instruction >= len(self.instructions):
            return False

        instruction = self.instructions[self.current_instruction]
        
        if self.current_instruction < len(self.instruction_status):
            self.instruction_status[self.current_instruction]['issue'] = True
        
        # Tratamento para BEQ (sem ROB para simplificar)
        if instruction.type == InstructionType.BEQ:
            r1_value = self.register_status.get_value(instruction.src1)
            r2_value = self.register_status.get_value(instruction.src2)
            if r1_value == r2_value:
                self.current_instruction += 1 + (instruction.immediate or 0)
            else:
                self.current_instruction += 1
            self.metrics["committed_instructions"] += 1
            return True
        
        # Verifica se há estação de reserva e ROB disponíveis
        station = self.reservation_stations.get_available_station(instruction)
        if station is None or self.reorder_buffer.is_full():
            return False

        # --- LÓGICA CORRIGIDA ---

        # Adiciona entrada no ROB e obtém o índice (nossa nova tag)
        rob_index = self.reorder_buffer.add_entry(instruction, instruction.dest)

        # Configura a estação de reserva
        station.busy = True
        station.op = instruction.type
        station.instruction = instruction
        station.remaining_cycles = instruction.latency + 1
        station.rob_index = rob_index  # Associa o índice do ROB à estação

        # Configura os operandos, buscando dependências no ROB
        if instruction.type == InstructionType.LD:
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
        
        elif instruction.type == InstructionType.ST:
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
            # Para ST, o valor a ser armazenado vem do registrador 'dest'
            if self.register_status.is_ready(instruction.dest):
                station.vj = self.register_status.get_value(instruction.dest)
            else:
                producer_rob_index = self.register_status.get_status(instruction.dest)
                producer_entry = self.reorder_buffer.get_entry(producer_rob_index)
                if producer_entry and producer_entry.ready:
                    station.vj = producer_entry.value
                else:
                    station.qj = producer_rob_index

        # Busca operandos para src1
        if instruction.src1 and instruction.type not in [InstructionType.LD, InstructionType.ST]:
            if self.register_status.is_ready(instruction.src1):
                station.vj = self.register_status.get_value(instruction.src1)
                station.qj = None
            else:
                producer_rob_index = self.register_status.get_status(instruction.src1)
                producer_entry = self.reorder_buffer.get_entry(producer_rob_index)
                if producer_entry and producer_entry.ready:
                    station.vj = producer_entry.value
                    station.qj = None
                else:
                    station.qj = producer_rob_index
        
        # Busca operandos para src2
        if instruction.src2:
            if self.register_status.is_ready(instruction.src2):
                station.vk = self.register_status.get_value(instruction.src2)
                station.qk = None
            else:
                producer_rob_index = self.register_status.get_status(instruction.src2)
                producer_entry = self.reorder_buffer.get_entry(producer_rob_index)
                if producer_entry and producer_entry.ready:
                    station.vk = producer_entry.value
                    station.qk = None
                else:
                    station.qk = producer_rob_index

        # Atualiza o status do registrador de destino com o índice do ROB
        if instruction.dest and instruction.type != InstructionType.ST:
            self.register_status.set_status(instruction.dest, rob_index)

        self.current_instruction += 1
        return True

    def execute(self):
        avancou = False
        for name, station in self.reservation_stations.get_all_stations().items():
            if not station.busy:
                continue

            # Marca que a instrução está em execução
            if station.remaining_cycles == station.instruction.latency:
                for instr_status in self.instruction_status:
                    if instr_status['instruction'] == str(station.instruction):
                        instr_status['execute'] = True
                        break
            
            # Decrementa os ciclos restantes se a estação está ocupada e operandos prontos
            if station.qj is None and station.qk is None and station.remaining_cycles > 0:
                station.remaining_cycles -= 1
            
            # Se a latência foi completada, executa a operação
            if station.remaining_cycles == 0 and station.qj is None and station.qk is None:
                result = self._execute_operation(station)
                
                # --- LÓGICA CORRIGIDA ---
                # Propaga resultado usando o índice do ROB como tag
                if station.rob_index is not None:
                    self.reservation_stations.update_stations(station.rob_index, result)
                    self.reorder_buffer.update_entry(station.rob_index, result)
                
                # Libera a estação de reserva
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
                avancou = True
        return avancou

    def _execute_operation(self, station) -> int:
        """Executa a operação na estação de reserva"""
        result = 0
        try:
            if station.op == InstructionType.ADD:
                result = (station.vj or 0) + (station.vk or 0)
            elif station.op == InstructionType.SUB:
                result = (station.vj or 0) - (station.vk or 0)
            elif station.op == InstructionType.MUL:
                result = (station.vj or 0) * (station.vk or 0)
            elif station.op == InstructionType.DIV:
                vk = station.vk if station.vk is not None and station.vk != 0 else 1
                result = (station.vj or 0) // vk
            elif station.op == InstructionType.LD:
                result = self.memory.get(station.a, 0)
            elif station.op == InstructionType.ST:
                if station.vj is not None:
                    self.memory[station.a] = station.vj
                result = station.vj or 0 # ST não tem resultado para propagar, mas ROB precisa de um valor
    
            # Marca que a instrução escreveu seu resultado
            for instr_status in self.instruction_status:
                if instr_status['instruction'] == str(station.instruction):
                    instr_status['write_result'] = True
                    break
        except Exception as e:
            print(f"Erro ao executar operação: {e}")
            result = 0
        return result

    def commit(self):
        """Tenta fazer commit de uma instrução"""
        if self.reorder_buffer.is_empty():
            return False

        # Pega o índice ANTES de remover a entrada do ROB
        committing_index = self.reorder_buffer.head
        entry = self.reorder_buffer.commit()

        if entry:
            # Marca que a instrução foi commitada
            for instr_status in self.instruction_status:
                if instr_status['instruction'] == str(entry.instruction):
                    instr_status['commit'] = True
                    break
            
            # Para ST, o valor já foi escrito na memória na fase de execução,
            # aqui apenas confirmamos. Para outros, escrevemos no registrador.
            if entry.instruction.type != InstructionType.ST and entry.destination and entry.value is not None:
                 # Faz o commit no registrador, passando o índice do ROB para a verificação
                self.register_status.update_on_commit(entry.destination, entry.value, committing_index)

            self.metrics["committed_instructions"] += 1
            return True
        return False

    def is_program_finished(self) -> bool:
        """Verifica se o programa terminou"""
        # A condição final é quando todas as instruções foram commitadas
        return self.metrics["committed_instructions"] == self.metrics["total_instructions"]

    def step(self) -> bool:
        """Executa um ciclo do processador"""
        if self.is_finished:
            return False

        self.cycle += 1
        self.metrics["total_cycles"] += 1

        # A ordem é importante para simular o pipeline: Commit -> Execute -> Issue
        committed = self.commit()
        executed = self.execute()
        issued = self.issue()

        # Uma bolha ocorre quando nada progride e o programa não terminou
        if not (issued or executed or committed) and not self.is_program_finished():
            self.metrics["bubble_cycles"] += 1

        self.is_finished = self.is_program_finished()
        # Se finalizou, retorna False para parar o simulador
        return not self.is_finished

    def get_metrics(self) -> Dict:
        """Retorna as métricas de desempenho"""
        return {
            **self.metrics,
            "ipc": self.metrics["committed_instructions"] / self.metrics["total_cycles"] if self.metrics["total_cycles"] > 0 else 0
        }

    def get_state(self) -> Dict:
        """Retorna o estado atual do processador"""
        # O restante do arquivo (get_state, debug_state, etc.) não precisa de alterações.
        return {
            "cycle": self.cycle,
            "metrics": self.get_metrics(),
            "registers": self.register_status.get_all_registers(),
            "reservation_stations": {
                name: {
                    "busy": station.busy,
                    "op": station.op.value if station.op else None,
                    "vj": station.vj,
                    "vk": station.vk,
                    "qj": station.qj,
                    "qk": station.qk,
                    "a": station.a,
                    "remaining_cycles": station.remaining_cycles
                }
                for name, station in self.reservation_stations.get_all_stations().items()
            },
            "instruction_status": self.instruction_status,
            "reorder_buffer": [
                {
                    "instruction": str(entry.instruction) if entry else None,
                    "state": entry.state if entry else None,
                    "destination": entry.destination if entry else None,
                    "value": entry.value if entry else None,
                    "ready": entry.ready if entry else None
                }
                for entry in self.reorder_buffer.get_all_entries()
            ],
            "is_finished": self.is_finished
        }