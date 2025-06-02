# graphics_editor/dialogs/__init__.py
"""
Pacote que contém os diálogos personalizados para o editor gráfico.

Diálogos disponíveis:
- CoordinateInputDialog: Para entrada de coordenadas de objetos 2D.
- TransformationDialog: Para configurar transformações geométricas 2D e 3D.
- CameraDialog: Para configurar parâmetros da câmera 3D.
"""

from .coordinates_input import CoordinateInputDialog
from .transformation_dialog import TransformationDialog
from .camera_dialog import CameraDialog  # Novo

__all__ = [
    "CoordinateInputDialog",
    "TransformationDialog",
    "CameraDialog",
]
