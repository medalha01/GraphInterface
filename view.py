# view.py
from PyQt5.QtWidgets import (QGraphicsView, QFrame, QGraphicsScene, QRubberBand,
                             QWidget)
from PyQt5.QtGui import QPainter, QBrush, QTransform, QMouseEvent, QKeyEvent, QWheelEvent
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QPoint

from typing import Optional


class GraphicsView(QGraphicsView):
    """QGraphicsView customizado com navegação e suporte a desenho aprimorados."""

    # Sinais para interações de desenho
    scene_left_clicked = pyqtSignal(QPointF)
    scene_right_clicked = pyqtSignal(QPointF)
    scene_mouse_moved = pyqtSignal(QPointF)
    delete_requested = pyqtSignal()

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)
        self._setup_view_defaults()

        # --- Configuração ---
        self._min_zoom_factor: float = 0.1
        self._max_zoom_factor: float = 10.0
        self._zoom_increment: float = 1.15
        self._pan_step: int = 30

        self._is_panning: bool = False
        self._last_pan_point: QPoint = QPoint()

        self.setFocusPolicy(Qt.StrongFocus)


    def _setup_view_defaults(self) -> None:
        """Aplica configurações padrão à view."""
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(Qt.lightGray))
        self.setFrameShape(QFrame.NoFrame)
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setMouseTracking(True)


    def set_drag_mode(self, mode: QGraphicsView.DragMode) -> None:
        """Define o modo de arrasto para a view (ex: Pan, RubberBand)."""
        if mode == QGraphicsView.ScrollHandDrag:
             self.setCursor(Qt.OpenHandCursor)
        elif mode == QGraphicsView.NoDrag:
             self.setCursor(Qt.CrossCursor)
        else:
             self.setCursor(Qt.ArrowCursor)
        self.setDragMode(mode)


    def _zoom(self, factor: float) -> None:
        """Aplica zoom na view por um fator dado, respeitando os limites."""
        transform = self.transform()
        current_scale_x = transform.m11()
        current_scale_y = transform.m22()

        if abs(current_scale_x) < 1e-9 or abs(current_scale_y) < 1e-9:
             current_scale_x = 1.0
             current_scale_y = 1.0
             self.setTransform(QTransform().scale(current_scale_x, current_scale_y))

        new_scale_x = current_scale_x * factor
        new_scale_y = current_scale_y * factor

        clamped_scale_x = max(self._min_zoom_factor, min(new_scale_x, self._max_zoom_factor))
        clamped_scale_y = max(self._min_zoom_factor, min(new_scale_y, self._max_zoom_factor))

        if abs(clamped_scale_x - current_scale_x) > 1e-6 or abs(clamped_scale_y - current_scale_y) > 1e-6:
            effective_factor_x = clamped_scale_x / current_scale_x
            effective_factor_y = clamped_scale_y / current_scale_y
            self.scale(effective_factor_x, effective_factor_y)


    def wheelEvent(self, event: QWheelEvent) -> None:
        """Trata eventos da roda do mouse para zoom."""
        angle = event.angleDelta().y()
        if angle > 0:
            self._zoom(self._zoom_increment)
        elif angle < 0:
            self._zoom(1.0 / self._zoom_increment)


    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Trata pressionamentos de tecla para navegação e ações."""
        key = event.key()

        if key == Qt.Key_Left: self.translate(self._pan_step, 0)
        elif key == Qt.Key_Right: self.translate(-self._pan_step, 0)
        elif key == Qt.Key_Up: self.translate(0, self._pan_step)
        elif key == Qt.Key_Down: self.translate(0, -self._pan_step)
        elif key == Qt.Key_Plus or key == Qt.Key_Equal: self._zoom(self._zoom_increment)
        elif key == Qt.Key_Minus: self._zoom(1.0 / self._zoom_increment)
        elif key == Qt.Key_Delete or key == Qt.Key_Backspace: self.delete_requested.emit()
        else: super().keyPressEvent(event)


    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Trata eventos de pressionamento do mouse, emitindo sinais para desenho."""
        scene_pos = self.mapToScene(event.pos())

        if event.button() == Qt.LeftButton:
            if self.dragMode() == QGraphicsView.ScrollHandDrag:
                self._is_panning = True
                self._last_pan_point = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
            elif self.dragMode() == QGraphicsView.NoDrag:
                 self.scene_left_clicked.emit(scene_pos)
            else:
                super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            self.scene_right_clicked.emit(scene_pos)
        else:
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Trata eventos de movimento do mouse para pan ou emissão de posição."""
        scene_pos = self.mapToScene(event.pos())

        if self._is_panning and self.dragMode() == QGraphicsView.ScrollHandDrag:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x())
            vs.setValue(vs.value() - delta.y())
        elif self.dragMode() == QGraphicsView.NoDrag:
            self.scene_mouse_moved.emit(scene_pos)
        else:
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Trata eventos de liberação do mouse, finalizando o pan."""
        if event.button() == Qt.LeftButton and self._is_panning:
            self._is_panning = False
            if self.dragMode() == QGraphicsView.ScrollHandDrag:
                 self.setCursor(Qt.OpenHandCursor)
        else:
            super().mouseReleaseEvent(event)