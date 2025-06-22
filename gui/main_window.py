from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QLabel, QTableWidget,
                             QTableWidgetItem, QGroupBox, QGridLayout, QMessageBox,
                             QSpinBox, QComboBox, QCheckBox, QTabWidget)
from PyQt6.QtCore import Qt, QTimer
from tomasulo.processor import TomasuloProcessor
from gui.instruction_window import InstructionStatusWindow

class MainWindow(QMainWindow):
    def __init__(self, processor=None):
        super().__init__()
        if processor is not None:
            self.processor = processor
        else:
            from tomasulo.processor import TomasuloProcessor
            self.processor = TomasuloProcessor()
        self.init_ui()
        self.update_ui()

    def init_ui(self):
        self.setWindowTitle('Simulador Tomasulo')
        self.setGeometry(100, 100, 1400, 900)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Painel esquerdo (programa e controles)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Configurações do processador
        config_group = QGroupBox("Configurações do Processador")
        config_layout = QGridLayout()
        
        # Configuração de latências
        self.latency_add = QSpinBox()
        self.latency_add.setRange(1, 10)
        self.latency_add.setValue(1)
        self.latency_mul = QSpinBox()
        self.latency_mul.setRange(1, 10)
        self.latency_mul.setValue(3)
        self.latency_div = QSpinBox()
        self.latency_div.setRange(1, 10)
        self.latency_div.setValue(5)
        self.latency_mem = QSpinBox()
        self.latency_mem.setRange(1, 10)
        self.latency_mem.setValue(2)
        
        config_layout.addWidget(QLabel("Latência ADD/SUB:"), 0, 0)
        config_layout.addWidget(self.latency_add, 0, 1)
        config_layout.addWidget(QLabel("Latência MUL:"), 1, 0)
        config_layout.addWidget(self.latency_mul, 1, 1)
        config_layout.addWidget(QLabel("Latência DIV:"), 2, 0)
        config_layout.addWidget(self.latency_div, 2, 1)
        config_layout.addWidget(QLabel("Latência LD/ST:"), 3, 0)
        config_layout.addWidget(self.latency_mem, 3, 1)
        
        # Configuração de buffers
        self.buffer_add = QSpinBox()
        self.buffer_add.setRange(1, 10)
        self.buffer_add.setValue(3)
        self.buffer_mul = QSpinBox()
        self.buffer_mul.setRange(1, 10)
        self.buffer_mul.setValue(3)
        self.buffer_mem = QSpinBox()
        self.buffer_mem.setRange(1, 10)
        self.buffer_mem.setValue(2)
        self.buffer_rob = QSpinBox()
        self.buffer_rob.setRange(4, 16)
        self.buffer_rob.setValue(8)
        
        config_layout.addWidget(QLabel("Buffers ADD/SUB:"), 0, 2)
        config_layout.addWidget(self.buffer_add, 0, 3)
        config_layout.addWidget(QLabel("Buffers MUL/DIV:"), 1, 2)
        config_layout.addWidget(self.buffer_mul, 1, 3)
        config_layout.addWidget(QLabel("Buffers LD/ST:"), 2, 2)
        config_layout.addWidget(self.buffer_mem, 2, 3)
        config_layout.addWidget(QLabel("Tamanho ROB:"), 3, 2)
        config_layout.addWidget(self.buffer_rob, 3, 3)
        
        # Especulação
        self.speculation_check = QCheckBox("Habilitar Especulação")
        self.speculation_check.setChecked(True)
        config_layout.addWidget(self.speculation_check, 4, 0, 1, 2)
        
        # Valores iniciais de memória
        self.mem_r1 = QSpinBox()
        self.mem_r1.setRange(-1000, 1000)
        self.mem_r1.setValue(10)
        self.mem_r2 = QSpinBox()
        self.mem_r2.setRange(-1000, 1000)
        self.mem_r2.setValue(20)
        
        config_layout.addWidget(QLabel("Mem[R1]:"), 5, 0)
        config_layout.addWidget(self.mem_r1, 5, 1)
        config_layout.addWidget(QLabel("Mem[R2]:"), 5, 2)
        config_layout.addWidget(self.mem_r2, 5, 3)
        
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)

        # Área de código
        code_group = QGroupBox("Programa MIPS")
        code_layout = QVBoxLayout()
        self.code_edit = QTextEdit()
        self.code_edit.setPlaceholderText("Digite seu programa MIPS aqui...\nExemplo:\nLD R1, 0(R0)\nLD R2, 4(R0)\nADD R3, R1, R2")
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
        self.status_btn = QPushButton("Status Instruções")
        controls_layout.addWidget(self.load_btn)
        controls_layout.addWidget(self.step_btn)
        controls_layout.addWidget(self.run_btn)
        controls_layout.addWidget(self.reset_btn)
        controls_layout.addWidget(self.status_btn)
        self.status_btn.clicked.connect(self.show_instruction_status)
        controls_group.setLayout(controls_layout)
        left_layout.addWidget(controls_group)

        # Métricas
        metrics_group = QGroupBox("Métricas")
        metrics_layout = QGridLayout()
        self.cycle_label = QLabel("Ciclo: 0")
        self.ipc_label = QLabel("IPC: 0.0")
        self.bubbles_label = QLabel("Ciclos de Bolha: 0")
        self.committed_label = QLabel("Instruções Commitadas: 0/0")
        self.status_label = QLabel("Status: Pronto")
        
        metrics_layout.addWidget(self.cycle_label, 0, 0)
        metrics_layout.addWidget(self.ipc_label, 0, 1)
        metrics_layout.addWidget(self.bubbles_label, 1, 0)
        metrics_layout.addWidget(self.committed_label, 1, 1)
        metrics_layout.addWidget(self.status_label, 2, 0, 1, 2)
        
        metrics_group.setLayout(metrics_layout)
        left_layout.addWidget(metrics_group)

        layout.addWidget(left_panel)

        # Painel direito (estado do processador)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Tabs para registradores
        registers_tabs = QTabWidget()
        
        # Registradores inteiros
        int_registers_group = QGroupBox("Registradores Inteiros (R0-R31)")
        int_registers_layout = QVBoxLayout()
        self.int_registers_table = QTableWidget(32, 3)
        self.int_registers_table.setHorizontalHeaderLabels(["Registrador", "Valor", "Status"])
        int_registers_layout.addWidget(self.int_registers_table)
        int_registers_group.setLayout(int_registers_layout)
        registers_tabs.addTab(int_registers_group, "Inteiros")
        
        # Registradores ponto flutuante
        fp_registers_group = QGroupBox("Registradores Ponto Flutuante (F0-F31)")
        fp_registers_layout = QVBoxLayout()
        self.fp_registers_table = QTableWidget(32, 3)
        self.fp_registers_table.setHorizontalHeaderLabels(["Registrador", "Valor", "Status"])
        fp_registers_layout.addWidget(self.fp_registers_table)
        fp_registers_group.setLayout(fp_registers_layout)
        registers_tabs.addTab(fp_registers_group, "Ponto Flutuante")
        
        right_layout.addWidget(registers_tabs)

        # Estações de Reserva
        stations_group = QGroupBox("Estações de Reserva")
        stations_layout = QVBoxLayout()
        self.stations_table = QTableWidget(9, 8)  # Added remaining cycles column
        self.stations_table.setHorizontalHeaderLabels(
            ["Nome", "Ocupada", "Operação", "Vj", "Vk", "Qj", "Qk", "Ciclos"]
        )
        stations_layout.addWidget(self.stations_table)
        stations_group.setLayout(stations_layout)
        right_layout.addWidget(stations_group)

        # Buffer de Reordenamento
        rob_group = QGroupBox("Buffer de Reordenamento")
        rob_layout = QVBoxLayout()
        self.rob_table = QTableWidget(8, 6)  # Added state column
        self.rob_table.setHorizontalHeaderLabels(
            ["Instrução", "Estado", "Destino", "Valor", "Pronto", "Especulação"]
        )
        rob_layout.addWidget(self.rob_table)
        rob_group.setLayout(rob_layout)
        right_layout.addWidget(rob_group)

        layout.addWidget(right_panel)

        # Conectar sinais
        self.load_btn.clicked.connect(self.load_program)
        self.step_btn.clicked.connect(self.step)
        self.run_btn.clicked.connect(self.run)
        self.reset_btn.clicked.connect(self.reset_processor)

        # Timer para execução contínua
        self.timer = QTimer()
        self.timer.timeout.connect(self.step)

    def load_program(self):
        try:
            # Get configuration values
            latencies = {
                "ADD": self.latency_add.value(),
                "SUB": self.latency_add.value(),
                "MUL": self.latency_mul.value(),
                "DIV": self.latency_div.value(),
                "LD": self.latency_mem.value(),
                "ST": self.latency_mem.value()
            }
            
            # Create new processor with configuration
            self.processor = TomasuloProcessor(
                latencies=latencies,
                n_add=self.buffer_add.value(),
                n_mul=self.buffer_mul.value(),
                n_mem=self.buffer_mem.value()
            )
            
            # Set memory initial values
            self.processor.memory[0] = self.mem_r1.value()
            self.processor.memory[4] = self.mem_r2.value()
            
            # Load program
            program = self.code_edit.toPlainText().strip().split('\n')
            program = [line.strip() for line in program if line.strip()]
            
            if not program:
                QMessageBox.warning(self, "Erro", "Por favor, insira um programa MIPS válido.")
                return
                
            self.processor.load_program(program)
            self.update_ui()
            self.status_label.setText("Status: Programa Carregado")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar programa:\n{str(e)}")

    def step(self):
        try:
            if self.processor.step():
                self.update_ui()
            else:
                self.timer.stop()
                self.run_btn.setText("Executar")
                self.status_label.setText("Status: Programa Finalizado")
                metrics = self.processor.get_metrics()
                QMessageBox.information(self, "Programa Finalizado", 
                                      f"O programa foi executado com sucesso!\n\n"
                                      f"Ciclos totais: {metrics['total_cycles']}\n"
                                      f"IPC: {metrics['ipc']:.2f}\n"
                                      f"Ciclos de bolha: {metrics['bubble_cycles']}\n"
                                      f"Instruções commitadas: {metrics['committed_instructions']}/{metrics['total_instructions']}")
        except Exception as e:
            self.timer.stop()
            self.run_btn.setText("Executar")
            self.status_label.setText("Status: Erro de Execução")
            QMessageBox.critical(self, "Erro de Execução", f"Erro durante a execução:\n{str(e)}")

    def run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.run_btn.setText("Executar")
            self.status_label.setText("Status: Pausado")
        else:
            self.timer.start(500)  # 0.5 segundo entre passos
            self.run_btn.setText("Pausar")
            self.status_label.setText("Status: Executando")

    def reset_processor(self):
        try:
            # Fecha a janela de status se estiver aberta
            if hasattr(self, 'instruction_window'):
                self.instruction_window.close()
                del self.instruction_window
                
            # Create new processor with current configuration
            latencies = {
                "ADD": self.latency_add.value(),
                "SUB": self.latency_add.value(),
                "MUL": self.latency_mul.value(),
                "DIV": self.latency_div.value(),
                "LD": self.latency_mem.value(),
                "ST": self.latency_mem.value()
            }
            
            self.processor = TomasuloProcessor(
                latencies=latencies,
                n_add=self.buffer_add.value(),
                n_mul=self.buffer_mul.value(),
                n_mem=self.buffer_mem.value()
            )
            
            # Reset memory values
            self.processor.memory[0] = self.mem_r1.value()
            self.processor.memory[4] = self.mem_r2.value()
            
            # Reload program if exists
            program = self.code_edit.toPlainText().strip().split('\n')
            program = [line.strip() for line in program if line.strip()]
            
            if program:
                self.processor.load_program(program)
            
            self.update_ui()
            self.status_label.setText("Status: Pronto")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao resetar processador:\n{str(e)}")

    def update_ui(self):
        state = self.processor.get_state()
        
        # Atualizar métricas
        self.cycle_label.setText(f"Ciclo: {state['cycle']}")
        self.ipc_label.setText(f"IPC: {state['metrics']['ipc']:.2f}")
        self.bubbles_label.setText(f"Ciclos de Bolha: {state['metrics']['bubble_cycles']}")
        self.committed_label.setText(f"Instruções Commitadas: {state['metrics']['committed_instructions']}/{state['metrics']['total_instructions']}")

        # Atualizar registradores inteiros
        self.int_registers_table.setRowCount(0)
        for i in range(32):
            reg = f"R{i}"
            info = state['registers'].get(reg, {'value': 0, 'status': None})
            row = self.int_registers_table.rowCount()
            self.int_registers_table.insertRow(row)
            self.int_registers_table.setItem(row, 0, QTableWidgetItem(reg))
            self.int_registers_table.setItem(row, 1, QTableWidgetItem(str(info['value'])))
            self.int_registers_table.setItem(row, 2, QTableWidgetItem(str(info['status'])))

        # Atualizar registradores ponto flutuante
        self.fp_registers_table.setRowCount(0)
        for i in range(32):
            reg = f"F{i}"
            info = state['registers'].get(reg, {'value': 0, 'status': None})
            row = self.fp_registers_table.rowCount()
            self.fp_registers_table.insertRow(row)
            self.fp_registers_table.setItem(row, 0, QTableWidgetItem(reg))
            self.fp_registers_table.setItem(row, 1, QTableWidgetItem(str(info['value'])))
            self.fp_registers_table.setItem(row, 2, QTableWidgetItem(str(info['status'])))

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
            self.stations_table.setItem(row, 7, QTableWidgetItem(str(info.get('remaining_cycles', ''))))

        # Atualizar buffer de reordenamento
        self.rob_table.setRowCount(0)
        for entry in state['reorder_buffer']:
            if entry is None:
                continue
                
            row = self.rob_table.rowCount()
            self.rob_table.insertRow(row)
            self.rob_table.setItem(row, 0, QTableWidgetItem(str(entry['instruction'])))
            self.rob_table.setItem(row, 1, QTableWidgetItem(str(entry['state'])))
            self.rob_table.setItem(row, 2, QTableWidgetItem(str(entry['destination'])))
            self.rob_table.setItem(row, 3, QTableWidgetItem(str(entry['value'])))
            self.rob_table.setItem(row, 4, QTableWidgetItem(str(entry['ready'])))
            
            # Highlight speculative entries
            if entry.get('branch_mispredicted', False):
                for col in range(5):
                    self.rob_table.item(row, col).setBackground(Qt.GlobalColor.yellow)
            elif entry['state'] == "ISSUE":
                for col in range(5):
                    self.rob_table.item(row, col).setBackground(Qt.GlobalColor.lightGray)
            elif entry['state'] == "EXECUTE":
                for col in range(5):
                    self.rob_table.item(row, col).setBackground(Qt.GlobalColor.cyan)
            elif entry['state'] == "WRITE_RESULT":
                for col in range(5):
                    self.rob_table.item(row, col).setBackground(Qt.GlobalColor.green)
            elif entry['state'] == "COMMIT":
                for col in range(5):
                    self.rob_table.item(row, col).setBackground(Qt.GlobalColor.darkGreen)
        
        # Atualizar janela de status das instruções se estiver aberta
        if hasattr(self, 'instruction_window') and self.instruction_window.isVisible():
            self.instruction_window.update_status()

                    
    def show_instruction_status(self):
        # Fecha a janela existente se houver
        if hasattr(self, 'instruction_window'):
            self.instruction_window.close()
    
        # Cria uma nova janela com o processador atual
        self.instruction_window = InstructionStatusWindow(self.processor)
        self.instruction_window.update_status()
        self.instruction_window.show()