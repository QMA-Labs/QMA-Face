import json
import threading
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
from PySide6.QtGui import (
    QFont,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qma_face.core.config import PROJECT_ROOT, data_directory
from qma_face.core.i18n import tr
from qma_face.core.storage import ChatStore
from qma_face.services.library import source_kind_label
from qma_face.services.local_ai import LocalAI
from qma_face.ui.widgets import (
    ActionTile,
    Atmosphere,
    CloudCompanion,
    IconButton,
    UploadZone,
    readable_image,
)
from qma_face.ui.worker import ReplyWorker

STYLE = """
QWidget { font-family: 'Plus Jakarta Sans', 'Vazirmatn', 'Segoe UI'; color: #24243D; }
QDialog { background: #F8F7FE; }
QLineEdit, QListWidget { background: white; border: 1px solid #E8E3F2;
 border-radius: 12px; padding: 8px; selection-background-color: #EEE9FA; }
QLabel { background: transparent; }
QLabel#brand { font-size: 14px; font-weight: 600; letter-spacing: 3px; color: #59576E; }
QLabel#headerNote { font-size: 12px; color: #8C899E; }
QLabel#headline { font-size: 40px; font-weight: 300; letter-spacing: -1px; color: #29263E; }
QLabel#caption { font-size: 15px; color: #77778E; }
QLabel#eyebrow { font-size: 12px; color: #9587C3; }
QLabel#footer { font-size: 11px; color: #9692A7; }
QLabel#error { font-size: 13px; color: #A24F64; }
QLabel#preview { border-radius: 20px; background: #FFFFFF; }
QLabel#message { font-size: 15px; padding: 4px; }
QLabel#role { font-size: 11px; color: #8D83AF; }
QComboBox { background: #FFFFFF; border: 1px solid #E8E3F2; border-radius: 12px;
 padding: 8px 14px; min-width: 106px; font-size: 12px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #FFFFFF; selection-background-color: #EEE9FA; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
 stop:0 #8D69E8, stop:1 #637FE2); color: #FFFFFF; border: none;
 border-radius: 16px; padding: 13px 24px; font-size: 14px; min-height: 22px; }
QPushButton#primary:hover { background: #7566CD; }
QPushButton#primary:focus { border: 2px solid #504485; }
QPushButton#primary:disabled { background: #C6BDD9; }
QPushButton#secondary { background: #FFFFFF; border: 1px solid #E8E3F2;
 border-radius: 16px; padding: 12px 20px; font-size: 14px; min-height: 22px; }
QPushButton#secondary:focus { border: 2px solid #8273D9; }
QPushButton#quiet { background: transparent; border: none; color: #8273D9;
 font-size: 12px; padding: 10px 14px; min-height: 24px; }
QPushButton#quiet:focus { border: 1px solid #8273D9; border-radius: 10px; }
QCheckBox { background: transparent; font-size: 12px; color: #77778E; padding: 8px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #DAD4EB; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QPlainTextEdit { background: #FFFFFF; border: 1px solid #E8E3F2;
 border-radius: 16px; padding: 12px; font-size: 14px; }
QPlainTextEdit:focus { border: 1px solid #A99BDF; }
QPushButton#translationToggle { border: 1px solid #DDD5F5; border-radius: 16px;
 background: #FFFFFF; color: #8D83AF; padding: 9px; font-size: 12px; }
QPushButton#translationToggle:checked { background: #EDE7FF; color: #6650AD; }
"""


def label(text: str, name: str, parent=None) -> QLabel:
    result = QLabel(text, parent)
    result.setObjectName(name)
    result.setAlignment(Qt.AlignmentFlag.AlignCenter)
    result.setWordWrap(True)
    result.setTextFormat(Qt.TextFormat.PlainText)
    return result


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def image_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.scaled(
        768, 768, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    ).save(buffer, "JPG", 88)
    buffer.close()
    return bytes(data)


class FaceWindow(QMainWindow):
    def __init__(self, store: ChatStore | None = None, backend=None, resume: bool = True):
        super().__init__()
        self.store = store or ChatStore(data_directory())
        self._saved_store = self.store
        self.backend = backend if backend is not None else LocalAI(log_root=self.store.root)
        self.language = self.store.setting("language", "en")
        if self.language not in {"en", "fr"}:
            self.language = "en"
        self.setWindowTitle("QMA Face")
        self.resize(1200, 820)
        self.setMinimumSize(800, 620)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setFont(QFont("Plus Jakarta Sans", 11))
        self.setStyleSheet(STYLE)
        self.selected_image: Path | None = None
        self.pending_photo: QImage | None = None
        self.active_images: dict[str, QImage] = {}
        self.chat_id: str | None = None
        self.current_screen = "home"
        self.worker: ReplyWorker | None = None
        self.reply_text = ""
        self.reply_label: QLabel | None = None
        self._reply_chat_id: str | None = None
        self._reply_language = self.language
        self._worker_closing = False
        self.surface = Atmosphere()
        self.setCentralWidget(self.surface)
        layout = QVBoxLayout(self.surface)
        layout.setContentsMargins(38, 22, 38, 22)
        layout.setSpacing(0)
        header = QHBoxLayout()
        self.back = IconButton("back", self.t("back"))
        self.back.clicked.connect(lambda: self.show_screen("home"))
        self.back.hide()
        header.addWidget(self.back)
        self.brand = label("QMA FACE", "brand")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.brand)
        header.addStretch()
        self.header_note = label("", "headerNote")
        header.addWidget(self.header_note)
        header.addSpacing(18)
        self.language_picker = QComboBox()
        self.language_picker.addItem("English", "en")
        self.language_picker.addItem("Français", "fr")
        self.language_picker.setCurrentIndex(0 if self.language == "en" else 1)
        self.language_picker.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_picker)
        self.translator = QPushButton("A/آ")
        self.translator.setFixedSize(48, 48)
        self.translator.setToolTip("Local translator · مترجم فارسی")
        self.translator.setStyleSheet(
            "QPushButton { background: #EEE8FF; color: #6553B0; border: 1px solid #D9CFF7;"
            "border-radius: 24px; font-weight: 600; padding: 0px; }"
            "QPushButton:hover { background: #DDD2FA; }"
        )
        self.translator.clicked.connect(lambda: self.open_translator())
        header.addWidget(self.translator)
        self.more = QPushButton()
        self.more.setObjectName("quiet")
        self.tools_menu = QMenu(self)
        self.more.setMenu(self.tools_menu)
        header.addWidget(self.more)
        layout.addLayout(header)
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        layout.addWidget(self.pages, 1)
        self._make_home()
        self._make_upload()
        self._make_chats()
        self._make_conversation()
        self.footer = label("", "footer")
        layout.addWidget(self.footer)
        self.retranslate()
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.activated.connect(
            lambda: self.send_message() if self.current_screen == "chat" else None
        )
        latest = self.store.get_chat(self.store.setting("last_chat_id")) if resume else None
        if latest:
            self.open_chat(latest["id"])

    def t(self, key):
        return tr(key, self.language)

    def _page(self):
        page = QWidget()
        page.setObjectName("contentPage")
        page.setStyleSheet("QWidget#contentPage { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(0)
        return page, layout

    def _make_home(self):
        self.home_page, layout = self._page()
        layout.addStretch(3)
        self.home_cloud = CloudCompanion()
        layout.addWidget(self.home_cloud, 0, Qt.AlignmentFlag.AlignHCenter)
        self.home_eyebrow = label("", "eyebrow")
        self.home_title = label("", "headline")
        self.home_caption = label("", "caption")
        layout.addWidget(self.home_eyebrow)
        layout.addSpacing(10)
        layout.addWidget(self.home_title)
        layout.addSpacing(10)
        layout.addWidget(self.home_caption)
        layout.addSpacing(32)
        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.new_chat = ActionTile("", "", "plus", primary=True)
        self.my_chats = ActionTile("", "", "history")
        self.new_chat.clicked.connect(self.begin_new_chat)
        self.my_chats.clicked.connect(lambda: self.show_screen("chats"))
        actions.addStretch()
        actions.addWidget(self.new_chat)
        actions.addWidget(self.my_chats)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch(4)
        self.pages.addWidget(self.home_page)

    def _make_upload(self):
        self.upload_page, layout = self._page()
        layout.addStretch(2)
        self.upload_cloud = CloudCompanion(compact=True)
        layout.addWidget(self.upload_cloud, 0, Qt.AlignmentFlag.AlignHCenter)
        self.upload_heading = label("", "headline")
        self.upload_caption = label("", "caption")
        layout.addWidget(self.upload_heading)
        layout.addSpacing(10)
        layout.addWidget(self.upload_caption)
        layout.addSpacing(22)
        self.upload_zone = UploadZone(language=self.language)
        self.upload_zone.clicked.connect(self.choose_photo)
        self.upload_zone.fileDropped.connect(self.select_photo)
        layout.addWidget(self.upload_zone, 0, Qt.AlignmentFlag.AlignHCenter)
        self.photo_preview = label("", "preview")
        self.photo_preview.setFixedSize(352, 200)
        self.photo_preview.hide()
        layout.addWidget(self.photo_preview, 0, Qt.AlignmentFlag.AlignHCenter)
        self.photo_error = label("", "error")
        self.photo_error.setMaximumWidth(500)
        self.photo_error.hide()
        layout.addWidget(self.photo_error, 0, Qt.AlignmentFlag.AlignHCenter)
        self.keep_photo = QCheckBox()
        self.keep_photo.hide()
        layout.addWidget(self.keep_photo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.photo_privacy = label("", "footer")
        self.photo_privacy.hide()
        layout.addWidget(self.photo_privacy)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.change_photo = self._button("secondary", self.choose_photo)
        self.change_photo.hide()
        self.start_chat = self._button("primary", self.start_conversation)
        self.start_chat.hide()
        buttons.addWidget(self.change_photo)
        buttons.addWidget(self.start_chat)
        buttons.addStretch()
        layout.addSpacing(12)
        layout.addLayout(buttons)
        self.without_photo = self._button("quiet", self.start_conversation)
        layout.addWidget(self.without_photo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(3)
        self.pages.addWidget(self.upload_page)

    def _make_chats(self):
        self.chats_page, layout = self._page()
        self.history_title = label("", "headline")
        self.history_caption = label("", "caption")
        self.chats_cloud = CloudCompanion(compact=True)
        layout.addWidget(self.chats_cloud, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.history_title)
        layout.addSpacing(10)
        layout.addWidget(self.history_caption)
        layout.addSpacing(22)
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_container = QWidget()
        self.history_container.setObjectName("historyContent")
        self.history_container.setStyleSheet("QWidget#historyContent { background: transparent; }")
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_layout.setContentsMargins(70, 8, 70, 8)
        self.history_layout.setSpacing(10)
        self.history_scroll.setWidget(self.history_container)
        layout.addWidget(self.history_scroll, 1)
        self.empty_new_chat = self._button("primary", self.begin_new_chat)
        layout.addWidget(self.empty_new_chat, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pages.addWidget(self.chats_page)

    def _make_conversation(self):
        self.chat_page, layout = self._page()
        top = QHBoxLayout()
        top.setContentsMargins(60, 0, 60, 0)
        self.chat_cloud = CloudCompanion(compact=True)
        self.chat_cloud.setFixedSize(100, 68)
        top.addWidget(self.chat_cloud)
        self.chat_heading = label("", "caption")
        self.chat_heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.chat_heading, 1)
        self.add_photo = self._button("quiet", self.choose_photo)
        top.addWidget(self.add_photo)
        self.analyse_photo = self._button("quiet", self.analyse_current_photo)
        self.analyse_photo.setMinimumSize(190, 48)
        self.analyse_photo.setStyleSheet(
            "QPushButton { background: #8273D9; color: white; border-radius: 16px; "
            "font-size: 15px; font-weight: 600; padding: 10px 20px; }"
        )
        self.analyse_photo.hide()
        top.addWidget(self.analyse_photo)
        layout.addLayout(top)
        photo_row = QHBoxLayout()
        photo_row.setContentsMargins(80, 4, 80, 8)
        self.chat_photo = label("", "preview")
        self.chat_photo.setFixedSize(76, 76)
        self.chat_photo.hide()
        photo_row.addWidget(self.chat_photo)
        self.chat_photo_note = label("", "footer")
        self.chat_photo_note.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        photo_row.addWidget(self.chat_photo_note, 1)
        self.remove_photo = self._button("quiet", self.remove_chat_photo)
        self.remove_photo.hide()
        photo_row.addWidget(self.remove_photo)
        layout.addLayout(photo_row)
        self.transcript_scroll = QScrollArea()
        self.transcript_scroll.setWidgetResizable(True)
        self.transcript = QWidget()
        self.transcript.setObjectName("transcript")
        self.transcript.setStyleSheet("QWidget#transcript { background: transparent; }")
        self.transcript_layout = QVBoxLayout(self.transcript)
        self.transcript_layout.setContentsMargins(80, 16, 80, 16)
        self.transcript_layout.setSpacing(16)
        self.transcript_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.transcript_scroll.setWidget(self.transcript)
        layout.addWidget(self.transcript_scroll, 1)
        self.request_status = label("", "eyebrow")
        self.request_status.hide()
        layout.addWidget(self.request_status)
        context_row = QHBoxLayout()
        context_row.setContentsMargins(80, 0, 80, 0)
        self.next_step = label("", "footer")
        self.next_step.setAlignment(Qt.AlignmentFlag.AlignLeft)
        context_row.addWidget(self.next_step, 1)
        self.style_picker = QComboBox()
        self.style_picker.addItem("", "scientific")
        self.style_picker.addItem("", "casual")
        self.style_picker.setCurrentIndex(
            1 if self.store.setting("answer_style") == "casual" else 0
        )
        self.style_picker.currentIndexChanged.connect(
            lambda: self.store.set_setting("answer_style", self.style_picker.currentData())
        )
        context_row.addWidget(self.style_picker)
        layout.addLayout(context_row)
        composer = QHBoxLayout()
        composer.setContentsMargins(80, 12, 80, 14)
        self.auto_translate = QPushButton("فارسی → EN")
        self.auto_translate.setObjectName("translationToggle")
        self.auto_translate.setCheckable(True)
        self.auto_translate.setChecked(self.store.setting("translate_persian", "true") == "true")
        self.auto_translate.setToolTip(
            "Translate Persian input into English locally before sending · ترجمهٔ خودکار ورودی"
        )
        self.auto_translate.toggled.connect(
            lambda checked: self.store.set_setting("translate_persian", str(checked).lower())
        )
        self.question = QPlainTextEdit()
        self.question.setFixedHeight(86)
        self.question.setTabChangesFocus(True)
        self.question.textChanged.connect(self.update_composer_direction)
        self.send = self._button("primary", self.send_message)
        self.stop_reply = self._button("secondary", self.cancel_reply)
        self.stop_reply.hide()
        composer.addWidget(self.question, 1)
        composer.addWidget(self.auto_translate)
        composer.addWidget(self.send)
        composer.addWidget(self.stop_reply)
        layout.addLayout(composer)
        self.pages.addWidget(self.chat_page)

    def _button(self, kind, callback):
        button = QPushButton()
        button.setObjectName(kind)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def change_language(self):
        draft = self.question.toPlainText()
        language = self.language_picker.currentData()
        if language not in {"en", "fr"}:
            return
        self.language = language
        self.store.set_setting("language", language)
        if self.chat_id and self.store.get_chat(self.chat_id):
            self.store.set_language(self.chat_id, language)
        self.retranslate()
        if self.current_screen == "chats":
            self.refresh_history()
        elif self.current_screen == "chat":
            self.refresh_conversation()
            self.question.setPlainText(draft)

    def retranslate(self):
        self.more.setText(self.t("tools"))
        self.more.setAccessibleName(self.t("tools"))
        self.style_picker.setItemText(0, self.t("scientific"))
        self.style_picker.setItemText(1, self.t("casual"))
        self.style_picker.setAccessibleName(self.t("style"))
        self.keep_photo.setEnabled(not self.store.memory)
        self.tools_menu.clear()
        self.tools_menu.addAction(self.t("privacy"), self.show_privacy)
        self.tools_menu.addAction(
            self.t("leave_private" if self.store.memory else "private_session"), self.toggle_private
        )
        if self.chat_id:
            self.tools_menu.addSeparator()
            self.tools_menu.addAction(self.t("compare"), self.compare_photos)
            self.tools_menu.addAction(self.t("erase_features"), self.erase_analysis)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.t("erase_all"), self.erase_all_chats)
        self.language_picker.setAccessibleName(self.t("language"))
        for cloud in (self.home_cloud, self.upload_cloud, self.chats_cloud, self.chat_cloud):
            cloud.setAccessibleName(self.t("cloud_name"))
        self.back.setAccessibleName(self.t("back"))
        self.back.setToolTip(self.t("back"))
        self.home_eyebrow.setText(self.t("companion"))
        self.home_title.setText(self.t("home_title"))
        self.home_caption.setText(self.t("home_caption"))
        self.new_chat.set_labels(self.t("new_chat"), self.t("new_subtitle"))
        self.my_chats.set_labels(self.t("my_chats"), self.t("chats_subtitle"))
        self.upload_zone.set_language(self.language)
        self.upload_heading.setText(
            self.t("photo_selected" if self.pending_photo else "upload_title")
        )
        self.upload_caption.setText(
            self.t("photo_caption" if self.pending_photo else "upload_caption")
        )
        self.keep_photo.setText(self.t("save_photo"))
        self.photo_privacy.setText(self.t("photo_privacy"))
        for widget, key in [
            (self.change_photo, "change_photo"),
            (self.start_chat, "start_chat"),
            (self.without_photo, "without_photo"),
            (self.empty_new_chat, "new_chat"),
            (self.add_photo, "add_photo"),
            (self.remove_photo, "clear_photo"),
            (self.send, "send"),
            (self.stop_reply, "stop"),
            (self.analyse_photo, "analyse"),
        ]:
            widget.setText(self.t(key))
        self.question.setPlaceholderText(self.t("question"))
        self.question.setAccessibleName(self.t("question"))
        self.question.setToolTip("Ctrl+Enter")
        self.footer.setText(self.t("footer"))
        self._header()
        self.refresh_history()

    def _header(self):
        if self.store.memory:
            self.header_note.setText(self.t("private_now"))
            return
        key = {"home": "space", "upload": "new_chat", "chats": "my_chats", "chat": "local"}[
            self.current_screen
        ]
        self.header_note.setText(self.t(key))

    def show_screen(self, name):
        screens = {"home": 0, "upload": 1, "chats": 2, "chat": 3}
        if name not in screens:
            raise ValueError("Unknown screen")
        if self.worker and self.worker.isRunning() and name != "chat":
            return
        self.current_screen = name
        self.pages.setCurrentIndex(screens[name])
        self.back.setVisible(name != "home")
        self._header()
        if name == "chats":
            self.refresh_history()

    def begin_new_chat(self):
        if self.worker and self.worker.isRunning():
            return
        self.chat_id = None
        self.selected_image = None
        self.pending_photo = None
        self.keep_photo.setChecked(False)
        self.keep_photo.hide()
        self.photo_privacy.hide()
        self.photo_preview.hide()
        self.photo_error.hide()
        self.change_photo.hide()
        self.start_chat.hide()
        self.without_photo.show()
        self.upload_zone.show()
        self.upload_cloud.show()
        self.retranslate()
        self.show_screen("upload")

    def choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("choose_photo"), "", self.t("photo_dialog")
        )
        if path:
            self.select_photo(path)

    def select_photo(self, path):
        try:
            reader = readable_image(Path(path))
            # Do not upscale small photos and hide their actual resolution from quality checks.
            if max(reader.size().width(), reader.size().height()) > 1024:
                reader.setScaledSize(
                    reader.size().scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio)
                )
            image = reader.read()
            if image.isNull():
                raise ValueError("image_decode")
        except (OSError, ValueError) as error:
            key = (
                str(error)
                if str(error) in {"image_type", "image_size", "image_decode"}
                else "image_decode"
            )
            self.photo_error.setText(self.t(key))
            self.photo_error.show()
            if self.current_screen == "chat":
                self.request_status.setText(self.t(key))
                self.request_status.show()
            return
        self.selected_image = Path(path)
        self.pending_photo = image
        self.photo_error.hide()
        if self.current_screen == "chat" and self.chat_id:
            self.active_images[self.chat_id] = image
            # Adding a photo during a chat never implies persistence consent.
            if not self.store.memory:
                self.store.attachment_path(self.chat_id).unlink(missing_ok=True)
            self.store.set_photo(self.chat_id, Path(path).name, False)
            self.refresh_conversation()
            QTimer.singleShot(0, self.analyse_current_photo)
            return
        self.upload_zone.hide()
        self.upload_cloud.hide()
        self.photo_preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                340,
                190,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.photo_preview.show()
        self.change_photo.show()
        self.start_chat.show()
        self.without_photo.hide()
        self.keep_photo.show()
        self.photo_privacy.show()
        self.retranslate()

    def start_conversation(self):
        if self.worker and self.worker.isRunning():
            return
        self.chat_id = self.store.create_chat(self.language, self.t("new_chat"))
        if self.pending_photo is not None:
            self.active_images[self.chat_id] = self.pending_photo
            kept = self.keep_photo.isChecked() and not self.store.memory
            if kept:
                if not self.pending_photo.save(
                    str(self.store.attachment_path(self.chat_id)), "PNG"
                ):
                    kept = False
            self.store.set_photo(
                self.chat_id, self.selected_image.name if self.selected_image else "photo", kept
            )
        self.open_chat(self.chat_id)
        if self.pending_photo is not None:
            QTimer.singleShot(0, self.analyse_current_photo)

    def open_chat(self, identity):
        if self.worker and self.worker.isRunning():
            return
        chat = self.store.get_chat(identity)
        if not chat:
            self.show_screen("chats")
            return
        self.chat_id = identity
        self.store.set_setting("last_chat_id", identity)
        self.language = chat["language"]
        self.store.set_setting("language", self.language)
        self.language_picker.blockSignals(True)
        self.language_picker.setCurrentIndex(0 if self.language == "en" else 1)
        self.language_picker.blockSignals(False)
        if chat["photo_kept"] and identity not in self.active_images:
            path = self.store.attachment_path(identity)
            image = QImage(str(path))
            if not image.isNull():
                self.active_images[identity] = image
        self.retranslate()
        self.refresh_conversation()
        self.show_screen("chat")

    def refresh_history(self):
        clear_layout(self.history_layout)
        chats = self.store.list_chats()
        self.history_title.setText(self.t("history_title" if chats else "empty_title"))
        self.history_caption.setText(self.t("history_caption" if chats else "empty_caption"))
        self.chats_cloud.setVisible(not chats)
        for chat in chats:
            row = QHBoxLayout()
            open_button = self._button(
                "secondary", lambda checked=False, identity=chat["id"]: self.open_chat(identity)
            )
            open_button.setText(chat["title"][:58])
            open_button.setToolTip(chat["title"])
            row.addWidget(open_button, 1)
            delete_button = self._button(
                "quiet", lambda checked=False, identity=chat["id"]: self.delete_chat(identity)
            )
            delete_button.setText(self.t("delete"))
            row.addWidget(delete_button)
            self.history_layout.addLayout(row)

    def delete_chat(self, identity):
        if self.worker and self.worker.isRunning():
            return
        self.store.delete_chat(identity)
        self.backend.stop()
        self.active_images.pop(identity, None)
        if self.chat_id == identity:
            self.chat_id = None
            self.pending_photo = None
            self.selected_image = None
            self.chat_photo.clear()
            self.photo_preview.clear()
            clear_layout(self.transcript_layout)
        self.refresh_history()

    def remove_chat_photo(self):
        if not self.chat_id or (self.worker and self.worker.isRunning()):
            return
        self.active_images.pop(self.chat_id, None)
        self.backend.stop()
        if not self.store.memory:
            self.store.attachment_path(self.chat_id).unlink(missing_ok=True)
        self.store.set_photo(self.chat_id, None, False)
        self.selected_image = None
        self.pending_photo = None
        self.refresh_conversation()

    def refresh_conversation(self):
        clear_layout(self.transcript_layout)
        self.reply_label = None
        if not self.chat_id:
            return
        chat = self.store.get_chat(self.chat_id)
        if not chat:
            return
        self.chat_heading.setText(
            (chat["title"][:36] + "…" if len(chat["title"]) > 36 else chat["title"])
            if self.store.messages(self.chat_id)
            else self.t("chat_ready")
        )
        self.chat_heading.setToolTip(chat["title"])
        image = self.active_images.get(self.chat_id)
        self.chat_photo.setVisible(image is not None)
        self.analyse_photo.setVisible(image is not None)
        self.remove_photo.setVisible(bool(chat["photo_name"]))
        if image is not None:
            self.chat_photo.setPixmap(
                QPixmap.fromImage(image).scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.chat_photo_note.setText(
                self.t("photo_saved" if chat["photo_kept"] else "photo_memory")
            )
        elif chat["photo_name"]:
            self.chat_photo_note.setText(self.t("photo_missing"))
        else:
            self.chat_photo_note.setText("")
        messages = self.store.messages(self.chat_id)
        from qma_face.services.analysis import active_analysis
        from qma_face.services.photo_quality import photo_digest
        from qma_face.ui.analysis_dialog import pil_image

        has_result = image is not None and active_analysis(messages, photo_digest(pil_image(image)))
        self.next_step.setText(
            self.t(
                "next_result"
                if has_result
                else "next_analysis"
                if image is not None
                else "next_photo"
            )
        )
        if has_result and self.is_historical_analysis(has_result):
            self.next_step.setText(
                "Résultat d’un ancien moteur : relancez l’analyse pour utiliser le nouveau."
                if self.language == "fr"
                else "Saved result from an earlier engine — run Check & analyse for a new result."
            )
        if not messages:
            guide = label(
                self.t("chat_ready_photo" if image is not None else "chat_ready_text"), "caption"
            )
            guide.setContentsMargins(16, 52, 16, 16)
            self.transcript_layout.addWidget(guide)
        else:
            for message in messages:
                self.append_bubble(message["role"], message["content"], message.get("metadata"))
        if has_result:
            self.add_analysis_suggestions()
        self.question.clear()
        self.request_status.hide()
        self._scroll_bottom()

    def append_bubble(self, role, content, metadata=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        bubble = QFrame()
        bubble.setObjectName("bubble")
        color = "#F0ECFA" if role == "user" else "#FFFFFF"
        bubble.setStyleSheet(f"QFrame#bubble {{ background: {color}; border-radius: 18px; }}")
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(5)
        name = label(self.t("you" if role == "user" else "assistant"), "role")
        name.setAlignment(Qt.AlignmentFlag.AlignLeft)
        text = label(content, "message")
        text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(name)
        inner.addWidget(text)
        self._add_input_translation(inner, metadata or {})
        if role == "assistant":
            translate = self._button("quiet", lambda: self.open_translator(text.text()))
            translate.setText("A/آ")
            translate.setStyleSheet("padding: 0px; color: #7867C7; font-size: 12px;")
            translate.setToolTip("Translate this answer · ترجمهٔ پاسخ")
            translate.setFixedSize(44, 36)
            inner.addWidget(translate, alignment=Qt.AlignmentFlag.AlignRight)
        if role == "assistant" and metadata:
            key = (
                "evidence_math"
                if metadata.get("answer_kind")
                in {"structured_analysis_explanation", "collection_calculation"}
                or metadata.get("analysis")
                or metadata.get("comparison")
                else ("evidence_source" if metadata.get("sources") else "evidence_visual")
            )
            evidence = label(self.t(key), "footer")
            evidence.setAlignment(Qt.AlignmentFlag.AlignLeft)
            inner.addWidget(evidence)
        self._add_source_button(inner, (metadata or {}).get("sources", []))
        analysis = (metadata or {}).get("analysis")
        if analysis:
            if self.is_historical_analysis(analysis):
                notice = label(
                    "Analyse enregistrée avec un ancien moteur."
                    if self.language == "fr"
                    else "Saved with an earlier engine.",
                    "footer",
                )
                inner.addWidget(notice)
            from qma_face.ui.analysis_cards import analysis_cards

            inner.addWidget(analysis_cards(analysis, self.language))
            button = self._button("quiet", lambda: self.show_analysis(analysis))
            button.setText(self.t("view_analysis"))
            button.setObjectName("analysisResultButton")
            inner.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        elif role == "assistant" and metadata and metadata.get("status") == "completed":
            button = self._button("quiet", lambda: self.export_text(content, metadata))
            button.setText(self.t("export_report"))
            inner.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble, 7)
        else:
            row.addWidget(bubble, 7)
            row.addStretch(1)
        self.transcript_layout.addLayout(row)
        return text

    @staticmethod
    def is_historical_analysis(analysis):
        try:
            current = json.loads(
                (PROJECT_ROOT / "models/engine-evaluation.json").read_text(encoding="utf-8")
            )["checkpoint_sha256"]
        except (OSError, ValueError, KeyError):
            return False
        return bool(analysis.get("checkpoint_sha256") != current)

    def _add_input_translation(self, layout, metadata):
        translation = metadata.get("input_translation")
        if not translation:
            return
        button = self._button(
            "quiet",
            lambda: QMessageBox.information(
                self, "English sent to model · متن ارسال‌شده", translation["text"]
            ),
        )
        button.setText("View English sent · مشاهدهٔ ترجمهٔ ورودی")
        layout.addWidget(button)

    def _add_source_button(self, layout, sources):
        if not sources:
            return
        button = QPushButton(f"{self.t('sources')} · {len(sources)}")
        button.setObjectName("sourceButton")
        button.setStyleSheet(
            "QPushButton { background: #F0ECFA; border: none; border-radius: 10px; "
            "padding: 8px 14px; color: #71609E; font-size: 12px; } "
            "QPushButton:hover { background: #E5DEF5; }"
        )
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self.show_sources(sources))
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)

    def show_sources(self, sources):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("source_detail"))
        dialog.resize(680, 520)
        dialog.setStyleSheet(
            "QDialog { background: #F8F7FD; } "
            "QPlainTextEdit { background: white; border: 1px solid #E5DFF4; "
            "border-radius: 18px; padding: 16px; font-size: 14px; } "
            "QPushButton { background: #8571D9; color: white; border: none; "
            "border-radius: 12px; padding: 9px 22px; }"
        )
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(self.t("source_notice"), "caption"))
        text = QPlainTextEdit()
        text.setReadOnly(True)
        sections = []
        for source in sources:
            locator = (
                f"p. {source['page']}"
                if source.get("page")
                else source.get("doi", source.get("url", ""))
            )
            sections.append(
                f"[{source['citation_id']}] {source['title']}\n{locator}\n"
                f"{source_kind_label(source['type'], self.language)}\n\n{source['text']}\n\n"
                f"{source.get('reviewed_translation', '')}\n\n"
                f"{source.get('limitations', '')}"
            )
        text.setPlainText("\n\n──────────\n\n".join(sections))
        layout.addWidget(text)
        close = QPushButton(self.t("close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def analyse_current_photo(self):
        if not self.chat_id or (self.worker and self.worker.isRunning()):
            return
        image = self.active_images.get(self.chat_id)
        if image is None:
            return
        from qma_face.ui.analysis_dialog import AnalysisDialog
        from qma_face.ui.analysis_text import text_report

        dialog = AnalysisDialog(image, self.language, self, guided_auto=True)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.analysis_report:
            self.store.add_message(
                self.chat_id,
                "assistant",
                text_report(dialog.analysis_report, self.language),
                {"status": "completed", "analysis": dialog.analysis_report},
            )
            self.refresh_conversation()
        dialog.deleteLater()

    def add_analysis_suggestions(self):
        french = self.language == "fr"
        heading = label(
            "Une question ou une réflexion personnelle ?"
            if french
            else "Ask a question or explore self-reflection?",
            "caption",
        )
        self.transcript_layout.addWidget(heading)
        suggestions = (
            [
                (
                    "Comprendre mon score",
                    "Explique mon score enregistré, les mesures et leurs "
                    "limites, avec les sources disponibles.",
                ),
                (
                    "Explorer la carte",
                    "Explique la carte d’attention et les variations par région "
                    "dans mon analyse enregistrée.",
                ),
                (
                    "Réflexion personnelle",
                    "Guide-moi dans une réflexion personnelle à partir de "
                    "mes réponses, sans déduire ma personnalité de ma photo. Commence par une "
                    "question sur mes objectifs et mes habitudes.",
                ),
            ]
            if french
            else [
                (
                    "Understand my score",
                    "Explain my saved score, measurements and their "
                    "limitations, using available sources.",
                ),
                (
                    "Explore the face map",
                    "Explain the attention map and regional sensitivity in my saved analysis.",
                ),
                (
                    "Self-reflection",
                    "Guide me through self-reflection based on my answers, "
                    "without inferring personality from my photo. Start with one question about "
                    "my goals and habits.",
                ),
            ]
        )
        row = QHBoxLayout()
        for title, prompt in suggestions:
            button = self._button(
                "quiet", lambda checked=False, text=prompt: self.use_suggestion(text)
            )
            button.setText(title)
            row.addWidget(button)
        self.transcript_layout.addLayout(row)
        self._scroll_bottom()

    def use_suggestion(self, prompt):
        self.question.setPlainText(prompt)
        self.question.setFocus()

    def update_composer_direction(self):
        if getattr(self, "_updating_direction", False):
            return
        first = next((c for c in self.question.toPlainText() if c.isalpha()), "")
        rtl = "\u0600" <= first <= "\u06ff"
        direction = Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight
        alignment = Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft
        if (
            self.question.layoutDirection() == direction
            and self.question.document().firstBlock().blockFormat().alignment() == alignment
        ):
            return
        self._updating_direction = True
        try:
            self.question.setLayoutDirection(direction)
            previous = self.question.textCursor()
            cursor = QTextCursor(self.question.document())
            cursor.select(QTextCursor.SelectionType.Document)
            block = QTextBlockFormat()
            block.setAlignment(alignment)
            cursor.mergeBlockFormat(block)
            self.question.setTextCursor(previous)
        finally:
            self._updating_direction = False

    def open_translator(self, text=None):
        if self.worker and self.worker.isRunning():
            self.request_status.setText(
                "Attendez la fin de la réponse ou arrêtez-la avant de traduire."
                if self.language == "fr"
                else "Finish or stop the reply before translating."
            )
            self.request_status.show()
            return
        from qma_face.ui.translator_dialog import TranslatorDialog

        if text is None:
            text = self.question.toPlainText()
            if not text and self.chat_id:
                text = next(
                    (
                        m["content"]
                        for m in reversed(self.store.messages(self.chat_id))
                        if m["role"] == "assistant"
                    ),
                    "",
                )
        dialog = TranslatorDialog(self.backend, text, self.language, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.use_suggestion(dialog.translated_text)
        dialog.deleteLater()

    def show_analysis(self, report):
        from qma_face.ui.analysis_dialog import AnalysisDialog

        dialog = AnalysisDialog.saved_result(
            report, self.language, self, self.active_images.get(self.chat_id)
        )
        if self.is_historical_analysis(report):
            dialog.status.setText(
                "Ancien moteur : relancez l’analyse pour obtenir un nouveau résultat."
                if self.language == "fr"
                else "Earlier engine: run a new analysis to use the current model."
            )
        dialog.exec()
        dialog.deleteLater()

    def export_text(self, text, metadata):
        from qma_face.ui.report_dialog import ReportDialog

        report = metadata.get("analysis") or metadata.get("comparison") or {}
        dialog = ReportDialog(
            text,
            self.language,
            self,
            engine_hash=report.get("checkpoint_sha256"),
            sources=metadata.get("sources", []),
        )
        dialog.exec()
        dialog.deleteLater()

    def compare_photos(self):
        if not self.chat_id or self.worker:
            return
        from qma_face.services.comparison import comparison_text
        from qma_face.ui.comparison_dialog import ComparisonDialog

        dialog = ComparisonDialog(self.language, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.comparison_report:
            self.store.add_message(
                self.chat_id,
                "assistant",
                comparison_text(dialog.comparison_report, self.language),
                {"comparison": dialog.comparison_report, "status": "completed"},
            )
            self.refresh_conversation()
        dialog.deleteLater()

    def show_privacy(self):
        QMessageBox.information(self, self.t("privacy"), self.t("privacy_note"))

    def toggle_private(self):
        if self.worker:
            return
        if not self.store.memory:
            QMessageBox.information(self, self.t("private_session"), self.t("private_note"))
            self.backend.stop()
            self.store = ChatStore(self._saved_store.root, memory=True)
            self.store.set_setting("language", self.language)
        else:
            self.backend.stop()
            self.store.close()
            self.store = self._saved_store
        self.active_images.clear()
        self.pending_photo = None
        self.selected_image = None
        self.chat_id = None
        self.chat_photo.clear()
        self.photo_preview.clear()
        self.chat_heading.clear()
        self.reply_text = ""
        self.reply_label = None
        clear_layout(self.transcript_layout)
        self.begin_new_chat()
        self.retranslate()

    def erase_analysis(self):
        if self.chat_id and not self.worker:
            self.backend.stop()
            self.store.delete_analysis(self.chat_id)
            self.refresh_conversation()

    def erase_all_chats(self):
        if self.worker:
            return
        result = QMessageBox.question(
            self,
            self.t("privacy"),
            self.t("erase_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.backend.stop()
            self.store.delete_all_chats()
            self.active_images.clear()
            self.pending_photo = None
            self.selected_image = None
            self.chat_id = None
            self.chat_photo.clear()
            self.photo_preview.clear()
            clear_layout(self.transcript_layout)
            self.retranslate()
            self.show_screen("home")

    def _scroll_bottom(self):
        QTimer.singleShot(
            0,
            lambda: self.transcript_scroll.verticalScrollBar().setValue(
                self.transcript_scroll.verticalScrollBar().maximum()
            ),
        )

    def send_message(self):
        if not self.chat_id or (self.worker and self.worker.isRunning()):
            return
        text = self.question.toPlainText().strip()
        if not text:
            return
        if len(text) > 3000:
            self.request_status.setText(self.t("message_too_long"))
            self.request_status.show()
            return
        self.store.add_message(self.chat_id, "user", text)
        self.refresh_conversation()
        self.reply_label = self.append_bubble("assistant", "")
        self.reply_text = ""
        self._reply_chat_id = self.chat_id
        self._reply_language = self.language
        image = self.active_images.get(self.chat_id)
        messages = self.store.messages(self.chat_id)
        messages[-1]["metadata"]["_answer_style"] = self.style_picker.currentData()
        messages[-1]["metadata"]["_translate_persian_input"] = self.auto_translate.isChecked()
        messages[-1]["metadata"]["_active_comparison"] = next(
            (
                m.get("metadata", {}).get("comparison")
                for m in reversed(messages)
                if m.get("metadata", {}).get("comparison")
            ),
            None,
        )
        if image is not None:
            from qma_face.services.analysis import active_analysis
            from qma_face.services.photo_quality import photo_digest
            from qma_face.ui.analysis_dialog import pil_image

            digest = photo_digest(pil_image(image))
            messages[-1]["metadata"]["_photo_sha256"] = digest
            messages[-1]["metadata"]["_active_analysis"] = active_analysis(messages, digest)
        self.worker = ReplyWorker(
            self.backend,
            messages,
            self.language,
            image_bytes(image) if image is not None else None,
            self,
        )
        self.worker.piece.connect(self._piece)
        self.worker.state.connect(self._state)
        self.worker.complete.connect(self._complete)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.send.hide()
        self.stop_reply.show()
        self.question.setEnabled(False)
        self.language_picker.setEnabled(False)
        self.back.setEnabled(False)
        self.add_photo.setEnabled(False)
        self.remove_photo.setEnabled(False)
        self.analyse_photo.setEnabled(False)
        self.more.setEnabled(False)
        self.style_picker.setEnabled(False)
        self.request_status.setText(self.t("loading"))
        self.request_status.show()
        self.worker.start()
        self.chat_cloud.set_motion_enabled(True)
        self._scroll_bottom()

    def _piece(self, piece):
        if self._worker_closing:
            return
        self.reply_text += piece
        if self.reply_label:
            self.reply_label.setText(self.reply_text)
        self._scroll_bottom()

    def _state(self, state):
        if state == "translating_input":
            self.request_status.setText(
                "Traduction du message persan en anglais…"
                if self.language == "fr"
                else "Translating your Persian message into English…"
            )
        else:
            self.request_status.setText(self.t(state))
        self.request_status.show()

    def _complete(self, result):
        if self.store.get_chat(self._reply_chat_id):
            metadata = {key: value for key, value in result.items() if key != "text"}
            metadata["status"] = "completed"
            self.store.add_message(self._reply_chat_id, "assistant", result["text"], metadata)
        self.reply_text = result["text"]
        if self.reply_label:
            self.reply_label.setText(self.reply_text)
            self._add_source_button(
                self.reply_label.parentWidget().layout(), result.get("sources", [])
            )
            self._add_input_translation(self.reply_label.parentWidget().layout(), result)

    def _failed(self, key):
        text = (
            self.reply_text
            if key == "cancelled" and self.reply_text
            else tr(key, self._reply_language)
        )
        if self.store.get_chat(self._reply_chat_id):
            self.store.add_message(
                self._reply_chat_id,
                "assistant",
                text,
                {"status": "cancelled" if key == "cancelled" else "error"},
            )
        if self.reply_label:
            self.reply_label.setText(text)

    def _finished(self):
        self.chat_cloud.set_motion_enabled(False)
        self.request_status.hide()
        self.send.show()
        self.stop_reply.hide()
        self.stop_reply.setEnabled(True)
        for widget in (
            self.question,
            self.language_picker,
            self.back,
            self.add_photo,
            self.remove_photo,
            self.analyse_photo,
            self.more,
            self.style_picker,
        ):
            widget.setEnabled(True)
        if self.worker:
            self.worker.deleteLater()
        self.worker = None
        self._reply_chat_id = None
        if not self._worker_closing and self.chat_id:
            self.refresh_conversation()
        self.question.setFocus()

    def cancel_reply(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel_event.set()
            self.stop_reply.setEnabled(False)
            threading.Thread(target=self.backend.cancel_generation, daemon=True).start()

    def closeEvent(self, event):
        self._worker_closing = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel_event.set()
            self.backend.cancel_generation()
            self.worker.wait(10000)
            if self.worker.isRunning():
                event.ignore()
                self._worker_closing = False
                return
        self.backend.stop()
        if self.store.memory:
            self.store.close()
            self.chat_photo.clear()
            self.photo_preview.clear()
            self.chat_heading.clear()
            self.reply_text = ""
            self.reply_label = None
            clear_layout(self.transcript_layout)
        self.active_images.clear()
        self.pending_photo = None
        self.selected_image = None
        event.accept()
