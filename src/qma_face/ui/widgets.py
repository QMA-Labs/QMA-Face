from math import cos, pi, sin
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImageReader,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QAbstractButton, QWidget

from qma_face.core.i18n import tr

INK = QColor("#24243D")
MUTED = QColor("#77778E")
ACCENT = QColor("#8273D9")


class ProcessingOrbit(QWidget):
    """Animated work indicator; deliberately does not imply measured completion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(54, 54)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.advance)
        self.setAccessibleName("Processing")
        self.hide()

    def set_running(self, running):
        self.setVisible(running)
        self.timer.start() if running else self.timer.stop()

    def advance(self):
        self.angle = (self.angle + 5) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(27, 27)
        glow = QRadialGradient(0, 0, 26)
        glow.setColorAt(0, QColor(183, 157, 255, 95))
        glow.setColorAt(1, QColor(183, 157, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(-26, -26, 52, 52))
        painter.rotate(self.angle)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#8B70DF"), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(-19, -19, 38, 38), 0, 245 * 16)
        painter.setPen(QPen(QColor("#B9A4F1"), 1.5))
        painter.drawArc(QRectF(-12, -12, 24, 24), 190 * 16, 230 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#8063D5"))
        for index in range(3):
            phase = index * 2 * pi / 3
            painter.drawEllipse(QRectF(cos(phase) * 5 - 2, sin(phase) * 5 - 2, 4, 4))


def draw_symbol(painter: QPainter, name: str, rect: QRectF, color: QColor) -> None:
    painter.save()
    painter.translate(rect.center())
    painter.scale(rect.width() / 24, rect.height() / 24)
    painter.setPen(QPen(color, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if name == "plus":
        painter.drawLine(-7, 0, 7, 0)
        painter.drawLine(0, -7, 0, 7)
    elif name == "history":
        painter.drawRoundedRect(QRectF(-9, -8, 18, 15), 4, 4)
        painter.drawLine(-4, -3, 4, -3)
        painter.drawLine(-4, 2, 1, 2)
        painter.drawLine(3, 7, 6, 10)
    elif name == "upload":
        painter.drawLine(0, 3, 0, -8)
        painter.drawLine(0, -8, -4, -4)
        painter.drawLine(0, -8, 4, -4)
        path = QPainterPath()
        path.moveTo(-9, 3)
        path.lineTo(-9, 8)
        path.quadTo(-9, 10, -7, 10)
        path.lineTo(7, 10)
        path.quadTo(9, 10, 9, 8)
        path.lineTo(9, 3)
        painter.drawPath(path)
    elif name == "back":
        painter.drawLine(-8, 0, 8, 0)
        painter.drawLine(-8, 0, -3, -5)
        painter.drawLine(-8, 0, -3, 5)
    painter.restore()


class Atmosphere(QWidget):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        background = QLinearGradient(0, 0, self.width(), self.height())
        background.setColorAt(0, QColor("#F6FAFF"))
        background.setColorAt(0.5, QColor("#FAF8FF"))
        background.setColorAt(1, QColor("#EFF7FF"))
        painter.fillRect(self.rect(), background)
        center = self.rect().center()
        gradient = QRadialGradient(center.x(), self.height() * 0.4, self.width() * 0.42)
        gradient.setColorAt(0, QColor("#F0EDFC"))
        gradient.setColorAt(0.55, QColor("#F7F6FD"))
        gradient.setColorAt(1, QColor("#FAFAFD"))
        painter.fillRect(self.rect(), gradient)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(125, 137, 215, 22), 1))
        for radius in (0.25, 0.38, 0.51):
            width = self.width() * radius
            painter.drawEllipse(
                QRectF(
                    self.width() * 0.5 - width,
                    self.height() * 0.45 - width * 0.42,
                    width * 2,
                    width * 0.84,
                )
            )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(128, 144, 221, 65))
        for x, y in ((0.14, 0.22), (0.83, 0.26), (0.73, 0.72), (0.22, 0.77)):
            painter.drawEllipse(QRectF(self.width() * x, self.height() * y, 3, 3))


class CloudCompanion(QWidget):
    """A native vector companion; no external image or AI asset is loaded."""

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 145) if compact else self.setFixedSize(300, 215)
        self.setAccessibleName("Cloud companion")
        self.phase = 0.0
        self.animate = False
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)

    def set_motion_enabled(self, enabled: bool) -> None:
        self.animate = enabled
        self.timer.start() if enabled else self.timer.stop()
        self.update()

    def _tick(self) -> None:
        self.phase = (self.phase + 0.045) % (2 * pi)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2 + 4)
        scale = min(self.width() / 300, self.height() / 215)
        painter.scale(scale, scale)
        glow = QRadialGradient(0, 10, 105)
        glow.setColorAt(0, QColor(191, 176, 243, 60))
        glow.setColorAt(0.65, QColor(212, 201, 250, 24))
        glow.setColorAt(1, QColor(225, 219, 250, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(-120, -90, 240, 180))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(163, 206, 241, 110), 1.2))
        painter.drawEllipse(QRectF(-86, -76, 172, 152))
        painter.setPen(QPen(QColor(183, 163, 232, 65), 1))
        painter.drawEllipse(QRectF(-96, -85, 192, 170))

        painter.save()
        painter.rotate(-16 + (sin(self.phase) * 12 if self.animate else 0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(186, 176, 222, 90), 1))
        painter.drawEllipse(QRectF(-127, -33, 254, 67))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#B5A2E9"))
        painter.drawEllipse(QRectF(119, -10, 5, 5))
        painter.setBrush(QColor("#B3DBED"))
        painter.drawEllipse(QRectF(-126, 4, 5, 5))
        painter.restore()

        shadow = QRadialGradient(0, 65, 70)
        shadow.setColorAt(0, QColor(155, 136, 211, 42))
        shadow.setColorAt(1, QColor(189, 174, 228, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(QRectF(-84, 44, 168, 40))
        painter.translate(0, sin(self.phase) * 3 if self.animate else 0)

        cloud = QPainterPath()
        cloud.moveTo(-59, 38)
        cloud.cubicTo(-112, 36, -111, -21, -71, -23)
        cloud.cubicTo(-66, -64, -15, -76, 9, -43)
        cloud.cubicTo(31, -60, 62, -44, 63, -17)
        cloud.cubicTo(101, -16, 104, 36, 66, 38)
        cloud.closeSubpath()
        fill = QLinearGradient(-45, -58, 37, 45)
        fill.setColorAt(0, QColor("#FFFFFF"))
        fill.setColorAt(0.57, QColor("#FFFFFF"))
        fill.setColorAt(1, QColor("#E6DFF8"))
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(255, 255, 255, 215), 1.6))
        painter.drawPath(cloud)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#9584CB"))
        painter.drawRoundedRect(QRectF(-22, 2, 6, 9), 3, 3)
        painter.drawRoundedRect(QRectF(13, 2, 6, 9), 3, 3)
        painter.setPen(QPen(QColor("#9584CB"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        smile = QPainterPath()
        smile.moveTo(-6, 17)
        smile.quadTo(-1, 22, 5, 17)
        painter.drawPath(smile)
        painter.setPen(QPen(QColor("#B2A2DE"), 1.3))
        painter.drawLine(97, -54, 97, -40)
        painter.drawLine(90, -47, 104, -47)


class ActionTile(QAbstractButton):
    def __init__(self, title: str, subtitle: str, symbol: str, primary: bool = False, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.symbol = symbol
        self.primary = primary
        self.setFixedSize(196, 138)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def set_labels(self, title: str, subtitle: str) -> None:
        self.title, self.subtitle = title, subtitle
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        self.update()

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor("#C8B9F3") if self.underMouse() else QColor("#E1E6F4"), 1))
        fill = QLinearGradient(0, 0, self.width(), self.height())
        fill.setColorAt(0, QColor("#F6F0FF") if self.underMouse() else QColor(255, 255, 255, 245))
        fill.setColorAt(1, QColor("#EAF5FF"))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 24, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EEE9FA") if self.primary else QColor("#F5F4F9"))
        painter.drawRoundedRect(QRectF(self.width() / 2 - 21, 15, 42, 38), 13, 13)
        draw_symbol(painter, self.symbol, QRectF(self.width() / 2 - 12, 22, 24, 24), ACCENT)
        painter.setPen(INK)
        painter.setFont(QFont("Plus Jakarta Sans", 13, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(8, 58, self.width() - 16, 30), Qt.AlignmentFlag.AlignCenter, self.title
        )
        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(8, 88, self.width() - 16, 25), Qt.AlignmentFlag.AlignCenter, self.subtitle
        )
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ACCENT, 2))
            painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 21, 21)


class IconButton(QAbstractButton):
    def __init__(self, symbol: str, accessible_name: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.setFixedSize(44, 44)
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EEEBF7") if self.underMouse() else QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        draw_symbol(painter, self.symbol, QRectF(10, 10, 24, 24), MUTED)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(ACCENT, 2))
            painter.drawRoundedRect(QRectF(3, 3, 38, 38), 12, 12)


class UploadZone(QAbstractButton):
    fileDropped = Signal(str)

    def __init__(self, parent=None, language="en"):
        super().__init__(parent)
        self.setFixedSize(352, 138)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language = language
        self.setAccessibleName(tr("choose_photo", language))

    def set_language(self, language):
        self.language = language
        self.setAccessibleName(tr("choose_photo", language))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(352, 138)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(
            QPen(ACCENT if self.hasFocus() else QColor("#D8D1E9"), 1, Qt.PenStyle.DashLine)
        )
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 24, 24)
        draw_symbol(painter, "upload", QRectF(164, 20, 24, 24), ACCENT)
        painter.setPen(INK)
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(12, 56, 328, 30), Qt.AlignmentFlag.AlignCenter, tr("choose_photo", self.language)
        )
        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(12, 90, 328, 25), Qt.AlignmentFlag.AlignCenter, tr("drop_photo", self.language)
        )

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            self.fileDropped.emit(urls[0].toLocalFile())
            event.acceptProposedAction()


def readable_image(path: Path) -> QImageReader:
    if not path.is_file() or path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("image_size")
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if not reader.canRead():
        raise ValueError("image_type")
    size = reader.size()
    if size.width() <= 0 or size.height() <= 0 or size.width() * size.height() > 40_000_000:
        raise ValueError("image_size")
    return reader
