#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"


PROJECT_BASE_DIR="$SCRIPT_DIR"


export PYTHONPATH="${PROJECT_BASE_DIR}:${PYTHONPATH}"

cd "$PROJECT_BASE_DIR" || exit # Sai se o cd falhar

echo "Executando o editor gráfico a partir de: $(pwd)"
echo "PYTHONPATH atual: $PYTHONPATH" 

if command -v python3 &> /dev/null
then
    PYTHON_EXEC="python3"
elif command -v python &> /dev/null
then
    PYTHON_EXEC="python"
else
    echo "Erro: Nem 'python3' nem 'python' foram encontrados no PATH."
    exit 1
fi

# Executa usando a flag -m para tratar graphics_editor.main como um módulo
$PYTHON_EXEC -m graphics_editor.main