# graphics_editor/controllers/scene_controller.py
import math
from typing import List, Tuple, Dict, Union, Optional
from enum import Enum  # Adicionado para BezierClipStatus
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsItem,
    QMessageBox,
    QGraphicsPathItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QPainterPath

from ..models import Point, Line, Polygon, BezierCurve
from ..models import __all__ as model_names_list

_models_module = __import__("graphics_editor.models", fromlist=model_names_list)
DATA_OBJECT_TYPES = tuple(getattr(_models_module, name) for name in model_names_list)

from ..state_manager import EditorStateManager, LineClippingAlgorithm
from ..utils import clipping as clp

DataObject = Union[Point, Line, Polygon, BezierCurve]

SC_ORIGINAL_OBJECT_KEY = Qt.UserRole + 1
SC_CURRENT_REPRESENTATION_KEY = Qt.UserRole + 3
SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY = Qt.UserRole + 2


class BezierClipStatus(Enum):
    """
    Enumeração que representa o status de recorte de uma curva de Bézier em relação à janela de visualização.
    
    Atributos:
        FULLY_INSIDE: Curva completamente dentro da janela de visualização
        FULLY_OUTSIDE: Curva completamente fora da janela de visualização
        PARTIALLY_INSIDE: Curva parcialmente dentro da janela de visualização
    """
    FULLY_INSIDE = 1
    FULLY_OUTSIDE = 2
    PARTIALLY_INSIDE = 3


class SceneController(QObject):
    """
    Controlador responsável por gerenciar a cena gráfica e suas interações.
    
    Esta classe coordena a exibição e manipulação de objetos gráficos na cena,
    incluindo operações de recorte, atualização e gerenciamento de estado.
    
    Atributos:
        scene_modified: Sinal emitido quando a cena é modificada
    """
    scene_modified = pyqtSignal(bool)

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        """
        Inicializa o controlador da cena.
        
        Args:
            scene: A cena gráfica a ser controlada
            state_manager: Gerenciador de estado do editor
            parent: Objeto pai opcional
        """
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager
        self._id_to_item_map: Dict[int, QGraphicsItem] = {}

        self._clip_rect_tuple: clp.ClipRect = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()

        self.bezier_sampling_points_per_segment = 20

        self._state_manager.clip_rect_changed.connect(
            self._on_clipping_parameters_changed
        )
        self._state_manager.line_clipper_changed.connect(
            self._on_clipping_parameters_changed
        )

    def _on_clipping_parameters_changed(self, *args):
        """
        Atualiza os parâmetros de recorte quando há mudanças nas configurações.
        """
        self._clip_rect_tuple = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()
        self.refresh_all_object_clipping()

    def refresh_all_object_clipping(self):
        """
        Atualiza o recorte de todos os objetos na cena.
        """
        original_objects_to_refresh = []
        for item_id in list(self._id_to_item_map.keys()):
            item = self._id_to_item_map.get(item_id)
            if item:
                original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
                if original_obj:
                    original_objects_to_refresh.append(original_obj)

        for original_data_object in original_objects_to_refresh:
            self.update_object_item(original_data_object, mark_modified=False)
        self._scene.update()

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        """
        Obtém as coordenadas da janela de recorte como uma tupla.
        
        Returns:
            Tupla contendo as coordenadas (esquerda, topo, direita, base) da janela de recorte
        """
        rect = self._state_manager.clip_rect()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _get_clipper_function(self):
        """
        Obtém a função de recorte de linha apropriada baseada no algoritmo selecionado.
        
        Returns:
            Função de recorte de linha (Cohen-Sutherland ou Liang-Barsky)
        """
        algo = self._state_manager.selected_line_clipper()
        return (
            clp.cohen_sutherland
            if algo == LineClippingAlgorithm.COHEN_SUTHERLAND
            else clp.liang_barsky
        )

    def _get_bezier_segment_clip_status(
        self, segment_cps: List[Point], clip_rect_tuple: clp.ClipRect
    ) -> BezierClipStatus:
        """
        Determina o status de recorte de um segmento de curva de Bézier.
        
        Args:
            segment_cps: Lista de pontos de controle do segmento
            clip_rect_tuple: Tupla com as coordenadas da janela de recorte
            
        Returns:
            Status de recorte do segmento (FULLY_INSIDE, FULLY_OUTSIDE ou PARTIALLY_INSIDE)
        """
        xmin, ymin, xmax, ymax = clip_rect_tuple

        all_inside = True

        codes = [
            _compute_cohen_sutherland_code_tuple(p.get_coords(), clip_rect_tuple)
            for p in segment_cps
        ]

        for code in codes:
            if code != clp.INSIDE:
                all_inside = False
                break
        if all_inside:
            return BezierClipStatus.FULLY_INSIDE

        combined_code_for_all_outside_check = codes[0]
        all_cps_definitively_outside_one_boundary = True
        for i in range(1, len(codes)):
            if codes[i] == clp.INSIDE:
                all_cps_definitively_outside_one_boundary = False
                break
            combined_code_for_all_outside_check &= codes[i]

        if (
            all_cps_definitively_outside_one_boundary
            and combined_code_for_all_outside_check != 0
        ):

            bbox = BezierCurve.segment_bounding_box(segment_cps)
            if bbox:
                bb_xmin, bb_ymin, bb_xmax, bb_ymax = bbox
                if bb_xmax < xmin or bb_xmin > xmax or bb_ymax < ymin or bb_ymin > ymax:
                    return BezierClipStatus.FULLY_OUTSIDE

        return BezierClipStatus.PARTIALLY_INSIDE

    def _clip_bezier_segment_recursive(
        self, segment_cps: List[Point], clip_rect_tuple: clp.ClipRect, depth: int
    ) -> List[List[Point]]:
        """
        Recorta recursivamente um segmento de curva de Bézier.
        
        Args:
            segment_cps: Lista de pontos de controle do segmento
            clip_rect_tuple: Tupla com as coordenadas da janela de recorte
            depth: Profundidade atual da recursão
            
        Returns:
            Lista de listas de pontos de controle dos segmentos visíveis após o recorte
        """
        visible_segments_cps: List[List[Point]] = []

        if depth > BezierCurve.MAX_SUBDIVISION_DEPTH:

            if (
                BezierCurve.segment_control_polygon_length(segment_cps)
                < BezierCurve.SUBDIVISION_THRESHOLD * 5
            ):
                visible_segments_cps.append(segment_cps)
            return visible_segments_cps

        status = self._get_bezier_segment_clip_status(segment_cps, clip_rect_tuple)

        if status == BezierClipStatus.FULLY_INSIDE:
            visible_segments_cps.append(segment_cps)
        elif status == BezierClipStatus.FULLY_OUTSIDE:
            pass
        elif status == BezierClipStatus.PARTIALLY_INSIDE:

            if (
                BezierCurve.segment_control_polygon_length(segment_cps)
                < BezierCurve.SUBDIVISION_THRESHOLD
            ):
                visible_segments_cps.append(segment_cps)
            else:

                cps1, cps2 = BezierCurve.subdivide_segment(segment_cps)
                visible_segments_cps.extend(
                    self._clip_bezier_segment_recursive(
                        cps1, clip_rect_tuple, depth + 1
                    )
                )
                visible_segments_cps.extend(
                    self._clip_bezier_segment_recursive(
                        cps2, clip_rect_tuple, depth + 1
                    )
                )

        return visible_segments_cps

    def _clip_data_object(
        self, original_data_object: DataObject
    ) -> Tuple[Optional[DataObject], bool]:
        """
        Recorta um objeto de dados de acordo com a janela de visualização.
        
        Args:
            original_data_object: Objeto a ser recortado
            
        Returns:
            Tupla contendo o objeto recortado (ou None se completamente fora da janela)
            e um booleano indicando se o tipo de exibição foi alterado
        """
        clipped_display_object: Optional[DataObject] = None
        display_type_changed = False
        clip_rect_tuple = self._clip_rect_tuple
        line_clipper = self._clipper_func

        try:
            if isinstance(original_data_object, Point):
                clipped_coords = clp.clip_point(
                    original_data_object.get_coords(), clip_rect_tuple
                )
                if clipped_coords:
                    clipped_display_object = Point(
                        clipped_coords[0], clipped_coords[1], original_data_object.color
                    )

            elif isinstance(original_data_object, Line):
                clipped_segment_coords = line_clipper(
                    original_data_object.start.get_coords(),
                    original_data_object.end.get_coords(),
                    clip_rect_tuple,
                )
                if clipped_segment_coords:
                    p1_coords, p2_coords = clipped_segment_coords
                    clipped_display_object = Line(
                        Point(p1_coords[0], p1_coords[1]),
                        Point(p2_coords[0], p2_coords[1]),
                        original_data_object.color,
                    )

            elif isinstance(original_data_object, Polygon):
                clipped_vertices_coords = clp.sutherland_hodgman(
                    original_data_object.get_coords(), clip_rect_tuple
                )
                min_points = 2 if original_data_object.is_open else 3
                if len(clipped_vertices_coords) >= min_points:
                    clipped_points_models = [
                        Point(x, y, original_data_object.color)
                        for x, y in clipped_vertices_coords
                    ]
                    clipped_display_object = Polygon(
                        clipped_points_models,
                        is_open=original_data_object.is_open,
                        color=original_data_object.color,
                        is_filled=original_data_object.is_filled,
                    )

            elif isinstance(original_data_object, BezierCurve):
                all_visible_segment_cps_lists: List[List[Point]] = []
                for i in range(original_data_object.get_num_segments()):
                    segment_cps = original_data_object.get_segment_control_points(i)
                    if segment_cps:
                        visible_sub_cps = self._clip_bezier_segment_recursive(
                            segment_cps, clip_rect_tuple, 0
                        )
                        all_visible_segment_cps_lists.extend(visible_sub_cps)

                if all_visible_segment_cps_lists:
                    combined_cps: List[Point] = []
                    for seg_idx, seg_cps_list in enumerate(
                        all_visible_segment_cps_lists
                    ):
                        if seg_idx == 0:
                            combined_cps.extend(seg_cps_list)
                        else:
                            # Evita duplicar o ponto de conexão se os segmentos devem ser encadeados
                            if (
                                combined_cps
                                and seg_cps_list
                                and seg_cps_list[0].get_coords()
                                == combined_cps[-1].get_coords()
                            ):
                                combined_cps.extend(seg_cps_list[1:])
                            elif seg_cps_list:
                                combined_cps.extend(seg_cps_list)

                    if len(combined_cps) >= 4 and (len(combined_cps) - 1) % 3 == 0:
                        clipped_display_object = BezierCurve(
                            combined_cps, original_data_object.color
                        )
                        display_type_changed = False
                    else:
                        # Fallback: se os CPs resultantes não formam uma Bézier encadeada válida
                        # Isso pode acontecer se o recorte resultar em CPs insuficientes ou
                        # uma estrutura que não pode ser uma única BezierCurve.
                        # Neste caso, o objeto não pode ser exibido como Bezier.
                        clipped_display_object = None
                        display_type_changed = True  # Era Bézier, agora não pode ser representada como uma.
                else:
                    clipped_display_object = None
                    if original_data_object.points:
                        display_type_changed = True

            return clipped_display_object, display_type_changed

        except Exception as e:
            import traceback

            print(
                f"Error during clipping of {type(original_data_object).__name__}: {e}\n{traceback.format_exc()}"
            )
            return None, False

    def _get_required_qgraphicsitem_type(
        self, display_data_object: DataObject
    ) -> Optional[type]:
        """
        Determina o tipo de QGraphicsItem apropriado para exibir o objeto.
        
        Args:
            display_data_object: Objeto de dados a ser exibido
            
        Returns:
            Classe QGraphicsItem apropriada para o tipo de objeto
        """
        if isinstance(display_data_object, Point):
            return QGraphicsEllipseItem
        if isinstance(display_data_object, Line):
            return QGraphicsLineItem
        if isinstance(display_data_object, Polygon):
            return (
                QGraphicsPathItem
                if display_data_object.is_open
                else QGraphicsPolygonItem
            )
        if isinstance(display_data_object, BezierCurve):
            return QGraphicsPathItem
        return None

    def add_object(
        self, original_data_object: DataObject, mark_modified: bool = True
    ) -> Optional[QGraphicsItem]:
        """
        Adiciona um novo objeto à cena.
        
        Args:
            original_data_object: Objeto a ser adicionado
            mark_modified: Se True, marca a cena como modificada
            
        Returns:
            Item gráfico criado ou None se a operação falhar
        """
        if not isinstance(original_data_object, DATA_OBJECT_TYPES):
            return None

        item_id = id(original_data_object)
        if item_id in self._id_to_item_map:
            return self._id_to_item_map[item_id]

        display_data_object, display_type_changed = self._clip_data_object(
            original_data_object
        )

        if display_data_object:
            try:
                graphics_item = display_data_object.create_graphics_item()
                graphics_item.setData(SC_ORIGINAL_OBJECT_KEY, original_data_object)
                graphics_item.setData(
                    SC_CURRENT_REPRESENTATION_KEY, display_data_object
                )

                is_poly_from_bezier = isinstance(
                    original_data_object, BezierCurve
                ) and isinstance(display_data_object, Polygon)
                graphics_item.setData(
                    SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_bezier
                )

                self._scene.addItem(graphics_item)
                self._id_to_item_map[item_id] = graphics_item
                if mark_modified:
                    self.scene_modified.emit(True)
                return graphics_item
            except Exception as e:
                QMessageBox.critical(
                    None, "Erro ao Adicionar Item", f"Falha ao criar item gráfico: {e}"
                )

        if mark_modified and display_data_object is None:
            self.scene_modified.emit(True)
        return None

    def remove_data_objects(
        self, data_objects_to_remove: List[DataObject], mark_modified: bool = True
    ) -> int:
        """
        Remove uma lista de objetos da cena.
        
        Args:
            data_objects_to_remove: Lista de objetos a serem removidos
            mark_modified: Se True, marca a cena como modificada
            
        Returns:
            Número de objetos removidos com sucesso
        """
        removed_count = 0
        for data_obj in data_objects_to_remove:
            item_id = id(data_obj)
            graphics_item = self._id_to_item_map.pop(item_id, None)
            if graphics_item and graphics_item.scene():
                self._scene.removeItem(graphics_item)
                removed_count += 1
        if removed_count > 0 and mark_modified:
            self.scene_modified.emit(True)
        return removed_count

    def clear_scene(self, mark_modified: bool = True):
        """
        Remove todos os objetos da cena.
        
        Args:
            mark_modified: Se True, marca a cena como modificada
        """
        items_to_remove = list(self._id_to_item_map.values())
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)
        cleared_count = len(self._id_to_item_map)
        self._id_to_item_map.clear()
        if mark_modified:
            self.scene_modified.emit(cleared_count > 0)

    def update_object_item(
        self, original_modified_data_object: DataObject, mark_modified: bool = True
    ):
        """
        Atualiza a representação visual de um objeto na cena.
        
        Args:
            original_modified_data_object: Objeto modificado a ser atualizado
            mark_modified: Se True, marca a cena como modificada
        """
        if not isinstance(original_modified_data_object, DATA_OBJECT_TYPES):
            return

        item_id = id(original_modified_data_object)
        current_graphics_item = self._id_to_item_map.get(item_id)

        new_display_data_object, display_type_changed = self._clip_data_object(
            original_modified_data_object
        )

        if not current_graphics_item or not current_graphics_item.scene():
            if new_display_data_object:
                self.add_object(original_modified_data_object, mark_modified)
            elif mark_modified:
                self.scene_modified.emit(True)
            return

        try:
            if new_display_data_object is None:
                if current_graphics_item.scene():
                    self._scene.removeItem(current_graphics_item)
                if item_id in self._id_to_item_map:
                    del self._id_to_item_map[item_id]
                if mark_modified:
                    self.scene_modified.emit(True)
            else:
                required_new_item_type = self._get_required_qgraphicsitem_type(
                    new_display_data_object
                )
                needs_replacement = not isinstance(
                    current_graphics_item, required_new_item_type
                )

                previous_display_obj = current_graphics_item.data(
                    SC_CURRENT_REPRESENTATION_KEY
                )
                if type(previous_display_obj) != type(new_display_data_object):
                    needs_replacement = True

                if display_type_changed:
                    needs_replacement = True

                if needs_replacement:
                    if current_graphics_item.scene():
                        self._scene.removeItem(current_graphics_item)
                    new_graphics_item = new_display_data_object.create_graphics_item()
                    new_graphics_item.setData(
                        SC_ORIGINAL_OBJECT_KEY, original_modified_data_object
                    )
                    new_graphics_item.setData(
                        SC_CURRENT_REPRESENTATION_KEY, new_display_data_object
                    )
                    is_poly_from_bezier = isinstance(
                        original_modified_data_object, BezierCurve
                    ) and isinstance(new_display_data_object, Polygon)
                    new_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_bezier
                    )

                    self._scene.addItem(new_graphics_item)
                    self._id_to_item_map[item_id] = new_graphics_item
                else:
                    current_graphics_item.prepareGeometryChange()
                    current_graphics_item.setData(
                        SC_CURRENT_REPRESENTATION_KEY, new_display_data_object
                    )
                    is_poly_from_bezier = isinstance(
                        original_modified_data_object, BezierCurve
                    ) and isinstance(new_display_data_object, Polygon)
                    current_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_bezier
                    )

                    self._update_graphics_item_geometry(
                        current_graphics_item, new_display_data_object
                    )
                    self._apply_style_to_item(
                        current_graphics_item, new_display_data_object
                    )
                    current_graphics_item.update()

                if mark_modified:
                    self.scene_modified.emit(True)
        except Exception as e:
            QMessageBox.critical(
                None, "Erro ao Atualizar Item", f"Falha ao atualizar item: {e}"
            )

    def _update_graphics_item_geometry(
        self, item: QGraphicsItem, display_data: DataObject
    ):
        """
        Atualiza a geometria de um item gráfico baseado nos dados de exibição.
        
        Args:
            item: Item gráfico a ser atualizado
            display_data: Dados que definem a nova geometria
        """
        try:
            if isinstance(display_data, Point) and isinstance(
                item, QGraphicsEllipseItem
            ):
                size, offset = (
                    display_data.GRAPHICS_SIZE,
                    display_data.GRAPHICS_SIZE / 2.0,
                )
                item.setRect(
                    QRectF(display_data.x - offset, display_data.y - offset, size, size)
                )
            elif isinstance(display_data, Line) and isinstance(item, QGraphicsLineItem):
                item.setLine(
                    QLineF(
                        display_data.start.to_qpointf(), display_data.end.to_qpointf()
                    )
                )
            elif isinstance(display_data, Polygon):
                is_poly_from_bezier = (
                    item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True
                )
                if display_data.is_open or is_poly_from_bezier:
                    if isinstance(item, QGraphicsPathItem):
                        new_path = QPainterPath()
                        if display_data.points:
                            new_path.moveTo(display_data.points[0].to_qpointf())
                            for p_model in display_data.points[1:]:
                                new_path.lineTo(p_model.to_qpointf())
                        item.setPath(new_path)
                else:
                    if isinstance(item, QGraphicsPolygonItem):
                        item.setPolygon(
                            QPolygonF([p.to_qpointf() for p in display_data.points])
                        )
            elif isinstance(display_data, BezierCurve) and isinstance(
                item, QGraphicsPathItem
            ):

                temp_item_for_path = display_data.create_graphics_item()
                if isinstance(temp_item_for_path, QGraphicsPathItem):
                    item.setPath(temp_item_for_path.path())

        except Exception as e:
            print(
                f"ERROR in _update_graphics_item_geometry for {type(display_data)}/{type(item)}: {e}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, display_data: DataObject):
        """
        Aplica o estilo visual a um item gráfico.
        
        Args:
            item: Item gráfico a ser estilizado
            display_data: Dados que definem o estilo
        """
        if not hasattr(display_data, "color"):
            return
        color = display_data.color if display_data.color.isValid() else QColor(Qt.black)
        pen = QPen(Qt.NoPen)
        brush = QBrush(Qt.NoBrush)
        is_poly_from_bezier = item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True

        if isinstance(display_data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(display_data, Line):
            pen = QPen(color, display_data.GRAPHICS_WIDTH, Qt.SolidLine)
        elif isinstance(display_data, Polygon):
            pen = QPen(color, Polygon.GRAPHICS_BORDER_WIDTH)
            pen.setStyle(
                Qt.DashLine
                if display_data.is_open or is_poly_from_bezier
                else Qt.SolidLine
            )
            if (
                not display_data.is_open
                and not is_poly_from_bezier
                and display_data.is_filled
            ):
                brush.setStyle(Qt.SolidPattern)
                fill_color = QColor(color)
                fill_color.setAlphaF(Polygon.GRAPHICS_FILL_ALPHA)
                brush.setColor(fill_color)
        elif isinstance(display_data, BezierCurve):
            pen = QPen(color, BezierCurve.GRAPHICS_WIDTH, Qt.SolidLine)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)

        if hasattr(item, "setPen"):
            item.setPen(pen)
        if hasattr(item, "setBrush"):
            item.setBrush(brush)

    def get_item_for_original_object_id(
        self, original_object_id: int
    ) -> Optional[QGraphicsItem]:
        """
        Obtém o item gráfico associado a um ID de objeto original.
        
        Args:
            original_object_id: ID do objeto original
            
        Returns:
            Item gráfico associado ou None se não encontrado
        """
        return self._id_to_item_map.get(original_object_id)

    def get_original_object_for_item(self, item: QGraphicsItem) -> Optional[DataObject]:
        """
        Obtém o objeto de dados original associado a um item gráfico.
        
        Args:
            item: Item gráfico
            
        Returns:
            Objeto de dados original ou None se não encontrado
        """
        data = item.data(SC_ORIGINAL_OBJECT_KEY)
        return data if isinstance(data, DATA_OBJECT_TYPES) else None

    def get_current_representation_for_item(
        self, item: QGraphicsItem
    ) -> Optional[DataObject]:
        """
        Obtém a representação atual de um item gráfico.
        
        Args:
            item: Item gráfico
            
        Returns:
            Representação atual do objeto ou None se não encontrada
        """
        data = item.data(SC_CURRENT_REPRESENTATION_KEY)
        return data if isinstance(data, DATA_OBJECT_TYPES) else None

    def get_all_original_data_objects(self) -> List[DataObject]:
        """
        Obtém todos os objetos de dados originais na cena.
        
        Returns:
            Lista de todos os objetos de dados originais
        """
        return [
            item.data(SC_ORIGINAL_OBJECT_KEY)
            for item in self._id_to_item_map.values()
            if item.data(SC_ORIGINAL_OBJECT_KEY)
            and isinstance(item.data(SC_ORIGINAL_OBJECT_KEY), DATA_OBJECT_TYPES)
        ]

    def get_selected_data_objects(self) -> List[DataObject]:
        """
        Obtém todos os objetos de dados atualmente selecionados na cena.
        
        Returns:
            Lista de objetos de dados selecionados
        """
        return [
            item.data(SC_ORIGINAL_OBJECT_KEY)
            for item in self._scene.selectedItems()
            if item.data(SC_ORIGINAL_OBJECT_KEY)
            and isinstance(item.data(SC_ORIGINAL_OBJECT_KEY), DATA_OBJECT_TYPES)
        ]


def _compute_cohen_sutherland_code_tuple(
    point: Tuple[float, float], clip_rect: clp.ClipRect
) -> int:
    """
    Calcula o código de região de Cohen-Sutherland para um ponto.
    
    Args:
        point: Tupla (x, y) representando o ponto
        clip_rect: Tupla com as coordenadas da janela de recorte
        
    Returns:
        Código de região de Cohen-Sutherland
    """
    x, y = point
    xmin, ymin, xmax, ymax = clip_rect
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)
    code = clp.INSIDE
    if x < actual_xmin:
        code |= clp.LEFT
    elif x > actual_xmax:
        code |= clp.RIGHT
    if y < actual_ymin:
        code |= clp.BOTTOM
    elif y > actual_ymax:
        code |= clp.TOP
    return code
