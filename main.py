import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from tomasulo.processor import TomasuloProcessor

def main():
    # Configurações customizadas
    latencies = {
        "ADD": 1,
        "SUB": 1,
        "MUL": 3,
        "DIV": 5,
        "LD": 2,
        "ST": 2
    }
    n_add = 2
    n_mul = 1
    n_mem = 2  # Agora controla tanto LD quanto ST
    max_issue_per_cycle = 4  # Máximo de instruções despachadas por ciclo

    app = QApplication(sys.argv)
    processor = TomasuloProcessor(latencies=latencies, n_add=n_add, n_mul=n_mul, n_mem=n_mem, max_issue_per_cycle=max_issue_per_cycle)
    
    # Carrega exemplo de demonstração do paralelismo
    with open('examples/parallelism_demo.txt', 'r') as f:
        program = [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith('#')]
    
    processor.load_program(program)
    window = MainWindow(processor=processor)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 