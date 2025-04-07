#!/bin/bash

# Define o diretório onde o script está localizado
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Define o PYTHONPATH para incluir o diretório pai de graphics_editor
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Executa o main.py usando python3 (ou python)
echo "Executando o editor gráfico..."
python3 "$SCRIPT_DIR/graphics_editor/main.py"

