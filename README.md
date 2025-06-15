# Simulador Didático do Algoritmo de Tomasulo

Este é um simulador didático do algoritmo de Tomasulo para arquitetura MIPS, desenvolvido para fins educacionais.

## Características

- Simulação do algoritmo de Tomasulo
- Interface gráfica interativa
- Suporte a instruções MIPS
- Métricas de desempenho:
  - IPC (Instruções por Ciclo)
  - Total de ciclos
  - Ciclos de bolha (quando o processador está parado esperando por recursos)
- Buffer de reordenamento
- Especulação de desvios condicionais
- Modo passo a passo para visualização detalhada

## Recursos do Processador

- 2 estações de reserva para ADD/SUB
- 1 estação de reserva para MUL/DIV
- 2 estações de reserva para LD/ST
- Latências configuradas:
  - ADD/SUB: 1 ciclo
  - MUL: 3 ciclos
  - DIV: 5 ciclos
  - LD/ST: 2 ciclos

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

## Exemplo de Uso

O simulador suporta instruções MIPS como:
```
LD R1, 0(R0)    # Carrega valor da memória
LD R2, 4(R0)    # Carrega valor da memória
MUL R3, R1, R2  # Multiplica R1 e R2
DIV R4, R3, R1  # Divide R3 por R1
MUL R5, R4, R2  # Multiplica R4 e R2
DIV R6, R5, R4  # Divide R5 por R4
ST R6, 8(R0)    # Armazena R6 na memória
```

## Métricas

O simulador fornece métricas importantes para análise de desempenho:
- IPC (Instruções por Ciclo): Número médio de instruções completadas por ciclo
- Total de ciclos: Número total de ciclos necessários para executar o programa
- Ciclos de bolha: Número de ciclos em que o processador está parado esperando por recursos 