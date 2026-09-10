# Manual de desinstalación

Desinstalar este sistema es seguro y **no borra ninguna de tus fotos ya
respaldadas** — solo se elimina el programa en sí; tus carpetas de backup
(en tu disco o USB) quedan intactas donde estaban.

## Paso 1 — Detener el servidor

1. Abre la app (ícono del Escritorio) si no está abierta.
2. Si dice "Escuchando en el puerto...", presiona **"Detener backup"**.
3. Cierra la ventana.

## Paso 2 — Quitar la regla de Firewall (opcional)

Abre PowerShell **como administrador** y ejecuta:

```powershell
Remove-NetFirewallRule -DisplayName "iPhone WiFi Backup"
```

## Paso 3 — Borrar el acceso directo del Escritorio

Borra el ícono **"Backup Fotos y Videos"** de tu Escritorio (clic derecho →
Eliminar), igual que cualquier otro acceso directo.

## Paso 4 — Borrar la carpeta del programa

Borra la carpeta donde instalaste el proyecto (ej. `C:\Backup Fotos y
Videos`). Esto elimina el programa, su configuración y la lista de
perfiles/tokens — **no** toca tus carpetas de fotos ya respaldadas, que
viven en otra ubicación (la carpeta destino que elegiste para cada perfil).

## Paso 5 — (Opcional) Quitar el Atajo del iPhone

1. En el iPhone, abre **Atajos**.
2. Mantén presionado el atajo (ej. "Backup Fotos y Videos") → **Delete**.
3. Si creaste una automatización de WiFi, ve a la pestaña **Automation** →
   mantén presionada la automatización → **Delete**.
4. Si creaste el álbum "Respaldado" en versiones anteriores del sistema
   (ya no es necesario en la versión actual), puedes borrarlo desde Fotos →
   Álbumes.

## ¿Y mis fotos ya respaldadas?

Siguen exactamente donde estaban, en la carpeta que elegiste — el sistema
nunca las mueve ni las modifica al desinstalarse. Puedes seguir usándolas
normalmente, o volver a instalar el sistema más adelante apuntando a esa
misma carpeta para retomar donde quedaste (el índice interno vive dentro de
esa carpeta, así que se reconoce automáticamente).
