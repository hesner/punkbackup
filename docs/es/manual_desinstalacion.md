# PunkBackup — Manual de desinstalación

Desinstalar este sistema es seguro y **no borra ninguna de tus fotos ya
respaldadas** — solo se elimina el programa en sí; tus carpetas de backup
(en tu disco o USB) quedan intactas donde estaban.

## Paso 1 — Detener el servidor (opcional)

Si la app está abierta y dice "Escuchando en el puerto...", presiona
**"Detener backup"** y cierra la ventana. No es obligatorio — el
desinstalador puede cerrar la app por ti — pero es más prolijo hacerlo a
mano primero.

## Paso 2 — Desinstalar desde Windows

1. Abre **Configuración** → **Aplicaciones** → **Aplicaciones instaladas**
   (o busca "Agregar o quitar programas" en el menú Inicio).
2. Busca **"PunkBackup"** en la lista.
3. Haz clic en los tres puntos (o clic derecho) → **Desinstalar**.
4. Acepta el aviso de **Control de cuentas de usuario (UAC)**.
5. Sigue el asistente y haz clic en **Finish** al terminar.

Esto elimina automáticamente:

- El programa (`Archivos de programa\PunkBackup`).
- Los accesos directos del Escritorio y del Menú Inicio.
- La regla de Firewall que se agregó durante la instalación.

Y **conserva a propósito**:

- Tus perfiles y tokens (`%APPDATA%\PunkBackup`) — así, si reinstalas más
  adelante, no tienes que volver a crear cada perfil ni repegar los tokens
  en los Atajos de cada iPhone.
- Tus carpetas de fotos ya respaldadas (en el disco/USB que elegiste para
  cada perfil) — el desinstalador nunca toca esas carpetas.

Si además quieres borrar tus perfiles/tokens, hazlo a mano borrando la
carpeta `%APPDATA%\PunkBackup` después de desinstalar.

## Paso 3 — (Opcional) Quitar el Atajo del iPhone

1. En el iPhone, abre **Atajos**.
2. Mantén presionado el atajo (`PunkBackup`) → **Delete**.
3. Si creaste una automatización de WiFi, ve a la pestaña **Automation** →
   mantén presionada la automatización → **Delete**.

## ¿Y mis fotos ya respaldadas?

Siguen exactamente donde estaban, en la carpeta que elegiste — el sistema
nunca las mueve ni las modifica al desinstalarse. Puedes seguir usándolas
normalmente, o volver a instalar el sistema más adelante apuntando a esa
misma carpeta para retomar donde quedaste (el índice interno vive dentro de
esa carpeta, así que se reconoce automáticamente).
