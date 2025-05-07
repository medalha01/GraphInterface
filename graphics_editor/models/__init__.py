# graphics_editor/models/__init__.py

# Expose the model classes for direct import from the package
from .point import Point
from .line import Line
from .polygon import Polygon
from .bezier_curve import BezierCurve

# __all__ defines the public API of the models package when using 'from .models import *'
# It's good practice to define it, even if not strictly necessary for direct imports.
__all__ = [
    "Point",
    "Line",
    "Polygon",
    "BezierCurve",
]
