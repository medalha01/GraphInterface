# graphics_editor/models/__init__.py
"""
Pacote que contém os modelos de dados do editor gráfico.

Este pacote fornece os seguintes modelos:
- Point: Representa um ponto 2D.
- Line: Representa uma linha 2D.
- Polygon: Representa um polígono 2D.
- BezierCurve: Representa uma curva de Bézier 2D.
- BSplineCurve: Representa uma curva B-spline 2D.
- Ponto3D: Representa um ponto 3D.
- Objeto3D: Representa um objeto de modelo de arame 3D.

Cada modelo é responsável por:
- Armazenar dados geométricos e de aparência.
- Fornecer métodos para criar sua representação gráfica (QGraphicsItem) - para 2D
  ou para ser usado pelo SceneController para projeção 3D.
- Fornecer métodos para manipulação de coordenadas e cálculo de centro.
"""

from .point import Point
from .line import Line
from .polygon import Polygon
from .bezier_curve import BezierCurve
from .bspline_curve import BSplineCurve
from .ponto3d import Ponto3D  # Novo modelo 3D
from .objeto3d import Objeto3D  # Novo modelo 3D


# Lista de todos os modelos exportados para facilitar importações com '*'
# (embora importações explícitas sejam geralmente preferidas)
__all__ = [
    "Point",
    "Line",
    "Polygon",
    "BezierCurve",
    "BSplineCurve",
    "Ponto3D",
    "Objeto3D",
]
