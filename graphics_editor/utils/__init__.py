# graphics_editor/utils/__init__.py
"""
Pacote de utilitários para o editor gráfico.

Contém módulos para:
- clipping: Algoritmos de recorte 2D (Cohen-Sutherland, Liang-Barsky, Sutherland-Hodgman).
- transformations: Funções para transformações geométricas 2D usando matrizes homogêneas.
- transformations_3d: Funções para transformações geométricas 3D e projeção.
"""

from . import clipping
from . import transformations
from . import transformations_3d  # Novo

__all__ = [
    "clipping",
    "transformations",
    "transformations_3d",
]
