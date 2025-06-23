from typing import List, Optional, Dict
from .instructions import Instruction, InstructionType, InstructionFactory
from .reservation_station import ReservationStations
from .register_status import RegisterStatus
from .reorder_buffer import ReorderBuffer
from .branch_predictor import BranchPredictor, BranchPrediction
from .speculation_manager import SpeculationManager

class TomasuloProcessor:
    def __init__(self, latencies=None, n_add=3, n_mul=3, n_mem=2, enable_speculation=True):
        self.latencies = latencies or {}
        self.reservation_stations = ReservationStations(n_add=n_add, n_mul=n_mul, n_mem=n_mem)
        self.register_status = RegisterStatus()
        self.reorder_buffer = ReorderBuffer()
        
        # Sistema de especulação
        self.enable_speculation = enable_speculation
        self.branch_predictor = BranchPredictor() if enable_speculation else None
        self.speculation_manager = SpeculationManager() if enable_speculation else None
        
        self.instructions: List[Instruction] = []
        self.current_instruction = 0
        self.cycle = 0
        self.pc = 0  # Program Counter
        
        self.metrics = {
            "total_instructions": 0,
            "total_cycles": 0,
            "bubble_cycles": 0,
            "committed_instructions": 0,
            "mispredictions": 0,
            "speculative_instructions": 0
        }
        
        self.memory: Dict[int, int] = {}
        self.is_finished = False
        self.memory[0] = 10
        self.memory[4] = 20
        self.instruction_status = []
        
        # Estado de recuperação
        self.recovering_from_misprediction = False
        self.pending_branch_resolutions: List[Dict] = []

    def load_program(self, program: List[str]):
        """Carrega um programa MIPS"""
        self.instructions = [InstructionFactory.create_instruction(instr, self.latencies) 
                        for instr in program]
        
        self.instruction_status = [{
            'instruction': str(instr),
            'pc': i,
            'issue': False,
            'execute': False,
            'write_result': False,
            'commit': False,
            'speculative': False,
            'flushed': False
        } for i, instr in enumerate(self.instructions)]
        
        self.current_instruction = 0
        self.pc = 0
        self.cycle = 0
        self.is_finished = False
        self.recovering_from_misprediction = False
        
        self.metrics = {
            "total_instructions": len(program),
            "total_cycles": 0,
            "bubble_cycles": 0,
            "committed_instructions": 0,
            "mispredictions": 0,
            "speculative_instructions": 0
        }
        
        # Reset componentes
        self.reservation_stations = ReservationStations(
            n_add=len(self.reservation_stations.add_stations),
            n_mul=len(self.reservation_stations.mul_stations),
            n_mem=len(self.reservation_stations.mem_stations)
        )
        self.register_status = RegisterStatus()
        self.reorder_buffer = ReorderBuffer()
        
        if self.enable_speculation:
            self.branch_predictor = BranchPredictor()
            self.speculation_manager = SpeculationManager()
        
        self.memory[0] = 10
        self.memory[4] = 20

   
    # processor.py (correção específica para desvios)
    def issue(self) -> bool:
        """Tenta emitir uma nova instrução com suporte à especulação"""
        if self.pc >= len(self.instructions):
            return False

        instruction = self.instructions[self.pc]

        # Verifica se esta instrução já foi emitida
        if self.pc < len(self.instruction_status):
            if self.instruction_status[self.pc]['issue']:
                return False  # Já foi emitida

        # Verifica disponibilidade de recursos
        station = self.reservation_stations.get_available_station(instruction)
        if station is None:
            return False

        if self.reorder_buffer.is_full():
            return False

        # Instruções normais após desvios são especulativas
        is_speculative_before = (self.enable_speculation and 
                            self.speculation_manager.is_speculative())

        branch_prediction = None
        next_pc = self.pc + 1  # PC padrão (sequencial)

        if (self.enable_speculation and 
            instruction.type in [InstructionType.BEQ, InstructionType.BNE]):
            
            branch_prediction = self.branch_predictor.predict(self.pc, instruction.type.value)
            
            if branch_prediction.taken:
                # Cálculo correto do endereço de desvio
                next_pc = self.pc + 1 + (instruction.immediate or 0)
                print(f"Predição: Desvio tomado de PC {self.pc} para {next_pc}")
                # Inicia nova especulação para o target
                self.speculation_manager.start_speculation(self.pc, next_pc)
            else:
                # Predição "não tomado" - continua sequencialmente
                next_pc = self.pc + 1
                print(f"Predição: Desvio não tomado no PC {self.pc}, próximo PC: {next_pc}")
                # Inicia especulação para o path "não tomado"
                self.speculation_manager.start_speculation(self.pc, next_pc)

        # CORREÇÃO: Determina se a instrução ATUAL é especulativa
        # - Desvios em si não são especulativos, eles CRIAM especulação
        # - Instruções normais são especulativas se já estamos em modo especulativo
        if instruction.type in [InstructionType.BEQ, InstructionType.BNE]:
            # Desvios são especulativos apenas se já estávamos especulando
            is_speculative = is_speculative_before
        else:
            # Instruções normais: especulativas se estamos em modo especulativo
            # (isso inclui instruções após desvios)
            is_speculative = (self.enable_speculation and 
                            self.speculation_manager.is_speculative())

        # Atualiza status da instrução
        if self.pc < len(self.instruction_status):
            self.instruction_status[self.pc]['issue'] = self.cycle
            if is_speculative:
                self.instruction_status[self.pc]['speculative'] = True
                self.metrics["speculative_instructions"] += 1

        # Adiciona entrada no ROB
        rob_index = self.reorder_buffer.add_entry(
            instruction, instruction.dest, speculative=is_speculative
        )

        # Adiciona à lista de instruções especulativas se necessário
        if is_speculative:
            self.speculation_manager.add_speculative_instruction(
                instruction, self.pc, rob_index
            )

        # Configura estação de reserva
        station.busy = True
        station.op = instruction.type
        station.instruction = instruction
        station.remaining_cycles = instruction.latency + 1
        station.rob_index = rob_index
        station.pc = self.pc
        station.branch_prediction = branch_prediction
        station.speculative = is_speculative

        self._configure_operands(station, instruction)

        if instruction.dest and instruction.type not in [InstructionType.ST, InstructionType.BEQ, InstructionType.BNE]:
            self.register_status.set_status(instruction.dest, station.name)

        old_pc = self.pc
        self.pc = next_pc

        print(f"Issue: PC {old_pc} -> {self.pc}, instrução: {instruction} (especulativa: {is_speculative})")
        return True

    def _configure_operands(self, station, instruction):
        """Configura operandos incluindo para desvios"""
        if instruction.type == InstructionType.LD:
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
            
        elif instruction.type == InstructionType.ST:
            base = self.register_status.get_value(instruction.src1) if instruction.src1 else 0
            station.a = base + (instruction.immediate or 0)
            
            if self.register_status.is_ready(instruction.dest):
                station.vj = self.register_status.get_value(instruction.dest)
            else:
                station.qj = self.register_status.get_status(instruction.dest)

        elif instruction.type in [InstructionType.BEQ, InstructionType.BNE]:
            # Para desvios, configura os operandos para comparação
            if instruction.src1:
                if self.register_status.is_ready(instruction.src1):
                    station.vj = self.register_status.get_value(instruction.src1)
                else:
                    station.qj = self.register_status.get_status(instruction.src1)
            
            if instruction.src2:
                if self.register_status.is_ready(instruction.src2):
                    station.vk = self.register_status.get_value(instruction.src2)
                else:
                    station.qk = self.register_status.get_status(instruction.src2)

        # Para outras instruções aritméticas
        elif instruction.src1:
            if self.register_status.is_ready(instruction.src1):
                station.vj = self.register_status.get_value(instruction.src1)
            else:
                station.qj = self.register_status.get_status(instruction.src1)

        if instruction.src2 and instruction.type not in [InstructionType.BEQ, InstructionType.BNE]:
            if self.register_status.is_ready(instruction.src2):
                station.vk = self.register_status.get_value(instruction.src2)
            else:
                station.qk = self.register_status.get_status(instruction.src2)

    def execute(self):
        """Executa operações nas estações de reserva"""
        avancou = False
        
        for name, station in self.reservation_stations.get_all_stations().items():
            if station.busy:
                # Marca execução no status
                if station.remaining_cycles == station.instruction.latency:
                    for instr_status in self.instruction_status:
                        if (instr_status['instruction'] == str(station.instruction) and
                            not instr_status['execute']):
                            instr_status['execute'] = self.cycle
                            break

                if station.remaining_cycles > 0:
                    station.remaining_cycles -= 1

                # Executa quando pronto
                if (station.remaining_cycles == 0 and 
                    station.qj is None and station.qk is None):
                    
                    result = self._execute_operation(station)
                    
                    # Para desvios, resolve predição
                    if (station.instruction.type in [InstructionType.BEQ, InstructionType.BNE] and
                        self.enable_speculation and hasattr(station, 'branch_prediction')):
                        
                        self._resolve_branch(station, result)
                    
                    # Propaga resultado
                    self.reservation_stations.update_stations(station.name, result)
                    
                    # Atualiza ROB
                    if hasattr(station, 'rob_index'):
                        self.reorder_buffer.update_entry(station.rob_index, result)
                    
                    # Marca write result
                    for instr_status in self.instruction_status:
                        if (instr_status['instruction'] == str(station.instruction) and
                            not instr_status['write_result']):
                            instr_status['write_result'] = self.cycle
                            break
                    
                    # Limpa estação
                    self._clear_station(station)
                    avancou = True
        
        return avancou

    def _resolve_branch(self, station, result):
        """Resolve predição de desvio - VERSÃO CORRIGIDA"""
        instruction = station.instruction
        prediction = station.branch_prediction

        if not prediction:
            return  # Não é um desvio com predição

        print(f"Resolvendo desvio no PC {station.pc}: resultado={result}")

        # CORREÇÃO: Determina resultado real baseado no tipo de desvio
        if instruction.type == InstructionType.BEQ:
            actual_taken = (result == 1)  # BEQ: toma desvio se valores são iguais (resultado=1)
        elif instruction.type == InstructionType.BNE:
            actual_taken = (result == 1)  # BNE: toma desvio se valores são diferentes (resultado=1)
        else:
            actual_taken = False

        # CORREÇÃO: Cálculo correto dos endereços
        if actual_taken:
            actual_target = station.pc + 1 + (instruction.immediate or 0)
        else:
            actual_target = station.pc + 1  # Próxima instrução sequencial

        # CORREÇÃO: Recalcula o que deveria ter sido predito
        predicted_taken = prediction.taken
        if predicted_taken:
            predicted_target = station.pc + 1 + (instruction.immediate or 0)
        else:
            predicted_target = station.pc + 1

        print(f"Real: tomado={actual_taken}, target={actual_target}")
        print(f"Predito: tomado={predicted_taken}, target={predicted_target}")

        # Verifica misprediction
        mispredicted = self.speculation_manager.resolve_branch(
            station.pc, actual_taken, actual_target,
            predicted_taken, predicted_target
        )

        # Atualiza preditor
        self.branch_predictor.update(
            station.pc, actual_taken, actual_target, prediction
        )

        if mispredicted:
            print(f"*** MISPREDICTION detectada no PC {station.pc} ***")
            self.metrics["mispredictions"] += 1
            self._handle_misprediction(station.pc, actual_target)
        else:
            print(f"Predição correta no PC {station.pc}")

    def _handle_misprediction(self, branch_pc: int, correct_target: int):
        """Trata misprediction fazendo flush das instruções especulativas"""
        print(f"Fazendo flush de instruções especulativas após PC {branch_pc}")
        print(f"PC correto: {correct_target}")

        # Flush instruções especulativas
        flushed_indices = self.speculation_manager.flush_speculative_instructions(branch_pc)
        print(f"Flushed {len(flushed_indices)} instruções especulativas")

        # Remove entradas do ROB
        for rob_index in flushed_indices:
            self.reorder_buffer.flush_entry(rob_index)

        # Marca instruções como flushed no status
        for instr_status in self.instruction_status:
            if instr_status['pc'] > branch_pc and instr_status.get('speculative', False):
                instr_status['flushed'] = True
                print(f"Marcando instrução no PC {instr_status['pc']} como flushed")

        # Limpa estações de reserva especulativas
        flushed_stations = self.reservation_stations.flush_speculative_stations(branch_pc)
        print(f"Limpas {len(flushed_stations)} estações especulativas")

        # CRÍTICO: Restaura PC correto
        old_pc = self.pc
        self.pc = correct_target
        print(f"PC restaurado de {old_pc} para {self.pc}")

        self.recovering_from_misprediction = True

    def _flush_speculative_stations(self, branch_pc: int):
        """Remove instruções especulativas das estações de reserva"""
        for station in self.reservation_stations.get_all_stations().values():
            if (station.busy and hasattr(station, 'pc') and 
                station.pc > branch_pc):
                self._clear_station(station)

    def _clear_station(self, station):
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
        if hasattr(station, 'branch_prediction'):
            station.branch_prediction = None

    def _execute_operation(self, station) -> int:
        """Executa operação (código anterior mantido com pequenas melhorias)"""
        result = 0
        
        if station.op == InstructionType.ADD:
            result = (station.vj or 0) + (station.vk or 0)
        elif station.op == InstructionType.SUB:
            result = (station.vj or 0) - (station.vk or 0)
        elif station.op == InstructionType.MUL:
            vj = station.vj if station.vj is not None else 0
            vk = station.vk if station.vk is not None else 0
            result = vj * vk
        elif station.op == InstructionType.DIV:
            vj = station.vj if station.vj is not None else 0
            vk = station.vk if station.vk is not None else 1
            if vk == 0:
                raise ValueError("Divisão por zero detectada")
            result = vj // vk
        elif station.op == InstructionType.LD:
            result = self.memory.get(station.a, 0)
        elif station.op == InstructionType.ST:
            if station.vj is not None:
                self.memory[station.a] = station.vj
                result = station.vj
            else:
                result = 0
        elif station.op == InstructionType.BEQ:
            result = 1 if (station.vj == station.vk) else 0
        elif station.op == InstructionType.BNE:
            result = 1 if (station.vj != station.vk) else 0
            
        return result

    def get_speculation_state(self) -> Dict:
        """Retorna estado da especulação"""
        if not self.enable_speculation:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "is_speculative": self.speculation_manager.is_speculative(),
            "speculation_level": self.speculation_manager.get_speculation_level(),
            "branch_predictor_stats": self.branch_predictor.get_stats(),
            "speculation_stats": self.speculation_manager.get_stats(),
            "recovering_from_misprediction": self.recovering_from_misprediction
        }

    def get_state(self) -> Dict:
        """Retorna estado atual do processador (versão atualizada)"""
        base_state = {
            "cycle": self.cycle,
            "pc": self.pc,
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
                    "remaining_cycles": station.remaining_cycles,
                    "speculative": hasattr(station, 'branch_prediction') and station.branch_prediction is not None
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
                    "ready": entry.ready if entry else None,
                    "speculative": entry.speculative if entry else False,
                    "branch_mispredicted": entry.branch_mispredicted if entry else False
                }
                for entry in self.reorder_buffer.get_all_entries()
            ],
            "is_finished": self.is_finished
        }
        
        # Adiciona estado de especulação se habilitado
        if self.enable_speculation:
            base_state["speculation"] = self.get_speculation_state()
        
        return base_state
    
    def commit(self):
        """Tenta fazer commit de uma instrução"""
        if self.reorder_buffer.is_empty():
            return False
        
        # Limpa entradas flushed primeiro
        self.reorder_buffer.cleanup_flushed()
        
        if self.reorder_buffer.is_empty():
            return False
            
        entry = self.reorder_buffer.commit()
        if entry:
            # Marca que a instrução foi commitada
            for instr_status in self.instruction_status:
                if (instr_status['instruction'] == str(entry.instruction) and
                    not instr_status['commit']):
                    instr_status['commit'] = self.cycle
                    break

            print(f"Commitando instrução: {entry.instruction}")
            
            # Para desvios, não precisa fazer nada especial aqui
            # A resolução já foi feita na fase de execução
            
            if entry.destination and entry.value is not None:
                self.register_status.update_on_commit(entry.destination, entry.value)
            
            self.metrics["committed_instructions"] += 1
            
            # Se estava se recuperando de misprediction, pode parar agora
            if self.recovering_from_misprediction:
                self.recovering_from_misprediction = False
                
            return True
        
        return False

    def step(self) -> bool:
        """Executa um ciclo do processador"""
        if self.is_finished:
            return False

        self.cycle += 1
        self.metrics["total_cycles"] += 1

        # Debug menos verboso - só a cada 10 ciclos
        if self.cycle % 10 == 1:
            print(f"\n=== Ciclo {self.cycle} ===")
            print(f"PC atual: {self.pc}")

        # Fase 1: Issue
        issued = self.issue()

        # Fase 2: Execute
        executed = self.execute()

        # Fase 3: Commit
        committed = self.commit()

        # Detecta ciclos de bolha
        if not (issued or executed or committed) and not self.is_program_finished():
            self.metrics["bubble_cycles"] += 1
            
            # Debug a cada 10 bolhas
            if self.metrics["bubble_cycles"] % 10 == 0:
                print(f"Ciclo de bolha #{self.metrics['bubble_cycles']}")
                
            # Prevenção de deadlock
            if self.metrics["bubble_cycles"] > 50:
                print("ALERTA: Muitos ciclos de bolha. Verificando estado...")
                self.debug_state()
                
            if self.metrics["bubble_cycles"] > 100:
                print("Forçando conclusão devido a deadlock.")
                self.is_finished = True
                return False

        # Verifica se o programa terminou
        self.is_finished = self.is_program_finished()

        return not self.is_finished

    def debug_speculation_state(self):
        """Debug do estado de especulação"""
        if not self.enable_speculation:
            return
            
        spec_state = self.get_speculation_state()
        print(f"\n=== Debug Especulação (Ciclo {self.cycle}) ===")
        print(f"Nível de especulação: {spec_state['speculation_level']}")
        print(f"Recuperando de misprediction: {spec_state['recovering_from_misprediction']}")
        print(f"Instruções especulativas no ROB: {self.reorder_buffer.get_speculative_count()}")
        print(f"Estações especulativas: {self.reservation_stations.get_speculative_count()}")
        
        bp_stats = spec_state['branch_predictor_stats']
        print(f"Precisão do preditor: {bp_stats['accuracy']:.2%}")
        print(f"Taxa de hit BTB: {bp_stats['btb_hit_rate']:.2%}")
        print(f"Mispredictions: {bp_stats['mispredictions']}")

    def is_program_finished(self) -> bool:
        """Verifica se o programa terminou - versão simplificada"""
        # SePC chegou ao fim das instruções
        if self.pc >= len(self.instructions):
            # Verifica se todas as estações estão livres
            for station in self.reservation_stations.get_all_stations().values():
                if station.busy:
                    return False
            
            # Verifica se ROB está vazio
            self.reorder_buffer.cleanup_flushed()
            if not self.reorder_buffer.is_empty():
                return False
            
            return True

        return False

    def get_metrics(self) -> Dict:
        """Retorna métricas de desempenho"""
        base_metrics = {
            **self.metrics,
            "ipc": (self.metrics["committed_instructions"] / self.metrics["total_cycles"] 
                if self.metrics["total_cycles"] > 0 else 0)
        }
        
        if self.enable_speculation:
            spec_stats = self.speculation_manager.get_stats()
            bp_stats = self.branch_predictor.get_stats()
            
            base_metrics.update({
                "branch_prediction_accuracy": bp_stats['accuracy'],
                "btb_hit_rate": bp_stats['btb_hit_rate'],
                "speculative_instructions_issued": spec_stats['speculative_instructions_issued'],
                "speculative_instructions_flushed": spec_stats['speculative_instructions_flushed'],
                "speculation_efficiency": (
                    (spec_stats['speculative_instructions_issued'] - 
                    spec_stats['speculative_instructions_flushed']) / 
                    spec_stats['speculative_instructions_issued']
                    if spec_stats['speculative_instructions_issued'] > 0 else 1.0
                )
            })
        
        return base_metrics

    def reset_speculation(self):
        """Reset completo do sistema de especulação"""
        if self.enable_speculation:
            self.branch_predictor = BranchPredictor()
            self.speculation_manager = SpeculationManager()
            self.recovering_from_misprediction = False
            self.pending_branch_resolutions = []

    def get_branch_predictor_state(self) -> Dict:
        """Retorna estado detalhado do preditor de desvios"""
        if not self.enable_speculation:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "btb_entries": len(self.branch_predictor.btb),
            "btb_size": self.branch_predictor.btb_size,
            "global_history": bin(self.branch_predictor.global_history),
            "pattern_table_size": self.branch_predictor.pattern_table_size,
            "stats": self.branch_predictor.get_stats(),
            "btb_contents": [
                {
                    "pc": pc,
                    "target": entry.target,
                    "state": entry.prediction_state.name,
                    "last_outcome": entry.last_outcome
                }
                for pc, entry in self.branch_predictor.btb.items()
                if entry.valid
            ]
        }
    
    def debug_state(self):
        """Debug melhorado do estado atual"""
        print(f"\n=== DEBUG Estado (Ciclo {self.cycle}) ===")
        print(f"PC: {self.pc}/{len(self.instructions)}")
        print(f"Instruções commitadas: {self.metrics['committed_instructions']}/{self.metrics['total_instructions']}")
        print(f"IPC: {self.metrics['committed_instructions'] / self.metrics['total_cycles'] if self.metrics['total_cycles'] > 0 else 0:.3f}")
        print(f"Ciclos de bolha: {self.metrics['bubble_cycles']}")

        # Estado das estações
        busy_stations = []
        for name, station in self.reservation_stations.get_all_stations().items():
            if station.busy:
                busy_stations.append(f"{name}({station.op.value if station.op else 'None'}, cycles={station.remaining_cycles})")

        print(f"Estações ocupadas: {busy_stations}")

        # Estado do ROB
        rob_count = sum(1 for entry in self.reorder_buffer.entries if entry and not entry.flushed)
        print(f"Entradas no ROB: {rob_count}/{self.reorder_buffer.size}")

        if self.enable_speculation:
            print(f"Nível de especulação: {self.speculation_manager.get_speculation_level()}")
            print(f"Recuperando de misprediction: {self.recovering_from_misprediction}")