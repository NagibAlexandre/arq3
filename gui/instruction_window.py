from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
from PyQt6.QtCore import Qt

class InstructionStatusWindow(QWidget):
    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Status das Instruções")
        self.setGeometry(300, 300, 800, 400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Título
        title = QLabel("Estágios das Instruções")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        layout.addWidget(title)
        
        # Tabela de status
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Instrução", "Issue", "Execute", "Write Result", "Commit"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.table)
        
    def update_status(self):
        state = self.processor.get_state()
        instructions = state.get('instruction_status', [])
        
        self.table.setRowCount(len(instructions))
        
        for row, instr in enumerate(instructions):
            # Coluna da instrução
            self.table.setItem(row, 0, QTableWidgetItem(instr['instruction']))
            
            # Colunas de estágio
            for i, stage in enumerate(['issue', 'execute', 'write_result', 'commit'], start=1):
                if instr.get(stage):
                    item = QTableWidgetItem("X")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    # Colorir baseado no estágio
                    if stage == 'issue':
                        item.setBackground(Qt.GlobalColor.lightGray)
                    elif stage == 'execute':
                        item.setBackground(Qt.GlobalColor.cyan)
                    elif stage == 'write_result':
                        item.setBackground(Qt.GlobalColor.green)
                    elif stage == 'commit':
                        item.setBackground(Qt.GlobalColor.darkGreen)
                        
                    self.table.setItem(row, i, item)
                else:
                    self.table.setItem(row, i, QTableWidgetItem(""))