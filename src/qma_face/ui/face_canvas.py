import numpy as np
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from qma_face.services.geometry import GROUPS


def qt_image(image):
    rgb = image.convert("RGB")
    return QImage(
        rgb.tobytes(), rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888
    ).copy()


class FaceCanvas(QWidget):
    cropChanged = Signal()
    pointsEdited = Signal()

    def __init__(self, mode="crop", parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 240)
        self.mode = mode
        self.image = None
        self.points = None
        self.visible_groups = {group: True for group in GROUPS}
        self.crop = QRectF(0, 0, 1, 1)
        self._start = None
        self._point = None
        self.zoom = 1.0
        self.pan = QPointF()
        self._pan_start = None
        self.show_numbers = False
        self.show_attention = False
        self.attention = None
        self.setAccessibleName("Photo / face map")

    def set_image(self, image):
        self.image = image.convert("RGB").copy()
        self.pixmap = qt_image(self.image)
        self.crop = QRectF(0, 0, 1, 1)
        self.reset_view()
        self.update()

    def reset_view(self):
        self.zoom = 1.0
        self.pan = QPointF()
        self.update()

    def image_rect(self):
        if self.image is None:
            return QRectF()
        factor = min(
            (self.width() - 28) / self.image.width, (self.height() - 28) / self.image.height
        )
        width, height = (
            self.image.width * factor * self.zoom,
            self.image.height * factor * self.zoom,
        )
        return QRectF(
            (self.width() - width) / 2 + self.pan.x(),
            (self.height() - height) / 2 + self.pan.y(),
            width,
            height,
        )

    def wheelEvent(self, event):
        if self.image is None or self.mode == "crop":
            return super().wheelEvent(event)
        old = self.image_rect()
        anchor = event.position()
        local = QPointF((anchor.x() - old.x()) / old.width(), (anchor.y() - old.y()) / old.height())
        self.zoom = min(6.0, max(1.0, self.zoom * (1.2 if event.angleDelta().y() > 0 else 1 / 1.2)))
        new = self.image_rect()
        self.pan += anchor - QPointF(
            new.x() + local.x() * new.width(), new.y() + local.y() * new.height()
        )
        if self.zoom == 1:
            self.pan = QPointF()
        self.update()
        event.accept()

    def normalized(self, point):
        rect = self.image_rect()
        return QPointF(
            min(1, max(0, (point.x() - rect.x()) / rect.width())),
            min(1, max(0, (point.y() - rect.y()) / rect.height())),
        )

    def crop_box(self):
        if self.image is None:
            return None
        return (
            max(0, int(self.crop.left() * self.image.width)),
            max(0, int(self.crop.top() * self.image.height)),
            min(self.image.width, int(self.crop.right() * self.image.width)),
            min(self.image.height, int(self.crop.bottom() * self.image.height)),
        )

    def set_attention(self, values):
        self.attention = None
        if values is not None:
            matrix = np.asarray(values)
            rgba = np.zeros((*matrix.shape, 4), dtype=np.uint8)
            rgba[..., 0], rgba[..., 1], rgba[..., 2] = 244, 139, 106
            rgba[..., 3] = (np.clip(matrix, 0, 1) * 175).astype(np.uint8)
            raw = Image.fromarray(rgba).resize(self.image.size, Image.Resampling.BILINEAR)
            self.attention = QImage(
                raw.tobytes(), raw.width, raw.height, raw.width * 4, QImage.Format.Format_RGBA8888
            ).copy()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F2EFF9"))
        if self.image is None:
            return
        rect = self.image_rect()
        painter.drawImage(rect, self.pixmap)
        if self.mode == "crop":
            selected = QRectF(
                rect.x() + self.crop.x() * rect.width(),
                rect.y() + self.crop.y() * rect.height(),
                self.crop.width() * rect.width(),
                self.crop.height() * rect.height(),
            )
            shade = QPainterPath()
            shade.setFillRule(Qt.FillRule.OddEvenFill)
            shade.addRect(rect)
            shade.addRect(selected)
            painter.fillPath(shade, QColor(28, 22, 55, 110))
            painter.setPen(QPen(QColor("#D4C8FF"), 2))
            painter.drawRect(selected)
        if self.show_attention and self.attention is not None:
            painter.drawImage(rect, self.attention)
        elif self.points is not None:
            painter.setPen(QPen(QColor("#B4ECDD"), 1.0))
            for group, numbers in GROUPS.items():
                if not self.visible_groups[group]:
                    continue
                locations = [
                    QPointF(
                        rect.x() + self.points[n - 1][0] * rect.width(),
                        rect.y() + self.points[n - 1][1] * rect.height(),
                    )
                    for n in numbers
                ]
                # Eye/brow contours are separate; never connect across the bridge.
                if group in {"outline", "nose", "mouth"}:
                    for first, second in zip(locations, locations[1:], strict=False):
                        painter.drawLine(first, second)
                painter.setBrush(QColor("#D2FFF2"))
                for number, location in zip(numbers, locations, strict=True):
                    painter.drawEllipse(location, 2.4, 2.4)
                    if self.show_numbers:
                        painter.drawText(location + QPointF(4, -4), str(number))

    def mousePressEvent(self, event):
        if (
            self.image is not None
            and self.mode != "crop"
            and event.button() == Qt.MouseButton.RightButton
        ):
            self._pan_start = event.position()
            return
        if self.image is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.image_rect().contains(event.position()):
            return
        position = self.normalized(event.position())
        if self.mode == "crop":
            self._start = position
        elif self.mode == "points" and self.points is not None:
            rect = self.image_rect()
            nearest = None
            best = 14.0
            for group, numbers in GROUPS.items():
                if not self.visible_groups[group]:
                    continue
                for number in numbers:
                    point = self.points[number - 1]
                    distance = np.hypot(
                        (point[0] - position.x()) * rect.width(),
                        (point[1] - position.y()) * rect.height(),
                    )
                    if distance < best:
                        nearest, best = number - 1, distance
            self._point = nearest

    def mouseMoveEvent(self, event):
        if self.image is None:
            return
        if self._pan_start is not None:
            self.pan += event.position() - self._pan_start
            self._pan_start = event.position()
            self.update()
            return
        position = self.normalized(event.position())
        if self._start is not None:
            candidate = QRectF(self._start, position).normalized()
            if candidate.width() > 0.01 and candidate.height() > 0.01:
                self.crop = candidate
        if self._point is not None:
            self.points[self._point] = [position.x(), position.y()]
            self.pointsEdited.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        self._pan_start = None
        crop_finished = self.mode == "crop" and self._start is not None
        self._start = self._point = None
        if crop_finished:
            self.cropChanged.emit()
