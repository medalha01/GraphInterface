"""
Pacote que contém as classes de modelo para representação de objetos gráficos 2D.

Este pacote fornece as seguintes classes:
- Point: Representa um ponto 2D
- Line: Representa um segmento de linha 2D
- Polygon: Representa um polígono ou polilinha 2D
- BezierCurve: Representa uma curva de Bézier cúbica composta
- BSplineCurve: Representa uma curva B-spline usando diferenças progressivas

Cada classe é responsável por:
- Armazenar os dados geométricos do objeto
- Gerenciar a aparência visual (cor, espessura, etc.)
- Criar a representação gráfica do objeto
- Fornecer métodos para manipulação de coordenadas
"""

# graphics_editor/models/__init__.py

# Expose the model classes for direct import from the package
from .point import Point
from .line import Line
from .polygon import Polygon
from .bezier_curve import BezierCurve
from .bspline_curve import BSplineCurve

# __all__ defines the public API of the models package when using 'from .models import *'
# It's good practice to define it, even if not strictly necessary for direct imports.
__all__ = [
    "Point",
    "Line",
    "Polygon",
    "BezierCurve",
    "BSplineCurve",
]
