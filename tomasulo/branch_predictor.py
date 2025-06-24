from typing import Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

class PredictionState(Enum):
    STRONGLY_NOT_TAKEN = 0
    WEAKLY_NOT_TAKEN = 1
    WEAKLY_TAKEN = 2
    STRONGLY_TAKEN = 3

@dataclass
class BTBEntry:
    """Entrada do Branch Target Buffer"""
    valid: bool = False
    tag: int = 0
    target: int = 0
    prediction_state: PredictionState = PredictionState.WEAKLY_NOT_TAKEN
    last_outcome: bool = False

@dataclass
class BranchPrediction:
    """Resultado de uma predição de desvio"""
    taken: bool
    target: int
    confidence: float
    btb_hit: bool

class BranchPredictor:
    """Preditor de desvios com BTB e preditor de 2 bits"""

    def __init__(self, btb_size: int = 16, history_bits: int = 4):
        self.btb_size = btb_size
        self.btb: Dict[int, BTBEntry] = {}
        
        # Preditor baseado em histórico global
        self.history_bits = history_bits
        self.global_history = 0  # Histórico global de desvios
        self.pattern_table_size = 2 ** history_bits
        self.pattern_table = [PredictionState.WEAKLY_NOT_TAKEN] * self.pattern_table_size
        
        # Estatísticas
        self.stats = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'btb_hits': 0,
            'btb_misses': 0,
            'taken_correct': 0,
            'not_taken_correct': 0,
            'mispredictions': 0
        }

    def predict(self, pc: int, instruction_type: str) -> BranchPrediction:
        """Faz uma predição para um desvio"""
        self.stats['total_predictions'] += 1

        btb_entry = self.btb.get(pc)
        btb_hit = btb_entry is not None and btb_entry.valid

        if btb_hit:
            self.stats['btb_hits'] += 1
            taken = btb_entry.prediction_state in [
                PredictionState.WEAKLY_TAKEN, 
                PredictionState.STRONGLY_TAKEN
            ]
            target = btb_entry.target
            confidence = self._get_confidence(btb_entry.prediction_state)
        else:
            self.stats['btb_misses'] += 1
            # Usar preditor global
            pattern_index = self.global_history & ((1 << self.history_bits) - 1)
            prediction_state = self.pattern_table[pattern_index]
            
            # CORREÇÃO: Heurística melhorada para primeira predição
            if instruction_type == "BEQ":
                # Para BEQ, ligeiramente tendencioso para TOMADO (heurística comum)
                if prediction_state == PredictionState.WEAKLY_NOT_TAKEN:
                    taken = True  # Muda para tomado por heurística
                else:
                    taken = prediction_state in [
                        PredictionState.WEAKLY_TAKEN, 
                        PredictionState.STRONGLY_TAKEN
                    ]
            else:
                taken = prediction_state in [
                    PredictionState.WEAKLY_TAKEN, 
                    PredictionState.STRONGLY_TAKEN
                ]
            
            # Target será corrigido no issue() com o offset correto
            target = pc + 1  
            confidence = self._get_confidence(prediction_state)

        return BranchPrediction(
            taken=taken,
            target=target,
            confidence=confidence,
            btb_hit=btb_hit
        )


    def update(self, pc: int, actual_taken: bool, actual_target: int, 
            prediction: BranchPrediction):
        """Atualiza o preditor com o resultado real"""
        
        # Atualiza estatísticas
        if prediction.taken == actual_taken:
            self.stats['correct_predictions'] += 1
            if actual_taken:
                self.stats['taken_correct'] += 1
            else:
                self.stats['not_taken_correct'] += 1
        else:
            self.stats['mispredictions'] += 1
        
        # Atualiza BTB
        self._update_btb(pc, actual_taken, actual_target)
        
        # Atualiza histórico global
        self.global_history = ((self.global_history << 1) | actual_taken) & ((1 << self.history_bits) - 1)
        
        # Atualiza tabela de padrões
        pattern_index = self.global_history
        self.pattern_table[pattern_index] = self._update_prediction_state(
            self.pattern_table[pattern_index], actual_taken
        )

    def _update_btb(self, pc: int, taken: bool, target: int):
        """Atualiza entrada do BTB - VERSÃO CORRIGIDA"""
        if pc not in self.btb:
            # Se BTB está cheio, substitui entrada aleatória (política simples)
            if len(self.btb) >= self.btb_size:
                # Remove entrada mais antiga (LRU simples)
                oldest_pc = min(self.btb.keys()) if self.btb else pc
                if oldest_pc in self.btb:
                    del self.btb[oldest_pc]

            self.btb[pc] = BTBEntry()

        entry = self.btb[pc]
        entry.valid = True
        entry.tag = pc
        # CORREÇÃO: Salva o target real calculado
        entry.target = target  # Usa o target real que foi calculado na resolução
        entry.last_outcome = taken
        entry.prediction_state = self._update_prediction_state(entry.prediction_state, taken)


    def _update_prediction_state(self, current_state: PredictionState, 
                                taken: bool) -> PredictionState:
        """Atualiza estado do preditor de 2 bits"""
        if taken:
            if current_state == PredictionState.STRONGLY_NOT_TAKEN:
                return PredictionState.WEAKLY_NOT_TAKEN
            elif current_state == PredictionState.WEAKLY_NOT_TAKEN:
                return PredictionState.WEAKLY_TAKEN
            elif current_state == PredictionState.WEAKLY_TAKEN:
                return PredictionState.STRONGLY_TAKEN
            else:  # STRONGLY_TAKEN
                return PredictionState.STRONGLY_TAKEN
        else:
            if current_state == PredictionState.STRONGLY_TAKEN:
                return PredictionState.WEAKLY_TAKEN
            elif current_state == PredictionState.WEAKLY_TAKEN:
                return PredictionState.WEAKLY_NOT_TAKEN
            elif current_state == PredictionState.WEAKLY_NOT_TAKEN:
                return PredictionState.STRONGLY_NOT_TAKEN
            else:  # STRONGLY_NOT_TAKEN
                return PredictionState.STRONGLY_NOT_TAKEN

    def _get_confidence(self, state: PredictionState) -> float:
        """Retorna confiança da predição (0.0 a 1.0)"""
        if state in [PredictionState.STRONGLY_NOT_TAKEN, PredictionState.STRONGLY_TAKEN]:
            return 0.9
        else:
            return 0.6

    def get_accuracy(self) -> float:
        """Retorna precisão do preditor"""
        if self.stats['total_predictions'] == 0:
            return 0.0
        return self.stats['correct_predictions'] / self.stats['total_predictions']

    def get_stats(self) -> Dict:
        """Retorna estatísticas detalhadas"""
        return {
            **self.stats,
            'accuracy': self.get_accuracy(),
            'btb_hit_rate': (self.stats['btb_hits'] / 
                        (self.stats['btb_hits'] + self.stats['btb_misses']) 
                        if (self.stats['btb_hits'] + self.stats['btb_misses']) > 0 else 0)
        }
