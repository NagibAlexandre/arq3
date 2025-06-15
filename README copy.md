# Simulador Didático do Algoritmo de Tomasulo

Este é um simulador didático do algoritmo de Tomasulo para arquitetura MIPS, desenvolvido para fins educacionais.

## Características

- Simulação do algoritmo de Tomasulo
- Interface gráfica interativa
- Suporte a instruções MIPS
- Métricas de desempenho (IPC, ciclos, bolhas)
- Buffer de reordenamento
- Especulação de desvios condicionais
- Modo passo a passo para visualização detalhada

## Requisitos

- Python 3.8+
- PyQt6
- NumPy

## Instalação

1. Clone o repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Execução

```bash
python main.py
```

## Estrutura do Projeto

- `main.py`: Ponto de entrada da aplicação
- `tomasulo/`: Módulo principal do simulador
  - `processor.py`: Implementação do processador Tomasulo
  - `instructions.py`: Definição das instruções MIPS
  - `reservation_station.py`: Estações de reserva
  - `register_status.py`: Status dos registradores
  - `reorder_buffer.py`: Buffer de reordenamento
- `gui/`: Interface gráfica
  - `main_window.py`: Janela principal
  - `components/`: Componentes da interface 