# graphics_editor/state_manager.py
from PyQt5.QtCore import QObject, pyqtSignal, QRectF, Qt
from PyQt5.QtGui import QColor, QVector3D
from enum import Enum, auto
from typing import Optional, List


class DrawingMode(Enum):
    """
    Enumeração que define os modos de desenho/interação disponíveis no editor.

    Atributos:
        POINT: Modo para desenhar pontos 2D.
        LINE: Modo para desenhar linhas 2D.
        POLYGON: Modo para desenhar polígonos 2D.
        BEZIER: Modo para desenhar curvas de Bézier 2D.
        BSPLINE: Modo para desenhar curvas B-spline 2D.
        SELECT: Modo para selecionar e manipular objetos (2D e 3D).
        PAN: Modo para mover a visualização (aplicável à vista 2D; navegação 3D é separada).
    """

    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    BEZIER = auto()
    BSPLINE = auto()
    SELECT = auto()
    PAN = auto()
    # Criação de objetos 3D é feita via menu, não um modo de desenho específico aqui.


class LineClippingAlgorithm(Enum):
    """
    Enumeração que define os algoritmos de recorte de linha 2D disponíveis.
    """

    COHEN_SUTHERLAND = auto()
    LIANG_BARSKY = auto()


class ProjectionMode(Enum):
    """
    Enumeração que define os modos de projeção 3D.
    """

    ORTHOGRAPHIC = auto()
    PERSPECTIVE = (
        auto()
    )  # Não totalmente implementado na projeção, mas o estado existe.


class EditorStateManager(QObject):
    """
    Gerencia o estado central da aplicação do editor.

    Responsável por:
    - Modo de desenho atual (para 2D).
    - Cor de desenho.
    - Estado de modificações não salvas.
    - Caminho do arquivo atual (para 2D).
    - Algoritmo de recorte de linha 2D.
    - Retângulo de recorte 2D.
    - Parâmetros da câmera 3D e tipo de projeção.
    """

    # --- Sinais de Mudança de Estado ---
    drawing_mode_changed = pyqtSignal(DrawingMode)
    draw_color_changed = pyqtSignal(QColor)
    unsaved_changes_changed = pyqtSignal(bool)
    filepath_changed = pyqtSignal(str)
    line_clipper_changed = pyqtSignal(LineClippingAlgorithm)
    clip_rect_changed = pyqtSignal(QRectF)  # Para viewport 2D

    # Sinais para 3D
    camera_params_changed = pyqtSignal()  # Emitido quando VRP, target, ou VUP mudam
    projection_params_changed = pyqtSignal()  # Emitido para modo de projeção, FoV, etc.

    # --- Constantes ---
    DEFAULT_CLIP_RECT = QRectF(-500.0, -400.0, 1000.0, 800.0)  # Viewport 2D

    DEFAULT_CAMERA_VRP = QVector3D(
        100.0, 100.0, 100.0
    )  # Ponto de Referência da Visão (olho)
    DEFAULT_CAMERA_TARGET = QVector3D(0.0, 0.0, 0.0)  # Ponto para o qual a câmera olha
    DEFAULT_CAMERA_VUP = QVector3D(
        0.0, 1.0, 0.0
    )  # Vetor "para cima" da câmera (Y global)

    DEFAULT_PROJECTION_MODE = ProjectionMode.ORTHOGRAPHIC
    DEFAULT_ORTHO_BOX_SIZE = (
        200.0  # Largura/Altura da caixa de visão ortográfica no plano do alvo
    )
    DEFAULT_FOV_DEGREES = 60.0  # Campo de visão ( graus) para perspectiva
    DEFAULT_NEAR_PLANE = 0.1
    DEFAULT_FAR_PLANE = 1000.0

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
            LineClippingAlgorithm.COHEN_SUTHERLAND
        )
        self._clip_rect: QRectF = self.DEFAULT_CLIP_RECT.normalized()  # Para 2D

        # Estado da Câmera 3D
        self._camera_vrp: QVector3D = self.DEFAULT_CAMERA_VRP
        self._camera_target: QVector3D = self.DEFAULT_CAMERA_TARGET
        self._camera_vup: QVector3D = self.DEFAULT_CAMERA_VUP.normalized()

        # Estado da Projeção 3D
        self._projection_mode: ProjectionMode = self.DEFAULT_PROJECTION_MODE
        self._ortho_box_size: float = self.DEFAULT_ORTHO_BOX_SIZE
        self._fov_degrees: float = self.DEFAULT_FOV_DEGREES
        self._near_plane: float = self.DEFAULT_NEAR_PLANE
        self._far_plane: float = self.DEFAULT_FAR_PLANE
        self._aspect_ratio: float = (
            1.0  # Proporção largura/altura da viewport de projeção
        )

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
        return self._clip_rect.normalized()  # Garante normalização

    # Getters da Câmera 3D
    def camera_vrp(self) -> QVector3D:
        return self._camera_vrp

    def camera_target(self) -> QVector3D:
        return self._camera_target

    def camera_vup(self) -> QVector3D:
        return self._camera_vup

    # Getters da Projeção 3D
    def projection_mode(self) -> ProjectionMode:
        return self._projection_mode

    def ortho_box_size(self) -> float:
        return self._ortho_box_size

    def fov_degrees(self) -> float:
        return self._fov_degrees

    def near_plane(self) -> float:
        return self._near_plane

    def far_plane(self) -> float:
        return self._far_plane

    def aspect_ratio(self) -> float:
        return self._aspect_ratio

    # --- Setters ---
    def set_drawing_mode(self, mode: DrawingMode):
        """
        Define o modo de desenho.

        Args:
            mode: Novo modo de desenho
        """
        if not isinstance(mode, DrawingMode):
            print(f"Aviso: Tipo de modo de desenho inválido: {mode}")
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
        normalized_new = filepath if filepath else None
        if self._current_filepath != normalized_new:
            self._current_filepath = normalized_new
            self.filepath_changed.emit(normalized_new or "")

    def set_selected_line_clipper(self, algorithm: LineClippingAlgorithm):
        """
        Define o algoritmo de recorte de linha.

        Args:
            algorithm: Novo algoritmo de recorte
        """
        if not isinstance(algorithm, LineClippingAlgorithm):
            print(f"Aviso: Tipo de algoritmo de recorte inválido: {algorithm}")
            return
        if self._selected_line_clipper != algorithm:
            self._selected_line_clipper = algorithm
            self.line_clipper_changed.emit(algorithm)

    def set_clip_rect(self, rect: QRectF):  # Para viewport 2D
        """
        Define o retângulo de recorte.

        Args:
            rect: Novo retângulo de recorte
        """
        """Sets the clipping rectangle, ensuring it's normalized."""
        if not isinstance(rect, QRectF):
            print(f"Aviso: Tipo de retângulo de recorte inválido: {rect}")
            return
        normalized_rect = rect.normalized()
        if self._clip_rect != normalized_rect:
            self._clip_rect = normalized_rect
            self.clip_rect_changed.emit(normalized_rect)

    # Setters da Câmera 3D
    def set_camera_vrp(self, vrp: QVector3D):
        if self._camera_vrp != vrp:
            self._camera_vrp = vrp
            self.camera_params_changed.emit()

    def set_camera_target(self, target: QVector3D):
        if self._camera_target != target:
            self._camera_target = target
            self.camera_params_changed.emit()

    def set_camera_vup(self, vup: QVector3D):
        normalized_vup = vup.normalized()
        if self._camera_vup != normalized_vup:
            self._camera_vup = normalized_vup
            self.camera_params_changed.emit()

    def set_camera_parameters(self, vrp: QVector3D, target: QVector3D, vup: QVector3D):
        """Define todos os parâmetros da câmera de uma vez e emite sinal se houver mudança."""
        changed = False
        if self._camera_vrp != vrp:
            self._camera_vrp = vrp
            changed = True
        if self._camera_target != target:
            self._camera_target = target
            changed = True

        normalized_vup = vup.normalized()
        # Pequena tolerância para evitar emissão de sinal por erros de ponto flutuante
        if (self._camera_vup - normalized_vup).lengthSquared() > 1e-9:
            self._camera_vup = normalized_vup
            changed = True

        if changed:
            self.camera_params_changed.emit()

    # Setters da Projeção 3D
    def set_projection_mode(self, mode: ProjectionMode):
        if self._projection_mode != mode:
            self._projection_mode = mode
            self.projection_params_changed.emit()

    def set_ortho_box_size(self, size: float):
        if size > 0 and self._ortho_box_size != size:
            self._ortho_box_size = size
            self.projection_params_changed.emit()

    def set_fov_degrees(self, fov: float):
        if 0 < fov < 180 and self._fov_degrees != fov:  # FOV deve ser >0 e <180
            self._fov_degrees = fov
            self.projection_params_changed.emit()

    def set_near_plane(self, near: float):
        if near > 0 and near < self._far_plane and self._near_plane != near:
            self._near_plane = near
            self.projection_params_changed.emit()

    def set_far_plane(self, far: float):
        if far > 0 and far > self._near_plane and self._far_plane != far:
            self._far_plane = far
            self.projection_params_changed.emit()

    def set_aspect_ratio(self, aspect_ratio: float):
        if aspect_ratio > 0 and self._aspect_ratio != aspect_ratio:
            self._aspect_ratio = aspect_ratio
            self.projection_params_changed.emit()

    # --- Métodos de Conveniência ---
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
