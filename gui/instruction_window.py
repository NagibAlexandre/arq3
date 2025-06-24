from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                         QTableWidget, QTableWidgetItem, QLabel, QPushButton,
                         QGroupBox, QHeaderView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class InstructionStatusWindow(QMainWindow):
    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Status das Instruções')
        self.setGeometry(200, 200, 1000, 600)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Informações gerais
        info_group = QGroupBox("Informações Gerais")
        info_layout = QHBoxLayout()
        
        self.cycle_label = QLabel("Ciclo: 0")
        self.pc_label = QLabel("PC: 0")
        self.committed_label = QLabel("Commitadas: 0/0")
        self.speculative_label = QLabel("Especulativas: 0")
        
        info_layout.addWidget(self.cycle_label)
        info_layout.addWidget(self.pc_label)
        info_layout.addWidget(self.committed_label)
        info_layout.addWidget(self.speculative_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Legenda
        legend_group = QGroupBox("Legenda")
        legend_layout = QHBoxLayout()
        
        legend_items = [
            ("⚪️ Não emitida", QColor(255, 255, 255)),
            ("🔵 Emitida", QColor(173, 216, 230)),
            ("🟡 Especulativa", QColor(255, 255, 0)),
            ("🟤 Executando", QColor(205, 133, 63)),
            ("🔴 Flushed/Cancelada", QColor(255, 182, 193)),
            ("⚫ Pulada", QColor(128, 128, 128)),
            ("✅ Commitada", QColor(152, 251, 152))
        ]
        
        for text, color in legend_items:
            label = QLabel(text)
            label.setStyleSheet(f"background-color: {color.name()}; padding: 5px; margin: 2px; border-radius: 3px;")
            legend_layout.addWidget(label)
        
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)

        # Tabela de status das instruções
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(8)
        self.status_table.setHorizontalHeaderLabels([
            "PC", "Instrução", "Issue", "Execute", "Write Result", "Commit", "Status", "Observações"
        ])
        
        # Ajustar largura das colunas
        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.status_table)

        # Botão de atualização
        update_btn = QPushButton("Atualizar")
        update_btn.clicked.connect(self.update_status)
        layout.addWidget(update_btn)

    def update_status(self):
        """Atualiza o status das instruções"""
        if not self.processor or not hasattr(self.processor, 'instruction_status'):
            return

        # Atualizar informações gerais
        state = self.processor.get_state()
        self.cycle_label.setText(f"Ciclo: {state['cycle']}")
        self.pc_label.setText(f"PC: {state['pc']}")
        self.committed_label.setText(f"Commitadas: {state['metrics']['committed_instructions']}/{state['metrics']['total_instructions']}")
        
        # Contar instruções especulativas
        speculative_count = sum(1 for status in self.processor.instruction_status 
                            if status.get('speculative', False) and not status.get('flushed', False))
        self.speculative_label.setText(f"Especulativas: {speculative_count}")

        # Configurar tabela
        instruction_status = self.processor.instruction_status
        self.status_table.setRowCount(len(instruction_status))

        for i, status in enumerate(instruction_status):
            # PC
            pc_item = QTableWidgetItem(str(i))
            self.status_table.setItem(i, 0, pc_item)

            # Instrução
            instr_item = QTableWidgetItem(status['instruction'])
            self.status_table.setItem(i, 1, instr_item)

            # Issue
            issue_item = QTableWidgetItem(str(status['issue']) if status['issue'] else "-")
            self.status_table.setItem(i, 2, issue_item)

            # Execute
            execute_item = QTableWidgetItem(str(status['execute']) if status['execute'] else "-")
            self.status_table.setItem(i, 3, execute_item)

            # Write Result
            write_item = QTableWidgetItem(str(status['write_result']) if status['write_result'] else "-")
            self.status_table.setItem(i, 4, write_item)

            # Commit
            commit_item = QTableWidgetItem(str(status['commit']) if status['commit'] else "-")
            self.status_table.setItem(i, 5, commit_item)

            # Determinar status e cor
            color, status_text, observations = self._get_instruction_color_and_status(status, i)

            # Status
            status_item = QTableWidgetItem(status_text)
            self.status_table.setItem(i, 6, status_item)

            # Observações
            obs_item = QTableWidgetItem(observations)
            self.status_table.setItem(i, 7, obs_item)

            # Aplicar cor a toda a linha
            for col in range(8):
                item = self.status_table.item(i, col)
                if item:
                    item.setBackground(color)

    def _get_instruction_color_and_status(self, status, pc):
        """Determina a cor e status de uma instrução baseado em seu estado"""
        
        # Verificar se foi flushed/cancelada
        if status.get('flushed', False):
            return QColor(255, 182, 193), "FLUSHED", "Cancelada por misprediction"
        
        # Verificar se foi pulada por branch
        if status.get('skipped', False):
            return QColor(128, 128, 128), "PULADA", "Pulada por branch tomado"
        
        # Verificar se foi cancelada por branch correto
        if status.get('cancelled_by_correct_branch', False):
            return QColor(255, 182, 193), "CANCELADA", "Cancelada (branch correto)"
        
        # Verificar se foi commitada
        if status.get('commit', False):
            return QColor(152, 251, 152), "COMMITADA", f"Commitada no ciclo {status['commit']}"
        
        # Verificar se está executando
        if status.get('write_result', False):
            if status.get('speculative', False):
                return QColor(255, 215, 0), "ESPECULATIVA (WR)", "Especulativa - Write Result"
            return QColor(205, 133, 63), "WRITE RESULT", f"Write Result no ciclo {status['write_result']}"
        
        if status.get('execute', False):
            if status.get('speculative', False):
                return QColor(255, 255, 0), "ESPECULATIVA (EX)", "Especulativa - Executando"
            return QColor(205, 133, 63), "EXECUTANDO", f"Executando desde ciclo {status['execute']}"
        
        # Verificar se foi emitida
        if status.get('issue', False):
            if status.get('speculative', False):
                return QColor(255, 255, 0), "ESPECULATIVA", f"Especulativa - Emitida no ciclo {status['issue']}"
            return QColor(173, 216, 230), "EMITIDA", f"Emitida no ciclo {status['issue']}"
        
        # Não foi emitida ainda
        return QColor(255, 255, 255), "PENDENTE", "Aguardando emissão"

    def closeEvent(self, event):
        """Sobrescreve o evento de fechamento"""
        event.accept()
