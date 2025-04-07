# graphics_editor/controllers/transformation_controller.py
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialog, QWidget # Adicionado QWidget

# Importações relativas dentro do pacote
from ..models.point import Point
from ..models.line import Line
from ..models.polygon import Polygon
from ..dialogs.transformation_dialog import TransformationDialog
from .. import transformations as tf # Importa o módulo de transformações

# Define o tipo de dado que pode ser transformado
TransformableObject = object # Alias genérico, refinado pela checagem isinstance

class TransformationController(QObject):
    """
    Controlador que gerencia a lógica para aplicar transformações 2D
    aos objetos de dados da cena (Point, Line, Polygon).
    """

    # Sinal emitido quando um objeto de dados foi modificado pela transformação
    # O argumento é o próprio objeto de dados modificado
    object_transformed = pyqtSignal(TransformableObject)

    def __init__(self, parent: QWidget = None):
        """Inicializa o controlador."""
        super().__init__(parent)

    def request_transformation(self, data_object: TransformableObject) -> None:
        """
        Inicia o processo de transformação para um objeto de dados específico.
        1. Valida o tipo do objeto.
        2. Abre o diálogo para obter os parâmetros da transformação.
        3. Se o diálogo for aceito, aplica a transformação.

        Args:
            data_object: O objeto de dados (Point, Line, Polygon) a ser transformado.
        """
        # Valida se o objeto é de um tipo suportado
        if not isinstance(data_object, (Point, Line, Polygon)):
            QMessageBox.warning(None, # Sem widget pai específico para esta mensagem
                                "Tipo Inválido",
                                f"Objeto do tipo '{type(data_object).__name__}' não pode ser transformado.")
            return

        # Cria e exibe o diálogo de transformação
        dialog = TransformationDialog() # Pai pode ser omitido ou ser a janela principal
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_transformation_parameters() # Obtém os parâmetros validados
            if params:
                # Se parâmetros válidos foram recebidos, executa a transformação
                self._perform_transformation(data_object, params)
            # else: O diálogo get_transformation_parameters já deve ter tratado erros internos

    def _perform_transformation(self, data_object: TransformableObject, params: dict) -> None:
        """
        Aplica a transformação geométrica ao objeto de dados com base nos parâmetros.

        Args:
            data_object: O objeto de dados (Point, Line, Polygon) a ser modificado.
            params: Dicionário contendo o tipo ('type') e os valores da transformação.
        """
        try:
            # 1. Extrai os vértices do objeto de dados
            if isinstance(data_object, Point):
                vertices = [data_object.get_coords()] # Lista com uma única tupla (x, y)
            elif isinstance(data_object, Line):
                vertices = data_object.get_coords() # Lista com duas tuplas [(x1, y1), (x2, y2)]
            elif isinstance(data_object, Polygon):
                vertices = data_object.get_coords() # Lista com N tuplas [(x1, y1), ..., (xn, yn)]
            else:
                # Segurança extra, embora já validado em request_transformation
                return

            if not vertices:
                 raise ValueError("Objeto selecionado não possui vértices para transformar.")

            # 2. Calcula o centro do objeto (se necessário para a transformação)
            center_x, center_y = 0.0, 0.0
            transform_type = params.get('type')
            if transform_type in ['scale_center', 'rotate_center']:
                 center = data_object.get_center() # Usa o método get_center do modelo
                 if center is None:
                     # Fallback ou erro se o centro não puder ser calculado
                     raise ValueError("Não foi possível calcular o centro do objeto para a transformação.")
                 center_x, center_y = center

            # 3. Constrói a matriz de transformação composta
            matrix = np.identity(3) # Começa com a matriz identidade

            if transform_type == 'translate':
                matrix = tf.create_translation_matrix(params['dx'], params['dy'])
            elif transform_type == 'scale_center':
                # Escala relativa ao centro: Translada para origem, escala, translada de volta
                T_to_origin = tf.create_translation_matrix(-center_x, -center_y)
                S = tf.create_scaling_matrix(params['sx'], params['sy'])
                T_back = tf.create_translation_matrix(center_x, center_y)
                matrix = T_back @ S @ T_to_origin # Ordem de aplicação: direita para esquerda
            elif transform_type == 'rotate_origin':
                # Rotação simples em torno da origem (0, 0)
                matrix = tf.create_rotation_matrix(params['angle'])
            elif transform_type == 'rotate_center':
                # Rotação relativa ao centro: Translada para origem, rotaciona, translada de volta
                T_to_origin = tf.create_translation_matrix(-center_x, -center_y)
                R = tf.create_rotation_matrix(params['angle'])
                T_back = tf.create_translation_matrix(center_x, center_y)
                matrix = T_back @ R @ T_to_origin
            elif transform_type == 'rotate_arbitrary':
                # Rotação em torno de um ponto arbitrário (px, py)
                px, py = params['px'], params['py']
                T_to_point = tf.create_translation_matrix(-px, -py)
                R = tf.create_rotation_matrix(params['angle'])
                T_back = tf.create_translation_matrix(px, py)
                matrix = T_back @ R @ T_to_point
            else:
                 raise ValueError(f"Tipo de transformação desconhecido ou não implementado: '{transform_type}'")

            # 4. Aplica a matriz de transformação aos vértices
            new_vertices = tf.apply_transformation(vertices, matrix)

            # 5. Atualiza as coordenadas no objeto de dados original
            if isinstance(data_object, Point):
                if not new_vertices: raise ValueError("Transformação resultou em vértice vazio para Ponto.")
                data_object.x, data_object.y = new_vertices[0]
            elif isinstance(data_object, Line):
                if len(new_vertices) != 2: raise ValueError("Transformação não resultou em 2 vértices para Linha.")
                data_object.start.x, data_object.start.y = new_vertices[0]
                data_object.end.x, data_object.end.y = new_vertices[1]
            elif isinstance(data_object, Polygon):
                if len(new_vertices) != len(data_object.points):
                     raise ValueError("Número de vértices transformados não corresponde ao original para Polígono.")
                # Atualiza cada ponto dentro do objeto Polygon
                for i, p in enumerate(data_object.points):
                    p.x, p.y = new_vertices[i]

            # 6. Emite o sinal notificando que o objeto foi transformado
            self.object_transformed.emit(data_object)

        except (ValueError, IndexError, KeyError, TypeError, Exception) as e:
            # Captura erros de lógica, matemática ou inesperados
            QMessageBox.critical(None, "Erro na Transformação",
                                 f"Falha ao aplicar a transformação '{params.get('type', 'desconhecido')}':\n{e}")
