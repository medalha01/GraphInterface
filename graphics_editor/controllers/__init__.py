# graphics_editor/controllers/__init__.py
"""
Pacote que contém os controladores do editor gráfico.

Controladores são responsáveis por:
- Gerenciar a lógica de interação do usuário.
- Modificar o estado da aplicação e os modelos de dados.
- Coordenar ações entre a UI, o estado e os modelos.

Controladores disponíveis:
- DrawingController: Gerencia o processo de desenho de objetos 2D.
- SceneController: Gerencia os objetos na cena gráfica (2D e 3D), incluindo recorte e projeção.
- TransformationController: Gerencia a aplicação de transformações geométricas.
"""

from .drawing_controller import DrawingController
from .scene_controller import SceneController
from .transformation_controller import TransformationController

__all__ = [
    "DrawingController",
    "SceneController",
    "TransformationController",
]
