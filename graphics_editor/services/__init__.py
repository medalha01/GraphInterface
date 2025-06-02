# graphics_editor/services/__init__.py
"""
Pacote que contém os serviços do editor gráfico.

Este pacote fornece os seguintes serviços:
- FileOperationService: Gerencia operações de arquivo (carregar/salvar OBJ/MTL para 2D).

Cada serviço é responsável por:
- Implementar funcionalidades específicas do editor.
- Coordenar a interação entre diferentes componentes.
- Gerenciar o estado e as operações do editor relacionadas à sua responsabilidade.
"""

from .file_operation_service import FileOperationService

__all__ = [
    "FileOperationService",
]
