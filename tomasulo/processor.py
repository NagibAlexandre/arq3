from typing import List, Optional, Dict
from .instructions import Instruction, InstructionType, InstructionFactory
from .reservation_station import ReservationStations
from .register_status import RegisterStatus
from .reorder_buffer import ReorderBuffer
from .branch_predictor import BranchPredictor, BranchPrediction
from .speculation_manager import SpeculationManager

class TomasuloProcessor:
    def __init__(self, latencies=None, n_add=3, n_mul=3, n_mem=2, enable_speculation=True, max_issue_per_cycle=4):
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
        
        # DESPACHO FORA DE ORDEM: Lista de instruções pendentes para despacho
        self.pending_instructions = []  # Lista de índices de instruções pendentes
        self.issued_instructions = set()  # Conjunto de instruções já despachadas
        
        # Controle de paralelismo do despacho
        self.max_issue_per_cycle = max_issue_per_cycle
        
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
        self.renames_log = []  # Log de renomeações do ciclo

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
        
        # DESPACHO FORA DE ORDEM: Inicializa lista de instruções pendentes
        self.pending_instructions = list(range(len(self.instructions)))
        self.issued_instructions = set()
        
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
        
        # Mantém configuração de paralelismo
        self.max_issue_per_cycle = getattr(self, 'max_issue_per_cycle', 4)
        
        if self.enable_speculation:
            self.branch_predictor = BranchPredictor()
            self.speculation_manager = SpeculationManager()
        
        self.memory[0] = 10
        self.memory[4] = 20

   
    def issue(self) -> bool:
        """Tenta emitir uma nova instrução com despacho fora de ordem e especulação"""
        if not self.pending_instructions:
            return False

        # Verifica se PC está além do programa
        if self.pc >= len(self.instructions):
            print(f"PC {self.pc} está além do fim do programa ({len(self.instructions)} instruções)")
            return False

        issued_any = False
        issued_count = 0

        # Cria cópia da lista para evitar modificação durante iteração
        pending_copy = self.pending_instructions.copy()

        for pc in pending_copy:
            # Não emitir instruções além do programa
            if pc >= len(self.instructions):
                print(f"Removendo PC {pc} da lista pendente (além do programa)")
                if pc in self.pending_instructions:
                    self.pending_instructions.remove(pc)
                continue
                
            # Verifica limite de instruções por ciclo
            if issued_count >= self.max_issue_per_cycle:
                break
                
            if pc in self.issued_instructions:
                continue
            
            # CORREÇÃO: Verificar se instrução foi pulada por branch
            if self.instruction_status[pc].get('flushed', False):
                if pc in self.pending_instructions:
                    self.pending_instructions.remove(pc)
                continue
                
            instruction = self.instructions[pc]
            
            # Verifica se já foi emitida
            if self.instruction_status[pc]['issue']:
                self.issued_instructions.add(pc)
                continue
                
            # Verifica disponibilidade de estação de reserva
            station = self.reservation_stations.get_available_station(instruction)
            if station is None:
                continue
                
            # Verifica se ROB tem espaço
            if self.reorder_buffer.is_full():
                continue
            
            # Verifica se pode emitir (não está em flush)
            if self.recovering_from_misprediction and pc <= getattr(self, 'flush_point', -1):
                continue
                
            # DETECÇÃO DE DEPENDÊNCIAS E RENOMEAÇÃO
            dep_type = self._check_dependencies(pc, instruction, return_type=True)
            old_phys = None
            
            if dep_type:
                old_phys = self.register_status.allocate_physical(instruction.dest)
                msg = f"PC {pc}: {instruction.dest} - {old_phys} → {self.register_status.get_physical(instruction.dest)} ({dep_type})"
                self.renames_log.append(msg)
                print(f"Renomeação: PC {pc}, {instruction.dest}: {dep_type}")
            
            # Determinação de especulação
            is_speculative = self._is_instruction_speculative(pc)
            
            # CORREÇÃO: PREDIÇÃO DE DESVIO COM CÁLCULO CORRETO
            branch_prediction = None
            next_pc = pc + 1
            will_start_speculation = False
            
            if (self.enable_speculation and 
                instruction.type in [InstructionType.BEQ, InstructionType.BNE]):
                
                branch_prediction = self.branch_predictor.predict(pc, instruction.type.value)
                
                if branch_prediction.taken:
                    # CORREÇÃO: Cálculo correto do target
                    target_offset = instruction.immediate if instruction.immediate is not None else 0
                    next_pc = pc + 1 + target_offset  # Fórmula correta
                    print(f"Predição TOMADO: PC {pc} -> {next_pc}")
                    
                    # CORREÇÃO: Atualizar a predição com o target correto
                    branch_prediction.target = next_pc
                else:
                    next_pc = pc + 1
                    print(f"Predição NÃO TOMADO: PC {pc} -> {next_pc}")
                
                # Sempre inicia especulação após um branch (predição pode estar errada)
                will_start_speculation = True
            
            # Status de especulação da instrução atual
            if is_speculative:
                print(f"Instrução PC {pc} ({instruction}) MARCADA COMO ESPECULATIVA <<<")
            else:
                print(f"Instrução PC {pc} ({instruction}) NÃO É ESPECULATIVA <<<")
            
            # EMISSÃO DA INSTRUÇÃO
            self.instruction_status[pc]['issue'] = self.cycle
            
            # Marca como especulativa se necessário
            if is_speculative:
                self.instruction_status[pc]['speculative'] = True
                self.metrics["speculative_instructions"] += 1
            
            # Adiciona ao ROB
            rob_index = self.reorder_buffer.add_entry(
                instruction, instruction.dest, speculative=is_speculative
            )
            
            # Salva o físico antigo na entrada do ROB se houve renomeação
            if old_phys is not None:
                self.reorder_buffer.entries[rob_index].old_phys = old_phys
            
            # Adiciona ao speculation manager se especulativa
            if is_speculative and self.enable_speculation:
                success = self.speculation_manager.add_speculative_instruction(
                    instruction, pc, rob_index
                )
                if not success:
                    print(f"ERRO: Falha ao adicionar instrução especulativa PC {pc}")
            
            # CONFIGURAÇÃO DA ESTAÇÃO DE RESERVA
            station.busy = True
            station.op = instruction.type
            station.instruction = instruction
            station.remaining_cycles = instruction.latency + 1
            station.rob_index = rob_index
            station.pc = pc
            station.branch_prediction = branch_prediction
            station.speculative = is_speculative
            
            # Configura operandos
            self._configure_operands(station, instruction)
            
            # Atualiza status do registrador de destino
            if (instruction.dest and 
                instruction.type not in [InstructionType.ST, InstructionType.BEQ, InstructionType.BNE]):
                self.register_status.set_status(instruction.dest, station.name)
            
            # Marca como emitida
            self.issued_instructions.add(pc)
            issued_any = True
            issued_count += 1
            
            print(f"Emitida: PC {pc}, {instruction}")
            
            # INICIA ESPECULAÇÃO APÓS EMITIR O DESVIO
            if will_start_speculation:
                print(f"=== INICIANDO ESPECULAÇÃO após emitir PC {pc} ===")
                print(f"Predição: {'TOMADO' if branch_prediction.taken else 'NÃO TOMADO'}")
                self.speculation_manager.start_speculation(pc, next_pc)
                
                # Atualiza PC baseado na predição
                old_pc = self.pc
                self.pc = next_pc
                print(f"PC atualizado: {old_pc} -> {self.pc}")
                
                # Limitar PC ao tamanho do programa
                if self.pc >= len(self.instructions):
                    print(f"PC {self.pc} limitado ao fim do programa {len(self.instructions)-1}")
                    self.pc = len(self.instructions)

        return issued_any


    def _check_dependencies(self, current_pc: int, instruction, return_type=False) -> bool:
        """Verifica se há dependências que requerem renomeação. Se return_type=True, retorna 'WAW', 'WAR' ou ''"""
        if not instruction.dest:
            return False if not return_type else ''
        for pc in self.issued_instructions:
            if pc >= current_pc:
                continue
            other_instruction = self.instructions[pc]
            # WAW (Write After Write) - Dependência falsa
            if (other_instruction.dest and 
                other_instruction.dest == instruction.dest and
                other_instruction.type not in [InstructionType.ST, InstructionType.BEQ, InstructionType.BNE]):
                if return_type:
                    return 'WAW'
                return True
            # WAR (Write After Read) - Antidependência
            if (other_instruction.dest and 
                other_instruction.dest in [instruction.src1, instruction.src2] and
                other_instruction.type not in [InstructionType.ST, InstructionType.BEQ, InstructionType.BNE]):
                if return_type:
                    return 'WAR'
                return True
        return False if not return_type else ''

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
            return

        print(f"Resolvendo desvio PC {station.pc}: resultado={result}")

        # Lógica de desvio
        if instruction.type == InstructionType.BEQ:
            actual_taken = (result == 1)
        elif instruction.type == InstructionType.BNE:
            actual_taken = (result == 1)
        else:
            return

        # Calcular target real
        if actual_taken:
            target_offset = instruction.immediate if instruction.immediate is not None else 0
            actual_target = station.pc + 1 + target_offset
        else:
            actual_target = station.pc + 1

        predicted_taken = prediction.taken
        predicted_target = prediction.target

        print(f"Real: tomado={actual_taken}, target={actual_target}")
        print(f"Predito: tomado={predicted_taken}, target={predicted_target}")

        # Verificação de misprediction
        mispredicted = (actual_taken != predicted_taken or 
                    (actual_taken and actual_target != predicted_target))

        # Atualizar preditor
        self.branch_predictor.update(station.pc, actual_taken, actual_target, prediction)

        # CORREÇÃO: Cancelar instruções especulativas mesmo com predição correta
        if actual_taken and actual_target > station.pc + 1:
            # Marca instruções como puladas
            self._mark_skipped_instructions(station.pc + 1, actual_target)
            
            # NOVO: Cancela instruções especulativas já emitidas no caminho errado
            self._cancel_wrong_path_instructions(station.pc + 1, actual_target)

        # Resolver no speculation manager
        if self.speculation_manager:
            spec_mispredicted = self.speculation_manager.resolve_branch(
                station.pc, actual_taken, actual_target,
                predicted_taken, predicted_target
            )
            mispredicted = mispredicted or spec_mispredicted

        if mispredicted:
            print(f"*** MISPREDICTION no PC {station.pc} ***")
            self.metrics["mispredictions"] += 1
            self._handle_misprediction(station.pc, actual_target)
        else:
            print(f"Predição correta no PC {station.pc}")


    def _mark_skipped_instructions(self, start_pc: int, end_pc: int):
        """Marca instruções como puladas mesmo com predição correta"""
        for pc in range(start_pc, end_pc):
            if pc < len(self.instructions):
                if pc in self.pending_instructions:
                    self.pending_instructions.remove(pc)
                self.instruction_status[pc]['skipped'] = True
                print(f"Instrução PC {pc} marcada como PULADA (predição correta)")

    def _cancel_wrong_path_instructions(self, start_pc: int, end_pc: int):
        """Cancela instruções já emitidas que estão no caminho errado (mesmo com predição correta)"""
        print(f"Cancelando instruções no caminho errado: PC {start_pc} até {end_pc-1}")

        instructions_to_cancel = []

        # Encontra instruções emitidas que estão no caminho errado
        for pc in self.issued_instructions.copy():
            if start_pc <= pc < end_pc:
                instructions_to_cancel.append(pc)

        if not instructions_to_cancel:
            return

        print(f"Instruções a cancelar: {instructions_to_cancel}")

        # Cancela as instruções
        for pc in instructions_to_cancel:
            # Remove das instruções emitidas
            self.issued_instructions.remove(pc)
            
            # Marca como cancelada
            self.instruction_status[pc]['flushed'] = True
            self.instruction_status[pc]['cancelled_by_correct_branch'] = True
            
            print(f"Cancelando instrução PC {pc} (estava no caminho errado)")
            
            # Remove da estação de reserva se ainda estiver lá
            for name, station_obj in self.reservation_stations.get_all_stations().items():
                if (station_obj.busy and 
                    hasattr(station_obj, 'pc') and 
                    station_obj.pc == pc):
                    print(f"Removendo PC {pc} da estação {name}")
                    self._clear_station(station_obj)
                    break
            
            # Marca entrada do ROB como flushed
            for i, entry in enumerate(self.reorder_buffer.entries):
                if entry and not entry.flushed:
                    # Encontra a instrução correspondente
                    for instr_pc, instr in enumerate(self.instructions):
                        if (str(instr) == str(entry.instruction) and 
                            instr_pc == pc):
                            entry.flushed = True
                            print(f"Marcando ROB entry {i} como flushed (PC {pc})")
                            break



    def _handle_misprediction(self, branch_pc: int, correct_target: int):
        """Trata misprediction fazendo flush das instruções especulativas"""
        print(f"*** MISPREDICTION DETECTADA ***")
        print(f"*** FLUSH: Branch PC {branch_pc} -> Target correto {correct_target} ***")

        self.flush_point = branch_pc
        flushed_count = 0
        instructions_to_flush = []

        # CORREÇÃO: Determinar quais instruções devem ser flushed
        for pc in list(self.issued_instructions):
            should_flush = False
            
            # CASO 1: Instruções no caminho especulativo errado (entre branch+1 e target correto)
            if pc > branch_pc and pc < correct_target:
                should_flush = True
                print(f"Flushing instrução PC {pc} (no caminho especulativo errado - deveria ser pulada)")
            
            # CASO 2: Instruções emitidas especulativamente após o branch
            elif pc > branch_pc:
                if self.instruction_status[pc].get('speculative', False):
                    should_flush = True
                    print(f"Flushing instrução especulativa PC {pc}")
            
            if should_flush:
                instructions_to_flush.append(pc)
                self.instruction_status[pc]['flushed'] = True
                self.issued_instructions.remove(pc)
                flushed_count += 1

        # Flush estações de reserva
        flushed_stations = 0
        for name, station in self.reservation_stations.get_all_stations().items():
            if (station.busy and 
                hasattr(station, 'pc') and 
                station.pc in instructions_to_flush):
                
                print(f"Flushing estação {name} com PC {station.pc}")
                self._clear_station(station)
                flushed_stations += 1

        # Flush entradas do ROB
        rob_flushed = 0
        flushed_rob_indices = []
        for i, entry in enumerate(self.reorder_buffer.entries):
            if entry and not entry.flushed:
                # Encontra PC da instrução
                for instr_pc, instr in enumerate(self.instructions):
                    if (str(instr) == str(entry.instruction) and 
                        instr_pc in instructions_to_flush):
                        entry.flushed = True
                        flushed_rob_indices.append(i)
                        rob_flushed += 1
                        print(f"Flushing ROB entry {i} com PC {instr_pc}")
                        break

        # Flush speculation manager
        if self.speculation_manager:
            spec_flushed = self.speculation_manager.flush_speculative_instructions(branch_pc)
            print(f"Speculation manager flushed {len(spec_flushed)} instruções")

        # CORREÇÃO: Reconstruir pending_instructions corretamente
        self.pending_instructions = []
        for i in range(len(self.instructions)):
            # Adiciona instruções que ainda não foram processadas
            is_not_issued = i not in self.issued_instructions
            is_not_flushed = not self.instruction_status[i].get('flushed', False)
            is_not_committed = not self.instruction_status[i].get('commit', False)
            
            if is_not_issued and is_not_flushed and is_not_committed:
                self.pending_instructions.append(i)

        # CORREÇÃO: Marcar instruções puladas pelo branch como não executáveis
        if correct_target > branch_pc + 1:
            for pc in range(branch_pc + 1, correct_target):
                if pc < len(self.instructions):
                    # Remove das pendentes se estiver lá
                    if pc in self.pending_instructions:
                        self.pending_instructions.remove(pc)
                    # Marca como pulada (mas não flushed, pois nunca foi emitida)
                    self.instruction_status[pc]['skipped'] = True
                    print(f"Instrução PC {pc} marcada como PULADA pelo branch")

        # Restaurar PC correto
        old_pc = self.pc
        self.pc = correct_target

        print(f"Flushed {flushed_count} instruções, {flushed_stations} estações, {rob_flushed} ROB entries")
        print(f"PC: {old_pc} -> {self.pc}")
        print(f"Pending instructions: {self.pending_instructions}")
        print(f"ROB indices flushed: {flushed_rob_indices}")

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
                    "speculative": getattr(station, 'speculative', False),
                    "pc": getattr(station, 'pc', None)
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
                    "branch_mispredicted": entry.branch_mispredicted if entry else False,
                    "flushed": entry.flushed if entry else False,
                    "rob_index": i  # Adicionar índice do ROB
                }
                for i, entry in enumerate(self.reorder_buffer.get_all_entries())
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
        self.reorder_buffer.cleanup_flushed()
        if self.reorder_buffer.is_empty():
            return False
        entry = self.reorder_buffer.commit()
        if entry:
            for instr_status in self.instruction_status:
                if (instr_status['instruction'] == str(entry.instruction) and not instr_status['commit']):
                    instr_status['commit'] = self.cycle
                    break
            print(f"Commitando instrução: {entry.instruction}")
            # Para desvios, não precisa fazer nada especial aqui
            # A resolução já foi feita na fase de execução
            if entry.destination and entry.value is not None:
                self.register_status.update_on_commit(entry.destination, entry.value)
                # RENOMEAÇÃO FÍSICA: libera físico antigo
                if hasattr(entry, 'old_phys') and entry.old_phys is not None:
                    self.register_status.free_physical(entry.old_phys)
            self.metrics["committed_instructions"] += 1
            if self.recovering_from_misprediction:
                self.recovering_from_misprediction = False
            return True
        return False

    def step(self) -> bool:
        """Executa um ciclo do processador"""
        self.renames_log = []  # Limpa log de renomeações a cada ciclo

        if self.is_finished:
            return False

        self.cycle += 1
        self.metrics["total_cycles"] += 1

        # Debug menos verboso - só a cada 10 ciclos ou quando há atividade
        debug_this_cycle = (self.cycle % 10 == 1 or 
                        self.metrics["bubble_cycles"] % 10 == 1)

        if debug_this_cycle:
            print(f"\n=== Ciclo {self.cycle} ===")
            print(f"PC atual: {self.pc}")

        # Fase 1: Issue
        issued = self.issue()

        # Fase 2: Execute
        executed = self.execute()

        # Fase 3: Commit
        committed = self.commit()

        # Detecta ciclos de bolha
        if not (issued or executed or committed):
            if not self.is_program_finished():
                self.metrics["bubble_cycles"] += 1
                
                # Debug a cada 10 bolhas
                if self.metrics["bubble_cycles"] % 10 == 0:
                    print(f"Ciclo de bolha #{self.metrics['bubble_cycles']}")
                    self.debug_state()
                
                # CORREÇÃO: Reduzir limite de deadlock
                if self.metrics["bubble_cycles"] > 20:
                    print("ALERTA: Muitos ciclos de bolha. Verificando estado...")
                    self.debug_state()
                    
                    # Verifica se realmente terminou
                    if self.is_program_finished():
                        print("Programa realmente terminou - finalizando")
                        self.is_finished = True
                        return False
                    
                if self.metrics["bubble_cycles"] > 30:
                    print("Forçando conclusão devido a possível deadlock.")
                    self.is_finished = True
                    return False
            else:
                # Programa terminou naturalmente
                print("Programa terminou naturalmente")
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
        """Verifica se o programa terminou - versão corrigida"""

        # Debug do estado atual
        print(f"\n=== Verificando fim do programa (Ciclo {self.cycle}) ===")
        print(f"PC atual: {self.pc}")
        print(f"Total de instruções: {len(self.instructions)}")
        print(f"Instruções emitidas: {len(self.issued_instructions)}/{len(self.instructions)}")
        print(f"Instruções commitadas: {self.metrics['committed_instructions']}")

        # Verifica se todas as instruções foram commitadas
        if self.metrics['committed_instructions'] >= len(self.instructions):
            print("Todas as instruções foram commitadas")
            return True

        # CORREÇÃO: Contar apenas instruções válidas (não flushed e não puladas)
        valid_instructions = 0
        for i, instr_status in enumerate(self.instruction_status):
            is_flushed = instr_status.get('flushed', False)
            is_skipped = instr_status.get('skipped', False)
            is_committed = instr_status.get('commit', False)
            
            if not is_flushed and not is_skipped:
                valid_instructions += 1
            elif is_committed:
                # Instruções commitadas contam mesmo se foram flushed/skipped depois
                valid_instructions += 1

        print(f"Instruções válidas (não flushed/skipped): {valid_instructions}")

        # Verifica se todas as instruções válidas foram processadas
        if self.metrics['committed_instructions'] >= valid_instructions:
            # Verifica se todas as estações estão livres
            busy_stations = []
            for name, station in self.reservation_stations.get_all_stations().items():
                if station.busy:
                    busy_stations.append(f"{name}(PC:{getattr(station, 'pc', 'N/A')})")
            
            print(f"Estações ocupadas: {busy_stations}")
            
            if not busy_stations:
                # Verifica se ROB está vazio
                self.reorder_buffer.cleanup_flushed()
                rob_entries = sum(1 for entry in self.reorder_buffer.entries 
                                if entry and not entry.flushed)
                print(f"Entradas no ROB: {rob_entries}")
                
                if rob_entries == 0:
                    print("Programa finalizado - todas as estruturas estão vazias")
                    return True

        print("Programa ainda em execução")
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
        print(f"Instruções emitidas: {len(self.issued_instructions)}/{len(self.instructions)}")
        print(f"Instruções pendentes: {len(self.pending_instructions) - len(self.issued_instructions)}")
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


    def _is_instruction_speculative(self, pc: int) -> bool:
        """Determina se uma instrução deve ser marcada como especulativa"""
        if not self.enable_speculation:
            return False

        # Se já estamos em modo especulativo, a instrução é especulativa
        if self.speculation_manager.is_speculative():
            return True

        # CORREÇÃO: Verifica se há branches emitidos mas ainda não COMMITADOS antes desta instrução
        for issued_pc in self.issued_instructions:
            if issued_pc < pc:
                issued_instr = self.instructions[issued_pc]
                if issued_instr.type in [InstructionType.BEQ, InstructionType.BNE]:
                    # CORREÇÃO: Verifica se este branch ainda não foi COMMITADO (não apenas resolvido)
                    if not self.instruction_status[issued_pc].get('commit', False):
                        print(f"Instrução PC {pc} é especulativa devido ao branch não commitado PC {issued_pc}")
                        return True

        return False


    def _is_branch_unresolved(self, branch_pc: int) -> bool:
        """Verifica se um branch ainda não foi resolvido"""
        # Verifica se está em alguma estação de reserva
        for station in self.reservation_stations.get_all_stations().values():
            if (station.busy and 
                hasattr(station, 'pc') and 
                station.pc == branch_pc and
                station.instruction.type in [InstructionType.BEQ, InstructionType.BNE]):
                return True

        # Verifica se está no ROB mas ainda não foi commitado
        for entry in self.reorder_buffer.entries:
            if (entry and not entry.flushed and 
                entry.instruction.type in [InstructionType.BEQ, InstructionType.BNE]):
                # Encontra o PC desta instrução
                for i, instr in enumerate(self.instructions):
                    if str(instr) == str(entry.instruction) and i == branch_pc:
                        return not self.instruction_status[i].get('commit', False)

        return False