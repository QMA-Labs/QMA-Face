TRANSLATIONS = {
    "en": {
        "space": "Your space",
        "back": "Back",
        "companion": "Here, one step at a time",
        "home_title": "A fresh perspective.",
        "home_caption": "Start with a conversation.",
        "new_chat": "New chat",
        "new_subtitle": "A fresh start",
        "my_chats": "My chats",
        "chats_subtitle": "Pick up where you left off",
        "upload_title": "Add your photo.",
        "upload_caption": "A clear, front-facing photo works best.",
        "choose_photo": "Choose a photo",
        "drop_photo": "or drop it here",
        "photo_selected": "Photo added.",
        "photo_caption": "Ready when you are.",
        "change_photo": "Choose another photo",
        "start_chat": "Start conversation",
        "without_photo": "Continue without a photo",
        "save_photo": "Keep this photo in the chat",
        "photo_privacy": "Off by default. Otherwise, the photo stays in memory only.",
        "empty_title": "Your first conversation awaits.",
        "empty_caption": "Start with a photo, or just ask a question.",
        "history_title": "Your conversations.",
        "history_caption": "Everything stays on this device.",
        "delete": "Delete",
        "deleted": "Conversation deleted.",
        "you": "You",
        "assistant": "Cloud",
        "question": "Ask about your photo…",
        "send": "Send",
        "stop": "Stop",
        "thinking": "Thinking…",
        "loading": "Preparing your local assistant…",
        "retrieving": "Finding relevant passages…",
        "sources": "Sources",
        "source_detail": "Retrieved evidence",
        "close": "Close",
        "source_notice": (
            "Retrieved passages may not support every generated claim. "
            "Check the text and source type."
        ),
        "chat_ready": "Let's take a closer look.",
        "chat_ready_photo": "Your photo is ready. What would you like to explore?",
        "chat_ready_text": "What would you like to explore? You can add a photo anytime.",
        "add_photo": "Add a photo",
        "photo_missing": "This photo wasn't saved. Add it again to discuss it.",
        "local": "On-device",
        "footer": "On-device · English & French",
        "unavailable": (
            "The local assistant isn't ready yet. Your message is saved; "
            "try again when the model is available."
        ),
        "request_failed": (
            "The assistant couldn't finish this reply. Your chat is saved. Please try again."
        ),
        "cancelled": "Reply stopped.",
        "image_type": "Choose a readable image file.",
        "image_size": "Choose an image smaller than 30 MB and 40 megapixels.",
        "image_decode": "This photo couldn't be opened. Try another image.",
        "photo_dialog": "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)",
        "photo_saved": "Photo kept in this chat",
        "photo_memory": "Photo kept in memory only",
        "language": "Language",
        "clear_photo": "Remove photo",
        "retry": "Try again",
        "message_too_long": "Please keep your message under 3,000 characters.",
        "cloud_name": "Cloud companion",
    },
    "fr": {
        "retrieving": "Recherche de passages pertinents…",
        "sources": "Sources",
        "source_detail": "Éléments retrouvés",
        "close": "Fermer",
        "source_notice": (
            "Les passages retrouvés ne confirment pas forcément chaque affirmation. "
            "Vérifiez le texte et le type de source."
        ),
        "space": "Votre espace",
        "back": "Retour",
        "companion": "À vos côtés, étape par étape",
        "home_title": "Un regard nouveau.",
        "home_caption": "Tout commence par une conversation.",
        "new_chat": "Nouvelle discussion",
        "new_subtitle": "Un nouveau départ",
        "my_chats": "Mes discussions",
        "chats_subtitle": "Reprendre le fil",
        "upload_title": "Ajoutez votre photo.",
        "upload_caption": "Une photo nette, prise de face, est idéale.",
        "choose_photo": "Choisir une photo",
        "drop_photo": "ou déposez-la ici",
        "photo_selected": "Photo ajoutée.",
        "photo_caption": "Nous pouvons commencer.",
        "change_photo": "Choisir une autre photo",
        "start_chat": "Commencer",
        "without_photo": "Continuer sans photo",
        "save_photo": "Conserver cette photo dans la discussion",
        "photo_privacy": "Désactivé par défaut. Sinon, la photo reste uniquement en mémoire.",
        "empty_title": "Votre première discussion vous attend.",
        "empty_caption": "Ajoutez une photo ou posez simplement une question.",
        "history_title": "Vos discussions.",
        "history_caption": "Tout reste sur cet appareil.",
        "delete": "Supprimer",
        "deleted": "Discussion supprimée.",
        "you": "Vous",
        "assistant": "Cloud",
        "question": "Une question sur votre photo…",
        "send": "Envoyer",
        "stop": "Arrêter",
        "thinking": "Réflexion en cours…",
        "loading": "Préparation de votre assistant local…",
        "chat_ready": "Regardons de plus près.",
        "chat_ready_photo": "Votre photo est prête. Que souhaitez-vous explorer ?",
        "chat_ready_text": (
            "Que souhaitez-vous explorer ? Vous pouvez ajouter une photo à tout moment."
        ),
        "add_photo": "Ajouter une photo",
        "photo_missing": (
            "Cette photo n'a pas été conservée. Ajoutez-la à nouveau pour en discuter."
        ),
        "local": "Sur cet appareil",
        "footer": "Sur cet appareil · Anglais et français",
        "unavailable": (
            "L'assistant local n'est pas encore prêt. Votre message est enregistré ; "
            "réessayez lorsque le modèle sera disponible."
        ),
        "request_failed": (
            "L'assistant n'a pas pu terminer sa réponse. "
            "Votre discussion est enregistrée. Réessayez."
        ),
        "cancelled": "Réponse arrêtée.",
        "image_type": "Choisissez un fichier image lisible.",
        "image_size": "Choisissez une image de moins de 30 Mo et 40 mégapixels.",
        "image_decode": "Cette photo ne peut pas être ouverte. Essayez une autre image.",
        "photo_dialog": "Images (*.png *.jpg *.jpeg *.webp *.bmp);;Tous les fichiers (*)",
        "photo_saved": "Photo conservée dans cette discussion",
        "photo_memory": "Photo conservée uniquement en mémoire",
        "language": "Langue",
        "clear_photo": "Retirer la photo",
        "retry": "Réessayer",
        "message_too_long": "Veuillez limiter votre message à 3 000 caractères.",
        "cloud_name": "Compagnon Cloud",
    },
}


from qma_face.ui.analysis_text import STRINGS  # noqa: E402
from qma_face.ui.experience_text import STRINGS as EXPERIENCE_STRINGS  # noqa: E402

for _language, _strings in STRINGS.items():
    TRANSLATIONS[_language].update(_strings)
    TRANSLATIONS[_language].update(EXPERIENCE_STRINGS[_language])


def tr(key: str, language: str = "en") -> str:
    if language not in TRANSLATIONS:
        raise ValueError("Only English and French are supported.")
    return TRANSLATIONS[language][key]
