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
    "status_starting": {"es": "Estado: Iniciando backup...", "en": "Status: Starting backup..."},
    "status_listening": {
        "es": "Estado: Escuchando en el puerto {port} 🤘",
        "en": "Status: Listening on port {port} 🤘",
    },

    "cable_mode_chip": {"es": "MODO CABLE", "en": "CABLE MODE"},
    "status_cable": {
        "es": "WiFi apagado. El Atajo no puede subir fotos ahora.",
        "en": "WiFi off. The Shortcut can't upload photos right now.",
    },
    "btn_mode_to_cable": {"es": "Backup por cable", "en": "Backup by cable"},
    "btn_mode_to_wifi": {"es": "Backup por WiFi", "en": "Backup by WiFi"},
    "btn_mode_switching": {"es": "Cambiando…", "en": "Switching…"},
    "confirm_switch_from_wifi": {
        "es": "Hay un backup por WiFi en curso y cambiar de modo lo detiene.\n\nLo ya copiado queda guardado y el Atajo retomará lo demás la próxima vez. ¿Cambiar a backup por cable?",
        "en": "A WiFi backup is in progress and switching stops it.\n\nWhat was copied stays saved and the Shortcut picks up the rest next time. Switch to backup by cable?",
    },
    "confirm_switch_from_cable": {
        "es": "Hay un backup por cable en curso y cambiar de modo lo detiene.\n\nLo ya copiado queda guardado y puedes retomarlo después. ¿Cambiar a backup por WiFi?",
        "en": "A cable backup is in progress and switching stops it.\n\nWhat was copied stays saved and you can resume later. Switch to backup by WiFi?",
    },
    "confirm_close_during_cable": {
        "es": "Hay un backup por cable en curso. Si cierras, se detiene; lo ya copiado queda guardado. ¿Cerrar?",
        "en": "A cable backup is in progress. Closing stops it; what was copied stays saved. Close?",
    },
    "err_server_did_not_stop": {
        "es": "El servidor no se detuvo a tiempo, así que sigo en modo WiFi. Intenta de nuevo.",
        "en": "The server didn't stop in time, so the app stays in WiFi mode. Try again.",
    },
    "log_mode_cable": {"es": "Modo cable activo. El servidor WiFi está apagado.", "en": "Cable mode on. The WiFi server is off."},
    "log_mode_wifi": {"es": "Modo WiFi activo.", "en": "WiFi mode on."},
    "cable_connection_title": {"es": "Conexión por cable:", "en": "Cable connection:"},
    "cable_looking": {"es": "Buscando el iPhone…", "en": "Looking for the iPhone…"},
    "cable_no_device": {
        "es": "No veo ningún iPhone. Conéctalo con el cable y desbloquéalo.",
        "en": "No iPhone found. Connect it with the cable and unlock it.",
    },
    "cable_no_device_hint": {
        "es": "Solo se lee del teléfono: nada se borra ni se modifica.",
        "en": "The phone is only read: nothing is deleted or changed.",
    },
    "cable_device_connected": {"es": "✓ {name} conectado", "en": "✓ {name} connected"},
    "cable_device_not_ready": {
        "es": "! Desbloquea el iPhone y, si te lo pregunta, toca «Confiar».",
        "en": "! Unlock the iPhone and, if it asks, tap \"Trust\".",
    },
    "cable_device_ready": {
        "es": "✓ Listo. Solo se lee del teléfono: nada se borra ni se modifica.",
        "en": "✓ Ready. The phone is only read: nothing is deleted or changed.",
    },
    "cable_many_devices": {
        "es": "! Hay más de un iPhone conectado. Deja solo el de este backup.",
        "en": "! More than one iPhone is connected. Leave only the one for this backup.",
    },
    "btn_start_cable": {"es": "Iniciar backup por cable", "en": "Start backup by cable"},
    "btn_copy_cable": {"es": "Revisar y copiar {pending} archivos", "en": "Review and copy {pending} files"},
    "btn_cancel_cable": {"es": "Cancelar", "en": "Cancel"},
    "btn_stop_cable": {"es": "Detener copia", "en": "Stop copy"},
    "btn_resume_cable": {"es": "Continuar", "en": "Resume"},
    "btn_close_cable": {"es": "Cerrar", "en": "Close"},
    "cable_other_profile_busy": {
        "es": "Disponible cuando termine la copia del otro perfil.",
        "en": "Available when the other profile's copy finishes.",
    },
    "cable_no_destination": {
        "es": "Elige una carpeta destino en ⚙ Configuración para usar el cable.",
        "en": "Choose a destination folder in ⚙ Settings to use the cable.",
    },
    "cable_analyzing": {
        "es": "Analizando el iPhone… {count} archivos vistos. Todavía no se copia nada.",
        "en": "Analyzing the iPhone… {count} files seen. Nothing is being copied yet.",
    },
    "cable_nothing_to_copy": {
        "es": "Los {total} archivos que el iPhone muestra por USB ya están en este destino. Corre el Atajo por WiFi para cubrir el resto de tu Fototeca.",
        "en": "The {total} files the iPhone shows over USB are already at this destination. Run the Shortcut over WiFi to cover the rest of your library.",
    },
    "cable_summary": {
        "es": "En el iPhone: {total}  |  Ya respaldados: {already}  |  Por revisar: {pending} ({size}, ~{time})\nSolo se guarda lo que de verdad falte; algunos pueden estar ya respaldados con otro nombre.",
        "en": "On the iPhone: {total}  |  Already backed up: {already}  |  To review: {pending} ({size}, ~{time})\nOnly what's really missing gets saved; some may already be backed up under another name.",
    },
    "cable_low_space": {
        "es": "! Solo hay {free} libres. Si no alcanza, la copia se detiene sin perder lo copiado.",
        "en": "! Only {free} free. If it isn't enough, the copy stops without losing what was copied.",
    },
    "cable_copying": {
        "es": "{done} de {total} confirmados  |  {failed} fallidos",
        "en": "{done} of {total} confirmed  |  {failed} failed",
    },
    "cable_speed": {"es": "  |  {speed}/s  |  quedan ~{time}", "en": "  |  {speed}/s  |  ~{time} left"},
    "cable_keep_connected": {
        "es": "Mantén el iPhone conectado y desbloqueado.",
        "en": "Keep the iPhone connected and unlocked.",
    },
    "cable_done": {
        "es": "Listo: {copied} nuevos, {already} ya estaban, {conflicts} con mismo nombre y contenido distinto (se conservan ambos), {failed} fallidos.\nEsto cubre lo que el iPhone muestra por USB; con iCloud pueden faltar originales. Corre el Atajo por WiFi para completar.",
        "en": "Done: {copied} new, {already} already there, {conflicts} with the same name and different content (both kept), {failed} failed.\nThis covers what the iPhone shows over USB; with iCloud, originals may be missing. Run the Shortcut over WiFi to complete it.",
    },
    "cable_analyze_failed": {
        "es": "No pude leer el iPhone. Revisa que siga conectado y desbloqueado, e intenta de nuevo.",
        "en": "Couldn't read the iPhone. Check it's still connected and unlocked, and try again.",
    },
    "cable_stopped_device": {
        "es": "El iPhone dejó de responder ({copied} nuevos guardados). Conéctalo, desbloquéalo y continúa.",
        "en": "The iPhone stopped responding ({copied} new saved). Connect it, unlock it and resume.",
    },
    "cable_stopped_destination": {
        "es": "No pude escribir en el destino ({copied} nuevos guardados). ¿Se llenó o se desconectó? Detalle: {error}",
        "en": "Couldn't write to the destination ({copied} new saved). Is it full or disconnected? Details: {error}",
    },
    "cable_stopped_verification": {
        "es": "El disco destino sigue fallando al verificar lo copiado ({copied} nuevos guardados). Revisa el disco antes de continuar.",
        "en": "The destination drive keeps failing to verify what's copied ({copied} new saved). Check the drive before resuming.",
    },
    "err_profile_name_empty": {
        "es": "El nombre del perfil no puede estar vacío.",
        "en": "The profile name can't be empty.",
    },
    "cable_stopped_user": {
        "es": "Copia detenida ({copied} nuevos guardados). Lo copiado queda a salvo.",
        "en": "Copy stopped ({copied} new saved). What was copied is safe.",
    },
    "cable_unreadable": {
        "es": "! El iPhone no dejó leer {count} elementos, así que este análisis está incompleto. Desbloquéalo y analiza de nuevo antes de darlo por respaldado.",
        "en": "! The iPhone wouldn't let {count} items be read, so this analysis is incomplete. Unlock it and analyze again before treating it as backed up.",
    },
    "cable_minutes": {"es": "{minutes} min", "en": "{minutes} min"},
    "cable_hours": {"es": "{hours} h", "en": "{hours} h"},
    "log_cable_analyzed": {
        "es": "iPhone analizado: {total} archivos, {already} ya respaldados, {pending} por revisar.",
        "en": "iPhone analyzed: {total} files, {already} already backed up, {pending} to review.",
    },
    "log_cable_result": {
        "es": "Backup por cable: {copied} nuevos, {already} ya estaban, {conflicts} conflictos, {failed} fallidos.",
        "en": "Cable backup: {copied} new, {already} already there, {conflicts} conflicts, {failed} failed.",
    },
    "confirm_cable_first_time": {
        "es": "¿Este {device} es de «{name}»?\n\nSus fotos se guardarán en la carpeta de ese perfil, y la app recordará el teléfono para avisarte si luego conectas otro.",
        "en": "Is this {device} \"{name}\"'s?\n\nIts photos go to that profile's folder, and the app remembers the phone to warn you if you connect a different one.",
    },
    "confirm_cable_different_device": {
        "es": "Este no es el iPhone que «{name}» usó antes. Si es de otra persona, sus fotos se mezclarían en esta carpeta. ¿Continuar de todos modos?",
        "en": "This isn't the iPhone \"{name}\" used before. If it's someone else's, their photos would mix into this folder. Continue anyway?",
    },
    "confirm_cable_other_owner": {
        "es": "Este iPhone pertenece a «{owner}». Si continúas, sus fotos se guardarán en la carpeta de «{name}». ¿Continuar?",
        "en": "This iPhone belongs to \"{owner}\". If you continue, its photos go to \"{name}\"'s folder. Continue?",
    },
    "warn_cable_busy_profile": {
        "es": "Este perfil tiene un backup por cable abierto. Ciérralo antes de cambiar su carpeta o eliminarlo.",
        "en": "This profile has a cable backup open. Close it before changing its folder or deleting it.",
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
    "stats_dest_not_connected": {
        "es": "⚠ USB no conectada: {path}",
        "en": "⚠ USB not connected: {path}",
    },
    "stats_usb": {"es": "USB: {info}", "en": "USB: {info}"},
    "stats_line": {
        "es": "Total en destino: {count} archivos, {size}   |   Última copia: {last}",
        "en": "Total in destination: {count} files, {size}   |   Last backup: {last}",
    },
    "stats_last_run": {
        "es": "Última corrida: {new} guardados, {skipped} ya existían{running}",
        "en": "Last run: {new} saved, {skipped} already had{running}",
    },
    "stats_last_run_in_progress": {
        "es": " (en curso: {checked} revisados)",
        "en": " (in progress: {checked} checked)",
    },
    "no_label": {"es": "Sin etiqueta", "en": "Unlabeled"},
    "free_of_total": {
        "es": '"{label}"  ({free} libres de {total})',
        "en": '"{label}"  ({free} free of {total})',
    },

    "settings_title": {"es": "Configuración", "en": "Settings"},
    "language_title": {"es": "Idioma", "en": "Language"},

    "settings_preferences_title": {"es": "Preferencias", "en": "Preferences"},
    "setting_start_with_windows": {
        "es": "Iniciar PunkBackup con Windows",
        "en": "Start PunkBackup with Windows",
    },
    "setting_auto_start_backup": {
        "es": "Iniciar backup al abrir el programa",
        "en": "Start backup when opening the app",
    },
    "setting_idle_timeout": {
        "es": "Minutos sin actividad para avisar que el backup se detuvo",
        "en": "Minutes of inactivity before flagging the backup as stopped",
    },
    "minutes_suffix": {"es": "min", "en": "min"},
    "toggle_on": {"es": "Activado", "en": "On"},
    "toggle_off": {"es": "Desactivado", "en": "Off"},
    "btn_save": {"es": "Guardar", "en": "Save"},
    "btn_saved": {"es": "✓ Guardado", "en": "✓ Saved"},

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

    # Mirror / second-copy feature (PLAN.md section 13)
    "btn_configure_mirror": {"es": "+ Configurar segunda copia (opcional)", "en": "+ Configure second copy (optional)"},
    "btn_choose_mirror": {"es": "Elegir carpeta...", "en": "Choose folder..."},
    "btn_sync_mirror": {"es": "🔄 Sincronizar ahora", "en": "🔄 Sync now"},
    "btn_stop_mirror_sync": {"es": "⏹ Detener", "en": "⏹ Stop"},
    "btn_remove_mirror": {"es": "Quitar", "en": "Remove"},
    "dlg_choose_mirror_title": {
        "es": 'Carpeta de segunda copia para "{name}"',
        "en": 'Second-copy folder for "{name}"',
    },
    "dlg_remove_mirror_title": {"es": "Quitar segunda copia", "en": "Remove second copy"},
    "dlg_remove_mirror_text": {
        "es": 'Esto deja de sincronizar "{name}" hacia esa carpeta. Los archivos que ya se '
        "copiaron ahí NO se borran. ¿Continuar?",
        "en": 'This stops syncing "{name}" to that folder. Files already copied there are NOT '
        "deleted. Continue?",
    },
    "dlg_mirror_same_folder_title": {"es": "No se puede usar esa carpeta", "en": "Can't use that folder"},
    "dlg_mirror_same_folder_text": {
        "es": "La segunda copia no puede ser la misma carpeta que el destino principal.",
        "en": "The second copy can't be the same folder as the primary destination.",
    },
    "mirror_status": {
        "es": "🔄 Segunda copia: {path}\n{total} archivos copiados  ·  {free} libres de {total_space}",
        "en": "🔄 Second copy: {path}\n{total} files copied  ·  {free} free of {total_space}",
    },
    "mirror_status_no_space_info": {
        "es": "🔄 Segunda copia: {path}\n{total} archivos copiados",
        "en": "🔄 Second copy: {path}\n{total} files copied",
    },
    "mirror_not_connected": {
        "es": "🔄 Segunda copia: {path}\n(no conectada)",
        "en": "🔄 Second copy: {path}\n(not connected)",
    },
    "mirror_syncing_progress": {
        "es": "🔄 Sincronizando... {done} / {total} archivos  ·  {free} libres de {total_space}",
        "en": "🔄 Syncing... {done} / {total} files  ·  {free} free of {total_space}",
    },
    "mirror_syncing_progress_no_space": {
        "es": "🔄 Sincronizando... {done} / {total} archivos",
        "en": "🔄 Syncing... {done} / {total} files",
    },
    # Shown instead of the two keys above when at least one file has
    # failed verification during this sync -- makes "it's actually
    # failing a lot, not just slow" visible without having to dig through
    # the database (see PLAN.md, the 2026-09-23 write-up on the old
    # attempts-not-successes counter).
    "mirror_syncing_progress_failed": {
        "es": "🔄 Sincronizando... {done} / {total} archivos  ·  ⚠ {failed} fallidos  ·  {free} libres de {total_space}",
        "en": "🔄 Syncing... {done} / {total} files  ·  ⚠ {failed} failed  ·  {free} free of {total_space}",
    },
    "mirror_syncing_progress_failed_no_space": {
        "es": "🔄 Sincronizando... {done} / {total} archivos  ·  ⚠ {failed} fallidos",
        "en": "🔄 Syncing... {done} / {total} files  ·  ⚠ {failed} failed",
    },
    "log_mirror_sync_started": {
        "es": "🔄 Sincronizando segunda copia de \"{name}\"...",
        "en": "🔄 Syncing second copy for \"{name}\"...",
    },
    "log_mirror_sync_done": {
        "es": "🔄 Segunda copia de \"{name}\" sincronizada: {copied} nuevos, {verify_failed} fallidos"
        " de verificación.",
        "en": "🔄 Second copy for \"{name}\" synced: {copied} new, {verify_failed} failed"
        " verification.",
    },
    "log_mirror_sync_cancelled": {
        "es": "⏹ Sincronización de segunda copia de \"{name}\" detenida — {copied} copiados. Puedes"
        " continuar más tarde, retoma justo donde quedó.",
        "en": "⏹ Second-copy sync for \"{name}\" stopped — {copied} copied. You can continue later,"
        " it picks up right where it left off.",
    },
    "warn_mirror_low_space": {
        "es": "La segunda copia no tiene espacio suficiente para todo lo pendiente — se copiará"
        " lo que alcance, empezando por lo más reciente.",
        "en": "The second copy doesn't have enough space for everything pending — it will copy"
        " as much as fits, starting with the most recent.",
    },
    "warn_mirror_stopped_with_error": {
        "es": "La sincronización se detuvo antes de terminar ({error}). Puede ser que la unidad se"
        " haya llenado o se haya desconectado — revisa y vuelve a tocar \"Sincronizar ahora\","
        " retoma justo donde quedó.",
        "en": "The sync stopped before finishing ({error}). The drive may have filled up or gotten"
        " disconnected — check it and tap \"Sync now\" again, it picks up right where it left off.",
    },
    "log_mirror_sync_fatal": {
        "es": "la segunda copia de \"{name}\" falló inesperadamente: {error}",
        "en": "second copy for \"{name}\" failed unexpectedly: {error}",
    },
    "err_mirror_sync_fatal": {
        "es": "No se pudo completar la sincronización de la segunda copia: {error}",
        "en": "Couldn't complete the second-copy sync: {error}",
    },

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
        "es": "No hay ningún perfil creado para iniciar backup. Créalo, actívalo y"
        " selecciona una carpeta destino.",
        "en": "No profile has been created to start a backup. Create one, activate it,"
        " and select a destination folder.",
    },
    "warn_no_active_profile": {
        "es": "No hay ningún perfil activado para iniciar backup. Actívalo y asegúrate"
        " de tener una carpeta destino seleccionada.",
        "en": "No profile is activated to start a backup. Activate one and make sure"
        " it has a destination folder selected.",
    },
    "warn_no_destination": {
        "es": 'En los perfiles activos no se encuentra seleccionada una carpeta de'
        ' destino. Ve a "⚙ Configuración" y usa "Elegir carpeta...".',
        "en": 'None of the active profiles has a destination folder selected. Go to'
        ' "⚙ Settings" and use "Choose folder...".',
    },
    "warn_no_valid_destination": {
        "es": "Ninguno de los perfiles activos tiene una carpeta válida para hacer"
        " el backup. Selecciona al menos un destino válido y vuelve a intentar.",
        "en": "None of the active profiles has a valid folder to back up to."
        " Select at least one valid destination and try again.",
    },

    "log_server_starting": {
        "es": "Iniciando backup... (puede reintentar unos segundos si el puerto tarda en liberarse)",
        "en": "Starting backup... (may retry for a few seconds if the port takes a moment to free up)",
    },
    "log_server_started": {"es": "Servidor iniciado. A darle.", "en": "Server started. Let's go."},
    "log_server_stopped": {"es": "Servidor detenido.", "en": "Server stopped."},
    "log_server_not_started": {
        "es": "No se ha iniciado el servidor debido a: {reason}",
        "en": "The server was not started because: {reason}",
    },
    "log_server_waiting_profile": {
        "es": 'Esperando backup para perfil "{name}".',
        "en": 'Waiting for backup from profile "{name}".',
    },
    "log_profile_activated": {"es": 'Perfil "{name}" activado.', "en": 'Profile "{name}" activated.'},
    "log_profile_paused": {"es": 'Perfil "{name}" pausado.', "en": 'Profile "{name}" paused.'},
    "log_backup_idle": {
        "es": '⏸ "{name}": sin actividad hace {minutes}+ minutos — el backup parece haberse detenido (¿se cortó el WiFi o se cerró el Atajo en el teléfono?).',
        "en": '⏸ "{name}": no activity for {minutes}+ minutes — the backup looks like it stopped (WiFi dropped, or the Shortcut closed on the phone?).',
    },

    "err_toggle_server": {
        "es": "Ocurrió un error al iniciar/detener el servidor:\n\n{details}",
        "en": "An error occurred starting/stopping the server:\n\n{details}",
    },
    "err_server_start_unknown": {
        "es": "no se pudo confirmar que el servidor quedó escuchando (razón desconocida)",
        "en": "could not confirm the server started listening (unknown reason)",
    },
    "log_server_start_failed": {
        "es": "El servidor NO quedó escuchando — {details}",
        "en": "The server did NOT start listening — {details}",
    },
    "err_server_start_failed": {
        "es": "No se pudo iniciar el servidor:\n\n{details}\n\nSi el puerto {port} ya está en uso "
        "por otro programa (u otra copia de PunkBackup), ciérralo e inténtalo de nuevo.",
        "en": "Could not start the server:\n\n{details}\n\nIf port {port} is already in use by "
        "another program (or another copy of PunkBackup), close it and try again.",
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
