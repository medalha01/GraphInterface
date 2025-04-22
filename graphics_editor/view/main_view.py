# graphics_editor/view/main_view.py

from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt5.QtCore import Qt, QPoint, QPointF, pyqtSignal, QRectF, QSize
from PyQt5.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QPainter,
    QTransform,
    QKeyEvent,
    QCursor,
)


class GraphicsView(QGraphicsView):
    """
    View customizada para exibir a cena gráfica, com zoom, pan e rotação.
    """

    # Define os limites de escala diretamente na View
    VIEW_SCALE_MIN = 0.02  # Zoom out maior
    VIEW_SCALE_MAX = 50.0  # Zoom in maior

    # Sinais com coordenadas da CENA
    scene_left_clicked = pyqtSignal(QPointF)
    scene_right_clicked = pyqtSignal(QPointF)
    scene_mouse_moved = pyqtSignal(QPointF)
    delete_requested = pyqtSignal()  # Sinal para deleção via teclado
    # Sinais para notificar UI sobre mudanças na view
    scale_changed = pyqtSignal()
    rotation_changed = pyqtSignal()

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self._current_scale: float = 1.0
        self._current_rotation: float = 0.0  # Rotação em graus
        self._is_panning: bool = False
        self._last_pan_point: QPoint = QPoint()
        self._zoom_sensitivity: float = 0.1  # Ajuste a sensibilidade do zoom aqui
        self._rotation_step: float = 5.0  # Graus por passo (Shift + Setas)

        # Configurações de renderização e comportamento
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(
            QGraphicsView.AnchorUnderMouse
        )  # Zoom centraliza no mouse
        self.setResizeAnchor(
            QGraphicsView.AnchorViewCenter
        )  # Redimensionar centraliza na view
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag)  # Modo padrão: seleção
        self.setOptimizationFlag(
            QGraphicsView.DontAdjustForAntialiasing, True
        )  # Opcional: performance
        self.setViewportUpdateMode(
            QGraphicsView.FullViewportUpdate  # Needed for smooth rotation/zoom
            # QGraphicsView.BoundingRectViewportUpdate # More performant but can have artifacts
        )

    # --- Getters ---
    def get_scale(self) -> float:
        """Retorna o fator de escala atual."""
        return self._current_scale

    def get_rotation_angle(self) -> float:
        """Retorna o ângulo de rotação atual em graus."""
        return self._current_rotation

    # --- Setters Controlados ---
    def set_scale(self, scale: float, center_on_mouse: bool = True):
        """Define a escala da view, com limites."""
        # Usa as constantes definidas NESTA classe
        min_scale = self.VIEW_SCALE_MIN
        max_scale = self.VIEW_SCALE_MAX
        clamped_scale = max(min_scale, min(scale, max_scale))

        if abs(self._current_scale - clamped_scale) < 1e-6:
            return  # Sem mudança significativa

        old_scale = self._current_scale
        self._current_scale = clamped_scale
        scale_factor = self._current_scale / old_scale

        # Define o ponto de ancoragem para o zoom
        anchor = (
            QGraphicsView.AnchorUnderMouse
            if center_on_mouse
            else QGraphicsView.AnchorViewCenter
        )
        current_anchor = self.transformationAnchor()  # Salva o anchor atual
        self.setTransformationAnchor(anchor)
        # Apply scale using QGraphicsView's scale method
        self.scale(scale_factor, scale_factor)
        self.setTransformationAnchor(current_anchor)  # Restaura anchor

        self.scale_changed.emit()  # Notifica a UI

    def set_rotation_angle(self, angle: float):
        """Define o ângulo de rotação da view em graus."""
        # Normaliza ângulo para [-180, 180) para consistência interna (opcional)
        # normalized_angle = ((angle + 180.0) % 360.0) - 180.0
        # Ou mantém acumulado como está, que é o comportamento do QGraphicsView.rotate

        if abs(self._current_rotation - angle) < 1e-6:
            return  # Sem mudança

        delta_angle = angle - self._current_rotation
        self._current_rotation = angle  # Store the absolute angle

        # Define o ponto de ancoragem para rotação (centro da view é mais comum)
        anchor = QGraphicsView.AnchorViewCenter
        current_anchor = self.transformationAnchor()
        self.setTransformationAnchor(anchor)
        # Apply incremental rotation using QGraphicsView's rotate method
        self.rotate(delta_angle)
        self.setTransformationAnchor(current_anchor)

        self.rotation_changed.emit()  # Notifica a UI

    def set_drag_mode(self, mode: QGraphicsView.DragMode):
        """Define o modo de arrasto e ajusta o cursor apropriado."""
        super().setDragMode(mode)
        if mode == QGraphicsView.ScrollHandDrag:
            self.setCursor(Qt.OpenHandCursor)
        elif mode == QGraphicsView.RubberBandDrag:
            self.setCursor(Qt.ArrowCursor)
        elif mode == QGraphicsView.NoDrag:
            # Use CrossCursor for drawing modes
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)  # Default

    # --- Event Handlers ---

    def mousePressEvent(self, event: QMouseEvent):
        """Captura cliques do mouse para iniciar pan ou emitir sinais."""
        scene_pos = self.mapToScene(event.pos())

        if event.button() == Qt.LeftButton:
            if self.dragMode() == QGraphicsView.ScrollHandDrag:
                self._is_panning = True
                self._last_pan_point = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            elif self.dragMode() == QGraphicsView.NoDrag:
                # Emit signal for drawing modes
                self.scene_left_clicked.emit(scene_pos)
                event.accept()  # Consume event, don't pass to base for NoDrag
            else:  # RubberBandDrag or others
                # Emit signal for potential selection start AND pass to base
                self.scene_left_clicked.emit(scene_pos)
                super().mousePressEvent(event)

        elif event.button() == Qt.RightButton:
            # Emit signal for editor (e.g., finish polygon/bezier)
            self.scene_right_clicked.emit(scene_pos)
            # Don't pass to base to prevent default context menu of QGraphicsView
            event.accept()

        elif event.button() == Qt.MiddleButton:
            # Always initiate pan with middle button, regardless of dragMode
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Captura movimento para pan ou emissão de posição."""
        scene_pos = self.mapToScene(event.pos())
        # Always emit mouse move for status bar coordinates etc.
        self.scene_mouse_moved.emit(scene_pos)

        if self._is_panning:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            # Translate the view by adjusting the scrollbars
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
        else:
            # If not panning, pass event to base class for selection (RubberBandDrag)
            # or drawing preview (NoDrag, handled by Editor via scene_mouse_moved signal)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Captura liberação do mouse para finalizar pan."""
        if self._is_panning and (
            event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton
        ):
            self._is_panning = False
            # Restore cursor based on current drag mode
            self.set_drag_mode(self.dragMode())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Captura scroll do mouse para aplicar zoom."""
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        # Exponential zoom factor for a smoother feel
        zoom_factor = 1.0 + (self._zoom_sensitivity * (delta / 120.0))
        new_scale = self._current_scale * zoom_factor
        # Use set_scale which applies limits and emits signal
        self.set_scale(new_scale, center_on_mouse=True)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """Captura teclas para rotação (Shift+Setas) e deleção (Delete/Backspace)."""
        # Rotation with Shift + Arrow Keys
        if event.modifiers() & Qt.ShiftModifier:
            angle_delta = 0.0
            if event.key() == Qt.Key_Left:
                angle_delta = -self._rotation_step
            elif event.key() == Qt.Key_Right:
                angle_delta = self._rotation_step
            # Optional: Up/Down for rotation
            # elif event.key() == Qt.Key_Up: angle_delta = self._rotation_step
            # elif event.key() == Qt.Key_Down: angle_delta = -self._rotation_step

            if angle_delta != 0.0:
                # Apply rotation via setter which handles signals
                self.set_rotation_angle(self._current_rotation + angle_delta)
                event.accept()
                return

        # Deletion Request
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.delete_requested.emit()
            event.accept()
            return

        # Pass other key events to the base class (e.g., for item navigation)
        super().keyPressEvent(event)

    # --- Métodos de Controle ---

    def reset_view(self):
        """Reseta zoom, pan e rotação para o padrão."""
        old_scale = self._current_scale
        old_rotation = self._current_rotation

        # Reset transformation matrix completely
        self.setTransform(QTransform())

        self._current_scale = 1.0
        self._current_rotation = 0.0
        self._is_panning = False

        # Ensure cursor is appropriate for the default mode (likely RubberBandDrag)
        self.set_drag_mode(self.dragMode())

        # Emit signals only if there was an actual change to update UI
        if abs(old_scale - 1.0) > 1e-6:
            self.scale_changed.emit()
        if abs(old_rotation - 0.0) > 1e-6:
            self.rotation_changed.emit()

        # Optionally center on a specific point (e.g., origin)
        # self.centerOn(0, 0)
        self.viewport().update()  # Force redraw
