"""
Módulo que implementa o diálogo de transformações geométricas 2D.

Este módulo contém:
- TransformationDialog: Diálogo para selecionar e parametrizar transformações 2D
  (translação, escala, rotação)
"""

# graphics_editor/dialogs/transformation_dialog.py
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QComboBox,
    QGroupBox,
    QDoubleSpinBox,
    QWidget,
    QStackedWidget,
)
from PyQt5.QtCore import Qt, QLocale
from typing import Optional, Dict, Any, List, Tuple
import numpy as np


class TransformationDialog(QDialog):
    """
    Diálogo para selecionar e parametrizar transformações geométricas 2D e 3D.

    Permite:
    - Selecionar tipo de transformação (translação, escala, rotação).
    - Configurar parâmetros específicos.
    - Suporta transformações relativas a diferentes pontos de referência.
    - Adapta campos de entrada para 2D ou 3D.
    """

    def __init__(self, parent: Optional[QWidget] = None, is_3d: bool = False):
        """
        Inicializa o diálogo de transformações.

        Args:
            parent: Widget pai do diálogo.
            is_3d: True se a transformação for para um objeto 3D, False para 2D.
        """
        super().__init__(parent)
        self.is_3d_mode = is_3d
        dim_str = "3D" if self.is_3d_mode else "2D"
        self.setWindowTitle(f"Aplicar Transformação {dim_str}")

        self._parameters: Optional[Dict[str, Any]] = None
        self._locale = QLocale()  # Para formatar spinboxes

        self._setup_ui()
        self._update_parameter_fields()  # Mostra campos iniciais corretos
        self.setMinimumWidth(380 if self.is_3d_mode else 350)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- Seleção do Tipo ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()

        if self.is_3d_mode:
            self.type_combo.addItems(
                [
                    "Translação 3D",
                    "Escala 3D (rel. ao Centro)",
                    "Rotação 3D (eixo X, Origem)",
                    "Rotação 3D (eixo Y, Origem)",
                    "Rotação 3D (eixo Z, Origem)",
                    "Rotação 3D (eixo Arbitrário, Ponto)",
                ]
            )
        else:  # 2D
            self.type_combo.addItems(
                [
                    "Translação 2D",
                    "Escala 2D (rel. ao Centro)",
                    "Rotação 2D (rel. à Origem)",
                    "Rotação 2D (rel. ao Centro)",
                    "Rotação 2D (rel. a Ponto)",
                ]
            )
        self.type_combo.currentIndexChanged.connect(self._update_parameter_fields)
        type_layout.addWidget(self.type_combo)
        main_layout.addLayout(type_layout)

        # --- Parâmetros (Grupos que são mostrados/ocultos) ---
        # Usaremos QStackedWidget para alternar entre os painéis de parâmetros
        self.parameter_stack = QStackedWidget()
        main_layout.addWidget(self.parameter_stack)

        self._create_translation_panel()
        self._create_scaling_panel()
        self._create_rotation_panel()
        if self.is_3d_mode:
            self._create_arbitrary_axis_rotation_panel_3d()  # Apenas para 3D
        else:  # Apenas para 2D
            self._create_arbitrary_point_rotation_panel_2d()

        # --- Botões ---
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Aplicar")
        ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _create_spinbox_row(
        self,
        label_text: str,
        min_val: float,
        max_val: float,
        default_val: float = 0.0,
        step: float = 0.1,
        decimals: int = 2,
    ) -> Tuple[QHBoxLayout, QDoubleSpinBox]:
        """Cria uma linha horizontal com QLabel e QDoubleSpinBox."""
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QDoubleSpinBox()
        spinbox.setLocale(self._locale)
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(default_val)
        spinbox.setMinimumWidth(100)
        spinbox.setAlignment(Qt.AlignRight)
        h_layout.addWidget(label)
        h_layout.addStretch()
        h_layout.addWidget(spinbox)
        return h_layout, spinbox

    def _create_translation_panel(self) -> None:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        dim_str = "3D" if self.is_3d_mode else "2D"
        group = QGroupBox(f"Parâmetros de Translação {dim_str}")
        group_layout = QVBoxLayout(group)

        _, self.dx_input = self._create_spinbox_row(
            "Deslocamento X (dx):", -99999, 99999, 0.0, 1.0
        )
        group_layout.addLayout(_[0])  # Adiciona o QHBoxLayout retornado
        _, self.dy_input = self._create_spinbox_row(
            "Deslocamento Y (dy):", -99999, 99999, 0.0, 1.0
        )
        group_layout.addLayout(_[0])
        if self.is_3d_mode:
            _, self.dz_input = self._create_spinbox_row(
                "Deslocamento Z (dz):", -99999, 99999, 0.0, 1.0
            )
            group_layout.addLayout(_[0])

        layout.addWidget(group)
        self.parameter_stack.addWidget(panel)

    def _create_scaling_panel(self) -> None:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        dim_str = "3D" if self.is_3d_mode else "2D"
        group = QGroupBox(f"Parâmetros de Escala {dim_str}")
        group_layout = QVBoxLayout(group)

        _, self.sx_input = self._create_spinbox_row(
            "Fator X (sx):", -100.0, 100.0, 1.0, 0.1, 3
        )
        group_layout.addLayout(_[0])
        _, self.sy_input = self._create_spinbox_row(
            "Fator Y (sy):", -100.0, 100.0, 1.0, 0.1, 3
        )
        group_layout.addLayout(_[0])
        if self.is_3d_mode:
            _, self.sz_input = self._create_spinbox_row(
                "Fator Z (sz):", -100.0, 100.0, 1.0, 0.1, 3
            )
            group_layout.addLayout(_[0])

        group_layout.addWidget(
            QLabel(
                "<small><i>Valores negativos espelham. Próximo de zero pode colapsar.</i></small>"
            )
        )
        layout.addWidget(group)
        self.parameter_stack.addWidget(panel)

    def _create_rotation_panel(
        self,
    ) -> None:  # Rotação em torno de eixos principais ou centro
        panel = QWidget()
        layout = QVBoxLayout(panel)
        dim_str = "3D" if self.is_3d_mode else "2D"
        group = QGroupBox(f"Parâmetros de Rotação {dim_str}")
        group_layout = QVBoxLayout(group)

        _, self.angle_input = self._create_spinbox_row(
            "Ângulo (graus):", -36000, 36000, 0.0, 5.0, 2
        )
        group_layout.addLayout(_[0])
        group_layout.addWidget(
            QLabel(
                "<small><i>Positivo: Anti-horário (convenção matemática).</i></small>"
            )
        )
        layout.addWidget(group)
        self.parameter_stack.addWidget(panel)

    def _create_arbitrary_point_rotation_panel_2d(
        self,
    ) -> None:  # Para rotação 2D em torno de ponto
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Ângulo (reutiliza o grupo de rotação, mas é um painel separado no stack)
        rot_group = QGroupBox("Parâmetros de Rotação 2D")
        rot_layout = QVBoxLayout(rot_group)
        _, self.angle_input_arb_2d = self._create_spinbox_row(
            "Ângulo (graus):", -36000, 36000, 0.0, 5.0, 2
        )
        rot_layout.addLayout(_[0])
        rot_layout.addWidget(QLabel("<small><i>Positivo: Anti-horário.</i></small>"))
        layout.addWidget(rot_group)

        # Ponto arbitrário 2D
        arb_pt_group = QGroupBox("Ponto de Rotação 2D (px, py)")
        arb_pt_layout = QVBoxLayout(arb_pt_group)
        _, self.px_input_2d = self._create_spinbox_row(
            "Coord. X (px):", -99999, 99999, 0.0, 1.0
        )
        arb_pt_layout.addLayout(_[0])
        _, self.py_input_2d = self._create_spinbox_row(
            "Coord. Y (py):", -99999, 99999, 0.0, 1.0
        )
        arb_pt_layout.addLayout(_[0])
        layout.addWidget(arb_pt_group)

        self.parameter_stack.addWidget(panel)

    def _create_arbitrary_axis_rotation_panel_3d(
        self,
    ) -> None:  # Para rotação 3D em torno de eixo arbitrário
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Ângulo
        rot_group = QGroupBox("Parâmetros de Rotação 3D")
        rot_layout = QVBoxLayout(rot_group)
        _, self.angle_input_arb_3d = self._create_spinbox_row(
            "Ângulo (graus):", -36000, 36000, 0.0, 5.0, 2
        )
        rot_layout.addLayout(_[0])
        rot_layout.addWidget(
            QLabel(
                "<small><i>Positivo: Anti-horário (regra da mão direita).</i></small>"
            )
        )
        layout.addWidget(rot_group)

        # Eixo arbitrário (vetor)
        axis_vec_group = QGroupBox("Vetor do Eixo de Rotação (ax, ay, az)")
        axis_vec_layout = QVBoxLayout(axis_vec_group)
        _, self.ax_input_3d = self._create_spinbox_row(
            "Componente X (ax):", -100, 100, 1.0, 0.1
        )
        axis_vec_layout.addLayout(_[0])
        _, self.ay_input_3d = self._create_spinbox_row(
            "Componente Y (ay):", -100, 100, 0.0, 0.1
        )
        axis_vec_layout.addLayout(_[0])
        _, self.az_input_3d = self._create_spinbox_row(
            "Componente Z (az):", -100, 100, 0.0, 0.1
        )
        axis_vec_layout.addLayout(_[0])
        axis_vec_layout.addWidget(
            QLabel("<small><i>O vetor do eixo será normalizado.</i></small>")
        )
        layout.addWidget(axis_vec_group)

        # Ponto na linha do eixo
        axis_pt_group = QGroupBox("Ponto na Linha do Eixo de Rotação (px, py, pz)")
        axis_pt_layout = QVBoxLayout(axis_pt_group)
        _, self.px_input_3d = self._create_spinbox_row(
            "Coord. X (px):", -99999, 99999, 0.0, 1.0
        )
        axis_pt_layout.addLayout(_[0])
        _, self.py_input_3d = self._create_spinbox_row(
            "Coord. Y (py):", -99999, 99999, 0.0, 1.0
        )
        axis_pt_layout.addLayout(_[0])
        _, self.pz_input_3d = self._create_spinbox_row(
            "Coord. Z (pz):", -99999, 99999, 0.0, 1.0
        )
        axis_pt_layout.addLayout(_[0])
        layout.addWidget(axis_pt_group)

        self.parameter_stack.addWidget(panel)

    def _update_parameter_fields(self) -> None:
        """Atualiza qual painel de parâmetros é visível no QStackedWidget."""
        selected_text = self.type_combo.currentText()

        # Mapeia texto do ComboBox para índice do QStackedWidget
        if "Translação" in selected_text:
            self.parameter_stack.setCurrentIndex(0)
        elif "Escala" in selected_text:
            self.parameter_stack.setCurrentIndex(1)
        elif "Rotação 2D (rel. a Ponto)" == selected_text:
            self.parameter_stack.setCurrentIndex(3)  # Painel específico 2D
        elif "Rotação 3D (eixo Arbitrário, Ponto)" == selected_text:
            self.parameter_stack.setCurrentIndex(3)  # Painel específico 3D
        elif "Rotação" in selected_text:
            self.parameter_stack.setCurrentIndex(2)  # Rotações simples (eixo/centro)

        self.adjustSize()  # Ajusta tamanho do diálogo

    def _on_accept(self) -> None:
        """Valida e armazena os parâmetros ao clicar OK/Aplicar."""
        selected_type = self.type_combo.currentText()
        params: Dict[str, Any] = {}
        epsilon = (
            1e-9  # Tolerância para checagens perto de zero (principalmente para escala)
        )

        try:
            # Coleta de parâmetros com base no tipo selecionado
            if selected_type == "Translação 2D":
                params = {
                    "type": "translate_2d",
                    "dx": self.dx_input.value(),
                    "dy": self.dy_input.value(),
                }
            elif selected_type == "Translação 3D":
                params = {
                    "type": "translate_3d",
                    "dx": self.dx_input.value(),
                    "dy": self.dy_input.value(),
                    "dz": self.dz_input.value(),
                }

            elif selected_type == "Escala 2D (rel. ao Centro)":
                sx, sy = self.sx_input.value(), self.sy_input.value()
                if abs(sx) < epsilon or abs(sy) < epsilon:
                    QMessageBox.warning(
                        self,
                        "Aviso de Escala 2D",
                        "Fator de escala X ou Y próximo de zero.",
                    )
                params = {"type": "scale_center_2d", "sx": sx, "sy": sy}
            elif selected_type == "Escala 3D (rel. ao Centro)":
                sx, sy, sz = (
                    self.sx_input.value(),
                    self.sy_input.value(),
                    self.sz_input.value(),
                )
                if abs(sx) < epsilon or abs(sy) < epsilon or abs(sz) < epsilon:
                    QMessageBox.warning(
                        self,
                        "Aviso de Escala 3D",
                        "Fator de escala X, Y ou Z próximo de zero.",
                    )
                params = {"type": "scale_center_3d", "sx": sx, "sy": sy, "sz": sz}

            elif selected_type == "Rotação 2D (rel. à Origem)":
                params = {"type": "rotate_origin_2d", "angle": self.angle_input.value()}
            elif selected_type == "Rotação 2D (rel. ao Centro)":
                params = {"type": "rotate_center_2d", "angle": self.angle_input.value()}
            elif selected_type == "Rotação 2D (rel. a Ponto)":
                params = {
                    "type": "rotate_arbitrary_2d",
                    "angle": self.angle_input_arb_2d.value(),
                    "px": self.px_input_2d.value(),
                    "py": self.py_input_2d.value(),
                }

            elif selected_type == "Rotação 3D (eixo X, Origem)":
                params = {"type": "rotate_x_3d", "angle": self.angle_input.value()}
            elif selected_type == "Rotação 3D (eixo Y, Origem)":
                params = {"type": "rotate_y_3d", "angle": self.angle_input.value()}
            elif selected_type == "Rotação 3D (eixo Z, Origem)":
                params = {"type": "rotate_z_3d", "angle": self.angle_input.value()}
            elif selected_type == "Rotação 3D (eixo Arbitrário, Ponto)":
                ax, ay, az = (
                    self.ax_input_3d.value(),
                    self.ay_input_3d.value(),
                    self.az_input_3d.value(),
                )
                axis_vec = np.array([ax, ay, az], dtype=float)
                if np.linalg.norm(axis_vec) < epsilon:
                    QMessageBox.warning(
                        self,
                        "Vetor de Eixo Inválido",
                        "O vetor do eixo de rotação não pode ser nulo.",
                    )
                    return
                params = {
                    "type": "rotate_arbitrary_axis_point_3d",
                    "angle": self.angle_input_arb_3d.value(),
                    "axis_vector": axis_vec,
                    "px": self.px_input_3d.value(),
                    "py": self.py_input_3d.value(),
                    "pz": self.pz_input_3d.value(),
                }
            else:
                raise ValueError(
                    f"Tipo de transformação desconhecido: '{selected_type}'"
                )

            self._parameters = params
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Erro de Valor", str(e))
            self._parameters = None
        except Exception as e:
            QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro: {e}")
            self._parameters = None

    def get_transformation_parameters(self) -> Optional[Dict[str, Any]]:
        """Obtém os parâmetros da transformação validados."""
        return self._parameters if self.result() == QDialog.Accepted else None
