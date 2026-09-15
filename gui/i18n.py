"""Live-switchable ES/EN translations for the GUI.

Every user-facing string in gui/main_window.py goes through `t(key, lang,
**kwargs)`. Switching language re-applies these to every already-built
widget in place — no restart needed (see MainWindow._apply_language()).
"""
from __future__ import annotations

LANGUAGES = ("es", "en")
LANGUAGE_NAMES = {"es": "Español", "en": "English"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "tagline": {
        "es": "🤘 Tus recuerdos. Tu USB. Cero dependencia de la nube.",
        "en": "🤘 Your memories. Your USB. Zero cloud dependency.",
    },
    "nav_main": {"es": "Principal", "en": "Main"},
    "nav_settings": {"es": "⚙ Configuración", "en": "⚙ Settings"},

    "btn_start": {"es": "🤘 Iniciar backup", "en": "🤘 Start backup"},
    "btn_stop": {"es": "Detener backup", "en": "Stop backup"},
    "status_stopped": {"es": "Estado: Detenido", "en": "Status: Stopped"},
    "status_listening": {
        "es": "Estado: Escuchando en el puerto {port} 🤘",
        "en": "Status: Listening on port {port} 🤘",
    },

    "server_address_title": {
        "es": "Dirección del servidor (igual para todos los perfiles):",
        "en": "Server address (same for every profile):",
    },
    "address_placeholder": {"es": "Dirección: -", "en": "Address: -"},
    "address_value": {"es": "Dirección: {url}", "en": "Address: {url}"},
    "ip_placeholder": {"es": "IP alternativa: -", "en": "Fallback IP: -"},
    "ip_value": {"es": "IP alternativa: {url}", "en": "Fallback IP: {url}"},

    "profiles_connected_title": {
        "es": "Perfiles conectados a este backup:",
        "en": "Profiles connected to this backup:",
    },
    "aggregate_stats": {
        "es": "Última copia (todos los perfiles): {last}   |   Total archivos: {total}",
        "en": "Last backup (all profiles): {last}   |   Total files: {total}",
    },
    "never": {"es": "nunca", "en": "never"},

    "show_activity": {"es": "▼  Mostrar actividad", "en": "▼  Show activity"},
    "hide_activity": {"es": "▲  Ocultar actividad", "en": "▲  Hide activity"},
    "expand_activity": {"es": "⤢ Expandir", "en": "⤢ Expand"},

    "profile_active": {"es": "Activo", "en": "Active"},
    "profile_paused": {"es": "Pausado", "en": "Paused"},

    "stats_no_dest": {
        "es": "Sin carpeta destino configurada",
        "en": "No destination folder configured",
    },
    "stats_folder": {"es": "Carpeta: {path}", "en": "Folder: {path}"},
    "stats_usb": {"es": "USB: {info}", "en": "USB: {info}"},
    "stats_line": {
        "es": "Total en destino: {count} archivos   |   Última copia: {last}",
        "en": "Total in destination: {count} files   |   Last backup: {last}",
    },
    "stats_last_run": {
        "es": "Última corrida: {new} guardados, {skipped} ya existían{running}",
        "en": "Last run: {new} saved, {skipped} already had{running}",
    },
    "stats_last_run_in_progress": {
        "es": " (en curso...)",
        "en": " (in progress...)",
    },
    "no_label": {"es": "Sin etiqueta", "en": "Unlabeled"},
    "free_of_total": {
        "es": '"{label}"  ({free} libres de {total})',
        "en": '"{label}"  ({free} free of {total})',
    },

    "settings_title": {"es": "Configuración", "en": "Settings"},
    "language_title": {"es": "Idioma", "en": "Language"},

    "profiles_title": {
        "es": "Perfiles (personas o dispositivos)",
        "en": "Profiles (people or devices)",
    },
    "add_profile": {"es": "+ Agregar perfil", "en": "+ Add profile"},
    "profiles_hint": {
        "es": "Crea un perfil por cada iPhone/iPad. Cada uno tiene su propio token y su"
        " propia carpeta — nunca se mezclan.",
        "en": "Create one profile per iPhone/iPad. Each one has its own token and its"
        " own folder — they never mix.",
    },

    "btn_choose_folder": {"es": "Elegir carpeta...", "en": "Choose folder..."},
    "btn_usb_history": {"es": "Historial USB", "en": "USB history"},
    "btn_copy_token": {"es": "Copiar token", "en": "Copy token"},
    "btn_rename": {"es": "Renombrar", "en": "Rename"},
    "btn_regenerate_token": {"es": "Renovar token", "en": "Regenerate token"},
    "btn_delete": {"es": "Eliminar", "en": "Delete"},

    "empty_profiles_main": {
        "es": 'Aún no hay perfiles. Ve a "⚙ Configuración" y arranca la banda.',
        "en": 'No profiles yet. Go to "⚙ Settings" and start the band.',
    },
    "empty_profiles_settings": {
        "es": 'Aún no hay perfiles. Usa "+ Agregar perfil" para registrar un iPhone o iPad.',
        "en": 'No profiles yet. Use "+ Add profile" to register an iPhone or iPad.',
    },

    "dlg_add_profile_title": {"es": "Agregar perfil", "en": "Add profile"},
    "dlg_add_profile_text": {
        "es": 'Nombre del perfil (ej. "iPhone de Laura"):',
        "en": 'Profile name (e.g. "iPhone de Laura"):',
    },
    "msg_profile_created": {
        "es": 'Perfil "{name}" creado.\n\nToken (ya copiado al portapapeles):\n{token}\n\n'
        "Pégalo en el Atajo de ese dispositivo siguiendo el manual de configuración del"
        " iPhone.\n\nAhora elige la carpeta destino de este perfil.",
        "en": 'Profile "{name}" created.\n\nToken (already copied to clipboard):\n{token}\n\n'
        "Paste it into that device's Shortcut following the iPhone Setup Manual.\n\n"
        "Now choose this profile's destination folder.",
    },
    "dlg_choose_dest_title": {
        "es": 'Carpeta destino para "{name}"',
        "en": 'Destination folder for "{name}"',
    },

    "msg_no_history": {
        "es": '"{name}" todavía no tiene historial de carpetas/USB.',
        "en": '"{name}" has no folder/USB history yet.',
    },
    "history_title": {
        "es": 'Historial de carpetas/USB para "{name}":\n\n{lines}',
        "en": 'Folder/USB history for "{name}":\n\n{lines}',
    },
    "history_current": {"es": " (actual)", "en": " (current)"},
    "history_serial": {"es": "serie {serial}", "en": "serial {serial}"},

    "msg_token_copied": {
        "es": 'Token de "{name}" copiado al portapapeles.',
        "en": "{name}'s token copied to clipboard.",
    },

    "dlg_rename_title": {"es": "Renombrar perfil", "en": "Rename profile"},
    "dlg_rename_text": {
        "es": 'Nuevo nombre para "{name}":',
        "en": 'New name for "{name}":',
    },

    "confirm_regenerate": {
        "es": '¿Renovar el token de "{name}"?\n\nEl Atajo de ese dispositivo dejará de'
        " funcionar hasta que pegues el nuevo token ahí.",
        "en": "Regenerate \"{name}\"'s token?\n\nThat device's Shortcut will stop working"
        " until you paste the new token in there.",
    },
    "msg_new_token": {
        "es": "Nuevo token (copiado al portapapeles):\n{token}",
        "en": "New token (copied to clipboard):\n{token}",
    },

    "confirm_delete": {
        "es": '¿Eliminar el perfil "{name}"?\n\nSus archivos YA respaldados no se borran'
        " — solo se revoca su acceso (su token dejará de funcionar).",
        "en": 'Delete profile "{name}"?\n\nFiles it has ALREADY backed up are not'
        " deleted — this only revokes its access (its token stops working).",
    },

    "warn_no_profiles": {
        "es": 'Agrega al menos un perfil (pestaña "⚙ Configuración") antes de iniciar.',
        "en": 'Add at least one profile (the "⚙ Settings" tab) before starting.',
    },
    "warn_no_destination": {
        "es": 'Ningún perfil tiene carpeta destino configurada. Ve a "⚙ Configuración" y'
        ' usa "Elegir carpeta..." en al menos uno.',
        "en": 'No profile has a destination folder set. Go to "⚙ Settings" and use'
        ' "Choose folder..." on at least one.',
    },

    "log_server_started": {"es": "Servidor iniciado. A darle.", "en": "Server started. Let's go."},
    "log_server_stopped": {"es": "Servidor detenido.", "en": "Server stopped."},
    "log_profile_activated": {"es": 'Perfil "{name}" activado.', "en": 'Profile "{name}" activated.'},
    "log_profile_paused": {"es": 'Perfil "{name}" pausado.', "en": 'Profile "{name}" paused.'},

    "err_toggle_server": {
        "es": "Ocurrió un error al iniciar/detener el servidor:\n\n{details}",
        "en": "An error occurred starting/stopping the server:\n\n{details}",
    },
    "err_unexpected": {
        "es": "Ocurrió un error inesperado:\n\n{val}",
        "en": "An unexpected error occurred:\n\n{val}",
    },

    # Titles for the custom dark dialogs in gui/dialogs.py (bodies reuse the
    # message keys above — these are just the short header line).
    "dlg_title_error": {"es": "Error", "en": "Error"},
    "dlg_title_warning": {"es": "Atención", "en": "Heads up"},
    "dlg_title_profile_created": {"es": "Perfil creado", "en": "Profile created"},
    "dlg_title_history": {"es": "Historial de carpetas/USB", "en": "Folder/USB history"},
    "dlg_title_token_copied": {"es": "Token copiado", "en": "Token copied"},
    "dlg_title_new_token": {"es": "Nuevo token", "en": "New token"},
    "dlg_title_confirm": {"es": "Confirmar", "en": "Confirm"},
}


def t(key: str, lang: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    template = entry.get(lang, entry.get("es", key))
    return template.format(**kwargs) if kwargs else template
