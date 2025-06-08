# graphics_editor/dialogs/camera_dialog.py
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
    QGroupBox,
    QMessageBox,
    QWidget,
)
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QVector3D
from typing import Tuple, Optional


class CameraDialog(QDialog):
    """
    Diálogo para configurar os parâmetros da câmera 3D.
    Permite definir o View Reference Point (VRP), Ponto Alvo (Target) e View Up Vector (VUP).
    """

    def __init__(
        self,
        current_vrp: QVector3D,
        current_target: QVector3D,
        current_vup: QVector3D,
        parent: Optional[QWidget] = None,
    ):
        """
        Inicializa o diálogo da câmera.

        Args:
            current_vrp: Posição atual do VRP (olho da câmera).
            current_target: Ponto alvo atual para o qual a câmera olha.
            current_vup: Vetor VUP ("para cima") atual da câmera.
            parent: Widget pai do diálogo.
        """
        super().__init__(parent)
        self.setWindowTitle("Configurar Câmera 3D")
        self._locale = QLocale()  # Para formatação dos QDoubleSpinBox

        self._initial_vrp = current_vrp
        self._initial_target = current_target
        self._initial_vup = current_vup

        # Campos de entrada para VRP, Target e VUP
        self._vrp_inputs: Tuple[QDoubleSpinBox, QDoubleSpinBox, QDoubleSpinBox]
        self._target_inputs: Tuple[QDoubleSpinBox, QDoubleSpinBox, QDoubleSpinBox]
        self._vup_inputs: Tuple[QDoubleSpinBox, QDoubleSpinBox, QDoubleSpinBox]

        self._setup_ui()
        self._load_initial_values()
        self.setMinimumWidth(380)  # Ajusta largura mínima para comportar os campos

    def _setup_ui(self) -> None:
        """Configura a interface do usuário do diálogo."""
        main_layout = QVBoxLayout(self)

        # Grupo VRP
        vrp_group = QGroupBox("Ponto de Referência da Visão (VRP / Olho da Câmera)")
        vrp_layout = QVBoxLayout(vrp_group)  # Layout vertical para o grupo
        self._vrp_inputs = self._create_vector_input_row(vrp_layout, "VRP")
        main_layout.addWidget(vrp_group)

        # Grupo Target
        target_group = QGroupBox("Ponto Alvo (Para Onde a Câmera Olha)")
        target_layout = QVBoxLayout(target_group)
        self._target_inputs = self._create_vector_input_row(target_layout, "Alvo")
        main_layout.addWidget(target_group)

        # Grupo VUP
        vup_group = QGroupBox("Vetor View Up (Direção 'Para Cima' da Câmera)")
        vup_layout = QVBoxLayout(vup_group)
        self._vup_inputs = self._create_vector_input_row(vup_layout, "VUP")
        vup_layout.addWidget(
            QLabel(
                "<small><i>Nota: VUP será normalizado. Não pode ser (quase) paralelo à direção da visão (VRP -> Alvo).</i></small>"
            )
        )
        main_layout.addWidget(vup_group)

        # Botões OK/Cancelar
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Aplicar")
        ok_button.setDefault(True)
        cancel_button = QPushButton("Cancelar")

        ok_button.clicked.connect(self._on_accept)
        cancel_button.clicked.connect(self.reject)  # Fecha o diálogo sem aplicar

        button_layout.addStretch()  # Empurra botões para a direita
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _create_vector_input_row(
        self, parent_layout: QVBoxLayout, prefix: str
    ) -> Tuple[QDoubleSpinBox, QDoubleSpinBox, QDoubleSpinBox]:
        """Cria uma linha de campos de entrada (X, Y, Z) para um vetor 3D."""
        row_layout = QHBoxLayout()  # Layout horizontal para X, Y, Z na mesma linha
        x_input = QDoubleSpinBox()
        y_input = QDoubleSpinBox()
        z_input = QDoubleSpinBox()

        inputs = [x_input, y_input, z_input]
        labels = [f"{prefix} X:", f"{prefix} Y:", f"{prefix} Z:"]

        for i, spinbox in enumerate(inputs):
            spinbox.setLocale(
                self._locale
            )  # Usa locale do sistema para separador decimal
            spinbox.setRange(-100000.0, 100000.0)  # Intervalo amplo
            spinbox.setDecimals(2)  # Duas casas decimais
            spinbox.setSingleStep(0.1)  # Incremento/decremento
            spinbox.setMinimumWidth(70)  # Largura mínima para o campo
            spinbox.setToolTip(f"Coordenada {labels[i][-2:]} do {prefix}")  # Dica

            row_layout.addWidget(QLabel(labels[i]))
            row_layout.addWidget(spinbox)
            if i < 2:
                row_layout.addSpacing(10)  # Espaçamento entre X-Y e Y-Z

        parent_layout.addLayout(row_layout)  # Adiciona a linha ao layout pai (vertical)
        return x_input, y_input, z_input

    def _load_initial_values(self) -> None:
        """Carrega os valores iniciais da câmera nos campos de entrada do diálogo."""
        self._vrp_inputs[0].setValue(self._initial_vrp.x())
        self._vrp_inputs[1].setValue(self._initial_vrp.y())
        self._vrp_inputs[2].setValue(self._initial_vrp.z())

        self._target_inputs[0].setValue(self._initial_target.x())
        self._target_inputs[1].setValue(self._initial_target.y())
        self._target_inputs[2].setValue(self._initial_target.z())

        self._vup_inputs[0].setValue(self._initial_vup.x())
        self._vup_inputs[1].setValue(self._initial_vup.y())
        self._vup_inputs[2].setValue(self._initial_vup.z())

    def _on_accept(self) -> None:
        """Valida os dados inseridos e, se válidos, fecha o diálogo com QDialog.Accepted."""
        try:
            # Coleta valores dos campos
            vrp = QVector3D(
                self._vrp_inputs[0].value(),
                self._vrp_inputs[1].value(),
                self._vrp_inputs[2].value(),
            )
            target = QVector3D(
                self._target_inputs[0].value(),
                self._target_inputs[1].value(),
                self._target_inputs[2].value(),
            )
            vup = QVector3D(
                self._vup_inputs[0].value(),
                self._vup_inputs[1].value(),
                self._vup_inputs[2].value(),
            )

            # Validações
            if vrp == target:
                QMessageBox.warning(
                    self,
                    "Entrada Inválida",
                    "O Ponto de Referência da Visão (VRP) e o Ponto Alvo não podem ser idênticos.",
                )
                return

            view_direction = (
                target - vrp
            ).normalized()  # Direção da visão (do VRP para o Target)
            if vup.lengthSquared() < 1e-9:  # VUP não pode ser vetor nulo
                QMessageBox.warning(
                    self,
                    "Entrada Inválida",
                    "O Vetor View Up (VUP) não pode ser um vetor nulo.",
                )
                return

            # Verifica se VUP é (quase) paralelo à direção da visão
            if abs(QVector3D.dotProduct(view_direction, vup.normalized())) > 0.9999:
                QMessageBox.warning(
                    self,
                    "Entrada Inválida",
                    "O Vetor View Up (VUP) não pode ser (quase) paralelo à direção da visão (VRP -> Alvo). Escolha um VUP diferente.",
                )
                return

            self.accept()  # Fecha o diálogo com sucesso
        except Exception as e:  # Captura outros erros inesperados
            QMessageBox.critical(
                self, "Erro de Entrada", f"Erro ao processar os valores da câmera: {e}"
            )

    def get_camera_parameters(self) -> Tuple[QVector3D, QVector3D, QVector3D]:
        """
        Retorna os parâmetros da câmera configurados pelo usuário.
        Este método deve ser chamado após o diálogo ser aceito (dialog.exec_() == QDialog.Accepted).

        Returns:
            Tuple[QVector3D, QVector3D, QVector3D]: Uma tupla contendo (VRP, Target, VUP).
                                                     O VUP retornado é normalizado.
        """
        vrp = QVector3D(
            self._vrp_inputs[0].value(),
            self._vrp_inputs[1].value(),
            self._vrp_inputs[2].value(),
        )
        target = QVector3D(
            self._target_inputs[0].value(),
            self._target_inputs[1].value(),
            self._target_inputs[2].value(),
        )
        vup = QVector3D(
            self._vup_inputs[0].value(),
            self._vup_inputs[1].value(),
            self._vup_inputs[2].value(),
        )
        return (
            vrp,
            target,
            vup.normalized(),
        )  # Garante que VUP retornado seja normalizado
