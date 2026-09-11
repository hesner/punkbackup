# PunkBackup — Manual de instalación

## Qué es este sistema

Respalda automáticamente las fotos y videos de uno o varios iPhone/iPad hacia
tu PC Windows, por WiFi local, sin cable y sin depender de iCloud. Cada
persona/dispositivo tiene su propio perfil con su propia carpeta destino.

## Requisitos

- PC con **Windows 10 o 11**.
- Conexión a **internet** (solo para descargar el instalador).
- El iPhone/iPad y la PC deben poder conectarse a la **misma red WiFi** al
  momento de respaldar.
- Permisos de **administrador** en la PC (se piden una sola vez, al
  instalar — para copiar el programa y agregar la regla de Firewall).

## Paso 1 — Descargar el instalador

Descarga `PunkBackupSetup.exe` desde la página de descargas del proyecto:

**https://github.com/hesner/punkbackup/releases/latest**

## Paso 2 — Ejecutar el instalador

1. Haz doble clic en `PunkBackupSetup.exe`.
2. Windows puede mostrar un aviso de **SmartScreen** ("Windows protegió tu
   PC") por tratarse de un programa nuevo sin firma digital de pago — haz
   clic en **"Más información"** → **"Ejecutar de todas formas"**.
3. Acepta el aviso de **Control de cuentas de usuario (UAC)** — el
   instalador necesita permisos de administrador para copiar el programa a
   `Archivos de programa` y para agregar la regla de Firewall.
4. Si tu antivirus escanea el archivo (por ejemplo Avast, "Suspicious file
   detected" / escaneo de reputación), es normal para un instalador nuevo —
   déjalo terminar el análisis, no debería encontrar nada.
5. Sigue el asistente:
   - Elige el idioma de instalación (esto **no** define el idioma de la
     app — la app tiene su propio selector ES/EN en "⚙ Configuración").
   - Deja marcada la casilla **"Create a desktop icon"** para tener el
     acceso directo en el Escritorio.
   - Deja marcada la casilla de la **regla de Firewall** (recomendado —
     si no la marcas, tendrás que agregarla a mano más adelante para que tu
     iPhone pueda conectarse).
   - Haz clic en **Install** y espera a que termine.
6. Al final, deja marcada la opción de lanzar PunkBackup y haz clic en
   **Finish** — la app se abre sola.

## Paso 3 — Primer arranque

1. Se abre la app (ventana oscura, dos pantallas: "Principal" y
   "⚙ Configuración").
   > La app abre en español por defecto. Si prefieres inglés, entra a
   > "⚙ Configuración" y toca "English" — cambia al instante, sin reiniciar.
2. Ve a **"⚙ Configuración"** → **"+ Agregar perfil"** → ponle un nombre
   a tu dispositivo (ej. "iPhone de [tu nombre]") → elige la carpeta donde
   quieres guardar tus fotos.
3. Ve a **Principal** → click **"🤘 Iniciar backup"**.
4. Si no marcaste la regla de Firewall durante la instalación, Windows
   puede mostrar aquí el aviso pidiendo permitir la conexión — acepta,
   marcando al menos **"Redes privadas"**.
5. Debe decir **"Estado: Escuchando en el puerto 8787 🤘"**.

## Paso 4 — Configurar tu iPhone

Sigue el **Manual de configuración del iPhone** (documento aparte) para
crear el Atajo de Shortcuts y, opcionalmente, la automatización por WiFi.

## ¿Ya quedó funcionando?

- Verifica en "⚙ Configuración" que tu perfil muestre su carpeta destino.
- Corre el Atajo en tu iPhone una vez de prueba.
- Revisa la carpeta que elegiste — deberían aparecer subcarpetas por Año/Mes
  con tus fotos.

Si algo no funciona, consulta el **Manual de solución de problemas**.
