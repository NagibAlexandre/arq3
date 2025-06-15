from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QLabel, QTableWidget,
                             QTableWidgetItem, QGroupBox, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from tomasulo.processor import TomasuloProcessor

class MainWindow(QMainWindow):
    def __init__(self, processor=None):
        super().__init__()
        if processor is not None:
            self.processor = processor
        else:
            from tomasulo.processor import TomasuloProcessor
            self.processor = TomasuloProcessor()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Simulador Tomasulo')
        self.setGeometry(100, 100, 1200, 800)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Painel esquerdo (programa e controles)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Área de código
        code_group = QGroupBox("Programa MIPS")
        code_layout = QVBoxLayout()
        self.code_edit = QTextEdit()
        self.code_edit.setPlaceholderText("Digite seu programa MIPS aqui...")
        code_layout.addWidget(self.code_edit)
        code_group.setLayout(code_layout)
        left_layout.addWidget(code_group)

        # Controles
        controls_group = QGroupBox("Controles")
        controls_layout = QHBoxLayout()
        self.load_btn = QPushButton("Carregar")
        self.step_btn = QPushButton("Passo")
        self.run_btn = QPushButton("Executar")
        self.reset_btn = QPushButton("Resetar")
        controls_layout.addWidget(self.load_btn)
        controls_layout.addWidget(self.step_btn)
        controls_layout.addWidget(self.run_btn)
        controls_layout.addWidget(self.reset_btn)
        controls_group.setLayout(controls_layout)
        left_layout.addWidget(controls_group)

        # Métricas
        metrics_group = QGroupBox("Métricas")
        metrics_layout = QGridLayout()
        self.cycle_label = QLabel("Ciclo: 0")
        self.ipc_label = QLabel("IPC: 0.0")
        self.bubbles_label = QLabel("Ciclos de Bolha: 0")
        self.status_label = QLabel("Status: Pronto")
        metrics_layout.addWidget(self.cycle_label, 0, 0)
        metrics_layout.addWidget(self.ipc_label, 0, 1)
        metrics_layout.addWidget(self.bubbles_label, 1, 0)
        metrics_layout.addWidget(self.status_label, 1, 1)
        metrics_group.setLayout(metrics_layout)
        left_layout.addWidget(metrics_group)

        layout.addWidget(left_panel)

        # Painel direito (estado do processador)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Registradores
        registers_group = QGroupBox("Registradores")
        registers_layout = QVBoxLayout()
        self.registers_table = QTableWidget(32, 3)
        self.registers_table.setHorizontalHeaderLabels(["Registrador", "Valor", "Status"])
        registers_layout.addWidget(self.registers_table)
        registers_group.setLayout(registers_layout)
        right_layout.addWidget(registers_group)

        # Estações de Reserva
        stations_group = QGroupBox("Estações de Reserva")
        stations_layout = QVBoxLayout()
        self.stations_table = QTableWidget(9, 7)
        self.stations_table.setHorizontalHeaderLabels(
            ["Nome", "Ocupada", "Operação", "Vj", "Vk", "Qj", "Qk"]
        )
        stations_layout.addWidget(self.stations_table)
        stations_group.setLayout(stations_layout)
        right_layout.addWidget(stations_group)

        # Buffer de Reordenamento
        rob_group = QGroupBox("Buffer de Reordenamento")
        rob_layout = QVBoxLayout()
        self.rob_table = QTableWidget(8, 5)
        self.rob_table.setHorizontalHeaderLabels(
            ["Instrução", "Estado", "Destino", "Valor", "Pronto"]
        )
        rob_layout.addWidget(self.rob_table)
        rob_group.setLayout(rob_layout)
        right_layout.addWidget(rob_group)

        layout.addWidget(right_panel)

        # Conectar sinais
        self.load_btn.clicked.connect(self.load_program)
        self.step_btn.clicked.connect(self.step)
        self.run_btn.clicked.connect(self.run)
        self.reset_btn.clicked.connect(self.reset)

        # Timer para execução contínua
        self.timer = QTimer()
        self.timer.timeout.connect(self.step)

    def load_program(self):
        program = self.code_edit.toPlainText().strip().split('\n')
        if not program or program[0] == '':
            QMessageBox.warning(self, "Erro", "Por favor, insira um programa MIPS válido.")
            return
        self.processor.load_program(program)
        self.update_ui()
        self.status_label.setText("Status: Programa Carregado")

    def step(self):
        if self.processor.step():
            self.update_ui()
        else:
            self.timer.stop()
            self.run_btn.setText("Executar")
            self.status_label.setText("Status: Programa Finalizado")
            QMessageBox.information(self, "Programa Finalizado", 
                                  f"O programa foi executado com sucesso!\n\n"
                                  f"Ciclos totais: {self.processor.cycle}\n"
                                  f"IPC: {self.processor.get_metrics()['ipc']:.2f}\n"
                                  f"Ciclos de bolha: {self.processor.metrics['bubble_cycles']}")

    def run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.run_btn.setText("Executar")
            self.status_label.setText("Status: Pausado")
        else:
            self.timer.start(1000)  # 1 segundo entre passos
            self.run_btn.setText("Pausar")
            self.status_label.setText("Status: Executando")

    def reset(self):
        self.processor = TomasuloProcessor()
        self.update_ui()
        self.status_label.setText("Status: Pronto")

    def update_ui(self):
        state = self.processor.get_state()
        
        # Atualizar métricas
        self.cycle_label.setText(f"Ciclo: {state['cycle']}")
        self.ipc_label.setText(f"IPC: {state['metrics']['ipc']:.2f}")
        self.bubbles_label.setText(f"Ciclos de Bolha: {state['metrics']['bubble_cycles']}")

        # Atualizar registradores
        self.registers_table.setRowCount(0)
        for reg, info in state['registers'].items():
            row = self.registers_table.rowCount()
            self.registers_table.insertRow(row)
            self.registers_table.setItem(row, 0, QTableWidgetItem(reg))
            self.registers_table.setItem(row, 1, QTableWidgetItem(str(info['value'])))
            self.registers_table.setItem(row, 2, QTableWidgetItem(str(info['status'])))

        # Atualizar estações de reserva
        self.stations_table.setRowCount(0)
        for name, info in state['reservation_stations'].items():
            row = self.stations_table.rowCount()
            self.stations_table.insertRow(row)
            self.stations_table.setItem(row, 0, QTableWidgetItem(name))
            self.stations_table.setItem(row, 1, QTableWidgetItem(str(info['busy'])))
            self.stations_table.setItem(row, 2, QTableWidgetItem(str(info['op'])))
            self.stations_table.setItem(row, 3, QTableWidgetItem(str(info['vj'])))
            self.stations_table.setItem(row, 4, QTableWidgetItem(str(info['vk'])))
            self.stations_table.setItem(row, 5, QTableWidgetItem(str(info['qj'])))
            self.stations_table.setItem(row, 6, QTableWidgetItem(str(info['qk'])))

        # Atualizar buffer de reordenamento
        self.rob_table.setRowCount(0)
        for entry in state['reorder_buffer']:
            row = self.rob_table.rowCount()
            self.rob_table.insertRow(row)
            self.rob_table.setItem(row, 0, QTableWidgetItem(str(entry['instruction'])))
            self.rob_table.setItem(row, 1, QTableWidgetItem(str(entry['state'])))
            self.rob_table.setItem(row, 2, QTableWidgetItem(str(entry['destination'])))
            self.rob_table.setItem(row, 3, QTableWidgetItem(str(entry['value'])))
            self.rob_table.setItem(row, 4, QTableWidgetItem(str(entry['ready']))) 