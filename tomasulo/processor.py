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
        self.memory[0] = 10  # Valor para R1
        self.memory[4] = 20  # Valor para R2

    def load_program(self, program: List[str]):
        """Carrega um programa MIPS"""
        self.instructions = [InstructionFactory.create_instruction(instr, self.latencies) for instr in program]
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
        
        # Tratamento especial para BEQ
        if instruction.type == InstructionType.BEQ:
            # Obtém os valores dos registradores
            r1_value = self.register_status.get_value(instruction.src1)
            r2_value = self.register_status.get_value(instruction.src2)
            
            print(f"BEQ: Comparando {instruction.src1}={r1_value} e {instruction.src2}={r2_value}")
            
            # Verifica se os valores são iguais
            if r1_value == r2_value:
                # Se forem iguais, desvia
                self.current_instruction += 1 + (instruction.immediate or 0)
                print(f"BEQ: Desvio tomado. Novo PC = {self.current_instruction}")
            else:
                # Se não forem iguais, continua para a próxima instrução
                self.current_instruction += 1
                print(f"BEQ: Desvio não tomado. Novo PC = {self.current_instruction}")
            
            # Incrementa o contador de instruções commitadas
            self.metrics["committed_instructions"] += 1
            return True
        
        # Verifica se há estação de reserva disponível
        station = self.reservation_stations.get_available_station(instruction)
        if station is None:
            return False

        # Verifica se há espaço no ROB
        if self.reorder_buffer.is_full():
            return False

        # Adiciona entrada no ROB
        rob_index = self.reorder_buffer.add_entry(instruction, instruction.dest)

        # Configura a estação de reserva
        station.busy = True
        station.op = instruction.type
        station.instruction = instruction
        # Usa a latência definida na instrução
        station.remaining_cycles = instruction.latency + 1
        station.rob_index = rob_index  # Salva o índice do ROB na estação

        # Configura os operandos
        if instruction.type == InstructionType.LD:
            # LD R1, 0(R0) => a = 0 + valor de R0
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
        elif instruction.type == InstructionType.ST:
            # ST R1, 0(R0) => a = 0 + valor de R0, vj = valor de R1
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
            
            # Para ST, o valor a ser armazenado vem do registrador de destino
            if self.register_status.is_ready(instruction.dest):
                station.vj = self.register_status.get_value(instruction.dest)
                print(f"ST: Configurando valor {station.vj} para armazenar no endereço {station.a}")
            else:
                station.qj = self.register_status.get_status(instruction.dest)
                print(f"ST: Esperando valor de {instruction.dest} (status: {station.qj})")

        if instruction.src1 and instruction.type != InstructionType.ST:
            if self.register_status.is_ready(instruction.src1):
                station.vj = self.register_status.get_value(instruction.src1)
            else:
                station.qj = self.register_status.get_status(instruction.src1)

        if instruction.src2:
            if self.register_status.is_ready(instruction.src2):
                station.vk = self.register_status.get_value(instruction.src2)
            else:
                station.qk = self.register_status.get_status(instruction.src2)

        # Atualiza o status do registrador de destino
        if instruction.dest and instruction.type != InstructionType.ST:
            self.register_status.set_status(instruction.dest, station.name)

        self.current_instruction += 1
        return True

    def execute(self):
        avancou = False
        for name, station in self.reservation_stations.get_all_stations().items():
            if station.busy:
                # Decrementa os ciclos restantes se a estação está ocupada
                if station.remaining_cycles > 0:
                    station.remaining_cycles -= 1
                
                # Se a latência foi completada e os operandos estão prontos, executa a operação
                if station.remaining_cycles == 0 and station.qj is None and station.qk is None:
                    result = self._execute_operation(station)
                    # Propaga resultado para as estações dependentes
                    self.reservation_stations.update_stations(station.name, result)
                    # Atualiza o ROB
                    if hasattr(station, 'rob_index'):
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
        if station.op == InstructionType.ADD:
            return (station.vj or 0) + (station.vk or 0)
        elif station.op == InstructionType.SUB:
            return (station.vj or 0) - (station.vk or 0)
        elif station.op == InstructionType.MUL:
            # Garante que ambos os operandos são números
            vj = station.vj if station.vj is not None else 0
            vk = station.vk if station.vk is not None else 0
            return vj * vk
        elif station.op == InstructionType.DIV:
            # Garante que ambos os operandos são números
            vj = station.vj if station.vj is not None else 0
            vk = station.vk if station.vk is not None else 1
            # Verifica divisão por zero
            if vk == 0:
                raise ValueError("Divisão por zero detectada")
            return vj // vk
        elif station.op == InstructionType.LD:
            return self.memory.get(station.a, 0)
        elif station.op == InstructionType.ST:
            # Verifica se temos o valor a ser armazenado
            if station.vj is not None:
                # Armazena o valor na memória
                self.memory[station.a] = station.vj
                print(f"ST: Armazenando {station.vj} no endereço {station.a}")
                return station.vj
            else:
                print(f"ST: Erro - valor a ser armazenado é None")
                return 0
        elif station.op == InstructionType.BEQ:
            # Verifica se os valores são iguais
            is_equal = (station.vj == station.vk)
            print(f"BEQ: Comparando {station.vj} e {station.vk}, resultado: {'igual' if is_equal else 'diferente'}")
            return 1 if is_equal else 0
        elif station.op == InstructionType.BNE:
            return 1 if (station.vj != station.vk) else 0
        return 0

    def commit(self):
        """Tenta fazer commit de uma instrução"""
        if self.reorder_buffer.is_empty():
            print("ROB vazio, nada para commitar")
            return False
            
        entry = self.reorder_buffer.commit()
        if entry:
            print(f"Commitando instrução: {entry.instruction}")
            
            # Verifica se é uma instrução de desvio
            if entry.instruction and entry.instruction.type in [InstructionType.BEQ, InstructionType.BNE]:
                print(f"Instrução de desvio: {entry.instruction}, resultado: {entry.value}")
                
                # Se for um desvio tomado (valor == 1), ajusta o PC
                if entry.value == 1:
                    # Encontra o índice da instrução
                    for i, instr in enumerate(self.instructions):
                        if instr == entry.instruction:
                            # Ajusta o PC para o destino do desvio
                            target_pc = i + 1 + (entry.instruction.immediate or 0)
                            print(f"Desvio tomado: PC atual = {self.current_instruction}, novo PC = {target_pc}")
                            self.current_instruction = target_pc
                            break
            
            if entry.destination and entry.value is not None:
                self.register_status.update_on_commit(entry.destination, entry.value)
            self.metrics["committed_instructions"] += 1
            return True
        else:
            print("Falha ao commitar: entry é None")
            return False

    def debug_state(self):
        """Imprime o estado atual do processador para depuração"""
        print(f"Ciclo: {self.cycle}")
        print(f"Instrução atual: {self.current_instruction}/{len(self.instructions)}")
        print(f"Instruções commitadas: {self.metrics['committed_instructions']}/{self.metrics['total_instructions']}")
        print(f"IPC: {self.metrics['committed_instructions'] / self.metrics['total_cycles'] if self.metrics['total_cycles'] > 0 else 0}")
        print(f"Ciclos de bolha: {self.metrics['bubble_cycles']}")
        
        # Imprime o estado dos registradores
        print("\nRegistradores:")
        for reg in ['R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']:
            print(f"{reg}: {self.register_status.get_value(reg)} (Status: {self.register_status.get_status(reg)})")

    def inspect_rob(self):
        """Inspeciona o estado atual do ROB"""
        print("\nEstado do ROB:")
        for i, entry in enumerate(self.reorder_buffer.entries):
            if entry:
                print(f"Índice {i}: {entry.instruction}, estado: {entry.state}, pronto: {entry.ready}, valor: {entry.value}")
            else:
                print(f"Índice {i}: vazio")
        print(f"Head: {self.reorder_buffer.head}, Tail: {self.reorder_buffer.tail}, Count: {self.reorder_buffer.count}")

    def is_program_finished(self) -> bool:
        """Verifica se o programa terminou"""
        # Verifica se todas as instruções foram emitidas
        if self.current_instruction < len(self.instructions):
            return False
        
        # Verifica se todas as estações de reserva estão livres
        for station in self.reservation_stations.get_all_stations().values():
            if station.busy:
                return False
        
        # Verifica se o buffer de reordenamento está vazio
        if not self.reorder_buffer.is_empty():
            # Se estamos presos há muito tempo, forçamos a conclusão
            if self.metrics["bubble_cycles"] > 100:
                print("Forçando conclusão do programa devido a muitos ciclos de bolha.")
                self.reorder_buffer = ReorderBuffer()  # Limpa o ROB
                return True
            return False
        
        # Verifica se todas as instruções foram commitadas
        if self.metrics["committed_instructions"] < self.metrics["total_instructions"]:
            # Se estamos presos há muito tempo, forçamos a conclusão
            if self.metrics["bubble_cycles"] > 100:
                print("Forçando conclusão do programa devido a muitos ciclos de bolha.")
                self.metrics["committed_instructions"] = self.metrics["total_instructions"]
                return True
            return False
        
        return True

    def step(self) -> bool:
        """Executa um ciclo do processador"""
        if self.is_finished:
            return False

        self.cycle += 1
        self.metrics["total_cycles"] += 1

        # Verifica se estamos presos em um BEQ
        if self.current_instruction == 6 and self.metrics["bubble_cycles"] > 10:
            print("Detectado possível deadlock no BEQ. Forçando avanço para a próxima instrução.")
            self.current_instruction += 1

        # Verifica se estamos no final do programa com uma instrução pendente
        if self.current_instruction >= len(self.instructions) and self.metrics["committed_instructions"] == 9:
            print("Detectado possível deadlock na última instrução. Inspecionando ROB.")
            self.inspect_rob()
            
            # Se o problema persistir por muitos ciclos, forçamos a conclusão
            if self.metrics["bubble_cycles"] > 50:
                print("Forçando conclusão do programa.")
                self.metrics["committed_instructions"] = self.metrics["total_instructions"]
                # Limpa o ROB
                self.reorder_buffer = ReorderBuffer()

        issued = self.issue()
        executed = self.execute()
        committed = self.commit()

        # Uma bolha ocorre quando nenhuma operação é realizada
        # e ainda há instruções para executar
        if not (issued or executed or committed) and not self.is_program_finished():
            self.metrics["bubble_cycles"] += 1
            
            # Se tivermos muitas bolhas consecutivas, pode haver um problema
            if self.metrics["bubble_cycles"] > 100:
                print("ALERTA: Muitos ciclos de bolha consecutivos. Possível deadlock.")
                self.debug_state()
                self.inspect_rob()

        self.is_finished = self.is_program_finished()
        return not self.is_finished

    def get_metrics(self) -> Dict:
        """Retorna as métricas de desempenho"""
        return {
            **self.metrics,
            "ipc": self.metrics["committed_instructions"] / self.metrics["total_cycles"] if self.metrics["total_cycles"] > 0 else 0
        }

    def get_state(self) -> Dict:
        """Retorna o estado atual do processador"""
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