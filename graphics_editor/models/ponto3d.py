# graphics_editor/models/ponto3d.py
from typing import Tuple, Optional
from PyQt5.QtGui import QColor, QVector3D
from PyQt5.QtCore import Qt
import numpy as np


class Ponto3D:
    """
    Representa um ponto geométrico 3D com coordenadas e cor.

    Esta classe é responsável por:
    - Armazenar coordenadas (x, y, z) de um ponto.
    - Gerenciar a cor do ponto.
    - Fornecer métodos para manipulação de coordenadas e transformações.
    """

    def __init__(self, x: float, y: float, z: float, color: Optional[QColor] = None):
        """
        Inicializa um Ponto3D com coordenadas e cor.

        Args:
            x: Coordenada x do ponto.
            y: Coordenada y do ponto.
            z: Coordenada z do ponto.
            color: Cor do ponto (opcional, padrão é preto).
        """
        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def to_qvector3d(self) -> QVector3D:
        """
        Converte o Ponto3D para o formato QVector3D do Qt.

        Returns:
            QVector3D: Ponto no formato Qt.
        """
        return QVector3D(self.x, self.y, self.z)

    def get_coords(self) -> Tuple[float, float, float]:
        """
        Retorna as coordenadas do ponto.

        Returns:
            Tuple[float, float, float]: Tupla contendo as coordenadas (x, y, z).
        """
        return (self.x, self.y, self.z)

    def get_homogeneous_coords(self) -> np.ndarray:
        """
        Retorna as coordenadas homogêneas do ponto (x, y, z, 1).

        Returns:
            np.ndarray: Array NumPy com as coordenadas homogêneas.
        """
        return np.array([self.x, self.y, self.z, 1.0], dtype=float)

    def set_from_homogeneous_coords(self, h_coords: np.ndarray) -> None:
        """
        Define as coordenadas do ponto a partir de coordenadas homogêneas.
        Normaliza dividindo por w se w não for zero.

        Args:
            h_coords: Array NumPy com as coordenadas homogêneas (x, y, z, w).
        """
        if h_coords.shape == (4,):
            w = h_coords[3]
            if abs(w) > 1e-9:  # Evita divisão por zero
                self.x = h_coords[0] / w
                self.y = h_coords[1] / w
                self.z = h_coords[2] / w
            else:  # Se w for próximo de zero, não normaliza (ponto no infinito)
                self.x = h_coords[0]
                self.y = h_coords[1]
                self.z = h_coords[2]
        else:
            raise ValueError("Coordenadas homogêneas devem ser um array (4,).")

    def __repr__(self) -> str:
        """
        Retorna uma representação textual do Ponto3D.

        Returns:
            str: String representando o Ponto3D com suas coordenadas e cor.
        """
        return f"Ponto3D(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f}, color={self.color.name()})"

    def __eq__(self, other: object) -> bool:
        """Verifica se dois Ponto3D são iguais (baseado nas coordenadas)."""
        if not isinstance(other, Ponto3D):
            return NotImplemented
        # Compara com uma pequena tolerância para pontos flutuantes
        epsilon = 1e-9
        return (
            abs(self.x - other.x) < epsilon
            and abs(self.y - other.y) < epsilon
            and abs(self.z - other.z) < epsilon
        )
        # A cor não é considerada para igualdade geométrica aqui.
