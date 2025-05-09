"""
Módulo que gerencia o estado central da aplicação do editor gráfico.
Este módulo contém as classes e enums necessários para gerenciar o estado da aplicação.
"""

# graphics_editor/state_manager.py
from PyQt5.QtCore import QObject, pyqtSignal, QRectF, Qt
from PyQt5.QtGui import QColor
from enum import Enum, auto
from typing import Optional, List


class DrawingMode(Enum):
    """
    Enumeração que define os modos de desenho disponíveis no editor.
    
    Atributos:
        POINT: Modo para desenhar pontos
        LINE: Modo para desenhar linhas
        POLYGON: Modo para desenhar polígonos
        BEZIER: Modo para desenhar curvas de Bézier
        BSPLINE: Modo para desenhar curvas B-spline
        SELECT: Modo para selecionar e manipular objetos
        PAN: Modo para mover a visualização
    """
    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    BEZIER = auto()
    BSPLINE = auto()  # Add B-spline mode
    SELECT = auto()
    PAN = auto()


class LineClippingAlgorithm(Enum):
    """
    Enumeração que define os algoritmos de recorte de linha disponíveis.
    
    Atributos:
        COHEN_SUTHERLAND: Algoritmo de Cohen-Sutherland para recorte de linhas
        LIANG_BARSKY: Algoritmo de Liang-Barsky para recorte de linhas
    """
    COHEN_SUTHERLAND = auto()
    LIANG_BARSKY = auto()


class EditorStateManager(QObject):
    """
    Gerencia o estado central da aplicação do editor.
    
    Esta classe é responsável por:
    - Gerenciar o modo de desenho atual
    - Gerenciar a cor de desenho
    - Controlar o estado de modificações não salvas
    - Gerenciar o caminho do arquivo atual
    - Controlar o algoritmo de recorte de linha
    - Gerenciar o retângulo de recorte
    """

    # --- Sinais de Mudança de Estado ---
    drawing_mode_changed = pyqtSignal(DrawingMode)
    draw_color_changed = pyqtSignal(QColor)
    unsaved_changes_changed = pyqtSignal(bool)
    filepath_changed = pyqtSignal(str)  # Emite caminho ou "" para novo/limpo
    line_clipper_changed = pyqtSignal(LineClippingAlgorithm)
    clip_rect_changed = pyqtSignal(QRectF)  # Se o retângulo de clip for dinâmico

    # --- Constantes ---
    # Default viewport rectangle (xmin, ymin, width, height)
    DEFAULT_CLIP_RECT = QRectF(-500.0, -400.0, 1000.0, 800.0)

    def __init__(self, parent: Optional[QObject] = None):
        """
        Inicializa o gerenciador de estado.
        
        Args:
            parent: Objeto pai opcional
        """
        super().__init__(parent)
        self._drawing_mode: DrawingMode = DrawingMode.SELECT
        self._current_draw_color: QColor = QColor(Qt.black)
        self._unsaved_changes: bool = False
        self._current_filepath: Optional[str] = None
        self._selected_line_clipper: LineClippingAlgorithm = (
            LineClippingAlgorithm.COHEN_SUTHERLAND  # Default clipper
        )
        # Clip rectangle defined by the StateManager
        self._clip_rect: QRectF = (
            self.DEFAULT_CLIP_RECT.normalized()
        )  # Ensure width/height are positive

    # --- Getters ---
    def drawing_mode(self) -> DrawingMode:
        """
        Retorna o modo de desenho atual.
        
        Returns:
            DrawingMode: Modo de desenho atual
        """
        return self._drawing_mode

    def draw_color(self) -> QColor:
        """
        Retorna a cor atual de desenho.
        
        Returns:
            QColor: Cor atual de desenho
        """
        return self._current_draw_color

    def has_unsaved_changes(self) -> bool:
        """
        Verifica se há modificações não salvas.
        
        Returns:
            bool: True se houver modificações não salvas, False caso contrário
        """
        return self._unsaved_changes

    def current_filepath(self) -> Optional[str]:
        """
        Retorna o caminho do arquivo atual.
        
        Returns:
            Optional[str]: Caminho do arquivo atual ou None se não houver arquivo
        """
        return self._current_filepath

    def selected_line_clipper(self) -> LineClippingAlgorithm:
        """
        Retorna o algoritmo de recorte de linha selecionado.
        
        Returns:
            LineClippingAlgorithm: Algoritmo de recorte atual
        """
        return self._selected_line_clipper

    def clip_rect(self) -> QRectF:
        """
        Retorna o retângulo de recorte atual.
        
        Returns:
            QRectF: Retângulo de recorte normalizado
        """
        """Returns the current clipping rectangle (normalized)."""
        return self._clip_rect.normalized()  # Always return normalized rect

    # --- Setters (com emissão de sinal em caso de mudança) ---
    def set_drawing_mode(self, mode: DrawingMode):
        """
        Define o modo de desenho.
        
        Args:
            mode: Novo modo de desenho
        """
        if not isinstance(mode, DrawingMode):
            print(f"Warning: Invalid drawing mode type set: {mode}")
            return
        if self._drawing_mode != mode:
            self._drawing_mode = mode
            self.drawing_mode_changed.emit(mode)

    def set_draw_color(self, color: QColor):
        """
        Define a cor de desenho.
        
        Args:
            color: Nova cor de desenho
        """
        if (
            isinstance(color, QColor)
            and color.isValid()
            and self._current_draw_color != color
        ):
            self._current_draw_color = color
            self.draw_color_changed.emit(color)

    def set_unsaved_changes(self, changed: bool):
        """
        Define o estado de modificações não salvas.
        
        Args:
            changed: True se houver modificações não salvas, False caso contrário
        """
        if self._unsaved_changes != changed:
            self._unsaved_changes = changed
            self.unsaved_changes_changed.emit(changed)

    def set_current_filepath(self, filepath: Optional[str]):
        """
        Define o caminho do arquivo atual.
        
        Args:
            filepath: Novo caminho do arquivo ou None
        """
        # Normalize empty strings to None for internal consistency
        normalized_new = filepath if filepath else None
        if self._current_filepath != normalized_new:
            self._current_filepath = normalized_new
            # Emit the path as a string (empty string if None) for UI updates
            self.filepath_changed.emit(normalized_new or "")

    def set_selected_line_clipper(self, algorithm: LineClippingAlgorithm):
        """
        Define o algoritmo de recorte de linha.
        
        Args:
            algorithm: Novo algoritmo de recorte
        """
        if not isinstance(algorithm, LineClippingAlgorithm):
            print(f"Warning: Invalid line clipper type set: {algorithm}")
            return
        if self._selected_line_clipper != algorithm:
            self._selected_line_clipper = algorithm
            self.line_clipper_changed.emit(algorithm)

    def set_clip_rect(self, rect: QRectF):
        """
        Define o retângulo de recorte.
        
        Args:
            rect: Novo retângulo de recorte
        """
        """Sets the clipping rectangle, ensuring it's normalized."""
        if not isinstance(rect, QRectF):
            print(f"Warning: Invalid clip rectangle type set: {rect}")
            return
        normalized_rect = rect.normalized()
        if self._clip_rect != normalized_rect:
            self._clip_rect = normalized_rect
            self.clip_rect_changed.emit(normalized_rect)

    # --- Convenience Methods ---
    def mark_as_modified(self):
        """
        Marca o documento como modificado.
        Define a flag de modificações não salvas como True.
        """
        """Sets the unsaved changes flag to True."""
        self.set_unsaved_changes(True)

    def mark_as_saved(self):
        """
        Marca o documento como salvo.
        Define a flag de modificações não salvas como False.
        """
        """Sets the unsaved changes flag to False."""
        self.set_unsaved_changes(False)
