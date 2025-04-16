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
)
from PyQt5.QtCore import Qt, QLocale
from typing import Optional, Dict, Any


class TransformationDialog(QDialog):
    """Diálogo para selecionar e parametrizar transformações 2D."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar Transformação 2D")
        self._parameters: Optional[Dict[str, Any]] = (
            None  # Armazena parâmetros validados
        )
        self._setup_ui()
        self._update_parameter_fields()  # Mostra campos iniciais corretos

    def _setup_ui(self) -> None:
        """Configura a interface do diálogo."""
        main_layout = QVBoxLayout(self)
        locale = QLocale()  # Para formatar spinboxes

        # --- Seleção do Tipo ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                "Translação",
                "Escala (rel. ao Centro)",
                "Rotação (rel. à Origem)",
                "Rotação (rel. ao Centro)",
                "Rotação (rel. a Ponto)",
            ]
        )
        self.type_combo.currentIndexChanged.connect(self._update_parameter_fields)
        type_layout.addWidget(self.type_combo)
        main_layout.addLayout(type_layout)

        # --- Parâmetros (Grupos que são mostrados/ocultos) ---

        # Translação (dx, dy)
        self.translation_group = QGroupBox("Parâmetros de Translação")
        trans_layout = QVBoxLayout()
        self.dx_input = self._create_spinbox(
            trans_layout, locale, "Deslocamento X (dx):", -9999, 9999, 0.0, 1.0
        )
        self.dy_input = self._create_spinbox(
            trans_layout, locale, "Deslocamento Y (dy):", -9999, 9999, 0.0, 1.0
        )
        self.translation_group.setLayout(trans_layout)
        main_layout.addWidget(self.translation_group)

        # Escala (sx, sy)
        self.scaling_group = QGroupBox("Parâmetros de Escala")
        scale_layout = QVBoxLayout()
        # Permite negativo para espelhamento, mas evita zero
        self.sx_input = self._create_spinbox(
            scale_layout, locale, "Fator X (sx):", -100, 100, 1.0, 0.1, 3
        )
        self.sy_input = self._create_spinbox(
            scale_layout, locale, "Fator Y (sy):", -100, 100, 1.0, 0.1, 3
        )
        scale_layout.addWidget(
            QLabel("<small><i>Valores negativos espelham. Evite zero.</i></small>")
        )
        self.scaling_group.setLayout(scale_layout)
        main_layout.addWidget(self.scaling_group)

        # Rotação (ângulo) - Usado por 3 tipos
        self.rotation_group = QGroupBox("Parâmetros de Rotação")
        rot_layout = QVBoxLayout()
        self.angle_input = self._create_spinbox(
            rot_layout, locale, "Ângulo (graus):", -3600, 3600, 0.0, 5.0, 2
        )
        rot_layout.addWidget(QLabel("<small><i>Positivo: Anti-horário</i></small>"))
        self.rotation_group.setLayout(rot_layout)
        main_layout.addWidget(self.rotation_group)

        # Ponto Arbitrário (px, py) - Usado por "Rotação (rel. Ponto)"
        self.arbitrary_point_group = QGroupBox("Ponto de Rotação")
        arb_layout = QVBoxLayout()
        self.px_input = self._create_spinbox(
            arb_layout, locale, "Coord. X (px):", -9999, 9999
        )
        self.py_input = self._create_spinbox(
            arb_layout, locale, "Coord. Y (py):", -9999, 9999
        )
        self.arbitrary_point_group.setLayout(arb_layout)
        main_layout.addWidget(self.arbitrary_point_group)

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

    def _create_spinbox(
        self,
        layout: QVBoxLayout,
        locale: QLocale,
        label_text: str,
        min_val: float,
        max_val: float,
        default_val: float = 0.0,
        step: float = 0.1,
        decimals: int = 2,
    ) -> QDoubleSpinBox:
        """Cria um QLabel e QDoubleSpinBox em um QHBoxLayout."""
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QDoubleSpinBox()
        spinbox.setLocale(locale)  # Define locale para formatação
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(default_val)
        spinbox.setMinimumWidth(100)
        spinbox.setFocusPolicy(Qt.StrongFocus)  # Melhora usabilidade
        # spinbox.lineEdit().setSelection(0, 100) # Seleciona ao focar (opcional)

        h_layout.addWidget(label)
        h_layout.addStretch()
        h_layout.addWidget(spinbox)
        layout.addLayout(h_layout)
        return spinbox

    def _update_parameter_fields(self) -> None:
        """Mostra/oculta grupos de parâmetros conforme o tipo selecionado."""
        selected_type = self.type_combo.currentText()
        is_translation = selected_type == "Translação"
        is_scaling = "Escala" in selected_type
        is_rotation = "Rotação" in selected_type
        is_arbitrary_point = selected_type == "Rotação (rel. a Ponto)"

        self.translation_group.setVisible(is_translation)
        self.scaling_group.setVisible(is_scaling)
        self.rotation_group.setVisible(is_rotation)
        self.arbitrary_point_group.setVisible(is_arbitrary_point)

        self.adjustSize()  # Ajusta tamanho do diálogo

    def _on_accept(self) -> None:
        """Valida e armazena os parâmetros ao clicar OK/Aplicar."""
        selected_type = self.type_combo.currentText()
        params: Dict[str, Any] = {}
        epsilon = 1e-9  # Tolerância para evitar zero

        try:
            if selected_type == "Translação":
                params["type"] = "translate"
                params["dx"] = self.dx_input.value()
                params["dy"] = self.dy_input.value()
                # if abs(params['dx']) < epsilon and abs(params['dy']) < epsilon:
                #     raise ValueError("Translação nula (dx e dy são zero).")
            elif selected_type == "Escala (rel. ao Centro)":
                params["type"] = "scale_center"
                sx = self.sx_input.value()
                sy = self.sy_input.value()
                if abs(sx) < epsilon or abs(sy) < epsilon:
                    raise ValueError("Fatores de escala não podem ser zero.")
                params["sx"] = sx
                params["sy"] = sy
            elif selected_type == "Rotação (rel. à Origem)":
                params["type"] = "rotate_origin"
                params["angle"] = self.angle_input.value()
                # if abs(params['angle']) < epsilon: raise ValueError("Ângulo de rotação é zero.")
            elif selected_type == "Rotação (rel. ao Centro)":
                params["type"] = "rotate_center"
                params["angle"] = self.angle_input.value()
            elif selected_type == "Rotação (rel. a Ponto)":
                params["type"] = "rotate_arbitrary"
                params["angle"] = self.angle_input.value()
                params["px"] = self.px_input.value()
                params["py"] = self.py_input.value()
            else:
                raise ValueError(
                    f"Tipo de transformação desconhecido: '{selected_type}'"
                )

            self._parameters = params
            self.accept()  # Fecha com status OK

        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self._parameters = None  # Limpa em caso de erro

    def get_transformation_parameters(self) -> Optional[Dict[str, Any]]:
        """Retorna parâmetros validados se diálogo foi aceito, senão None."""
        return self._parameters if self.result() == QDialog.Accepted else None
