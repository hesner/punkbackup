# PunkBackup — Manual de instalación

## Qué es este sistema

Respalda automáticamente las fotos y videos de uno o varios iPhone/iPad hacia
tu PC Windows, por WiFi local, sin cable y sin depender de iCloud. Cada
persona/dispositivo tiene su propio perfil con su propia carpeta destino.

## Requisitos

- PC con **Windows 10 o 11**.
- Conexión a **internet** (solo para la instalación inicial).
- El iPhone/iPad y la PC deben poder conectarse a la **misma red WiFi** al
  momento de respaldar.
- Permisos de **administrador** en la PC (se piden solo una vez, para la
  regla de Firewall).

> Esta versión requiere unos pasos con la Terminal (PowerShell) para
> instalar Python. Una versión futura con instalador de doble clic
> eliminará este requisito.

## Paso 1 — Instalar Python

1. Abre **PowerShell** (búscalo en el menú Inicio).
2. Ejecuta:
   ```
   winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
   ```
3. Espera a que termine (unos minutos).

## Paso 2 — Copiar el proyecto a tu PC

1. Copia la carpeta completa del proyecto (la que te compartieron) a una
   ubicación permanente, por ejemplo: `C:\Backup Fotos y Videos`.
2. Abre PowerShell **dentro de esa carpeta** (clic derecho en la carpeta →
   "Abrir en Terminal", o navega con `cd`).

## Paso 3 — Preparar el entorno

Ejecuta, uno por uno, dentro de la carpeta del proyecto:

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Paso 4 — Crear el acceso directo del Escritorio

Ejecuta en PowerShell (ajusta la ruta si copiaste el proyecto a otro lugar):

```powershell
$projectDir = "C:\Backup Fotos y Videos"
$target = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
$script = Join-Path $projectDir "main.py"
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "PunkBackup.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $target
$Shortcut.Arguments = '"' + $script + '"'
$Shortcut.WorkingDirectory = $projectDir
$Shortcut.IconLocation = $target + ",0"
$Shortcut.Save()
```

Deberías ver un nuevo ícono **"PunkBackup"** en tu Escritorio.

## Paso 5 — Primer arranque y regla de Firewall

1. Haz doble clic en el ícono del Escritorio — se abre la app (ventana
   oscura, dos pestañas: "Principal" y "Perfiles").
2. Ve a la pestaña **Perfiles** → **"+ Agregar perfil"** → ponle un nombre
   a tu dispositivo (ej. "iPhone de [tu nombre]") → elige la carpeta donde
   quieres guardar tus fotos.
3. Ve a **Principal** → click **"Iniciar backup"**.
4. La primera vez, Windows puede mostrar un aviso de **Firewall** pidiendo
   permitir la conexión — acepta, marcando al menos **"Redes privadas"**.
5. Debe decir **"Estado: Escuchando en el puerto 8787"**.

## Paso 6 — Configurar tu iPhone

Sigue el **Manual de configuración del iPhone** (documento aparte) para
crear el Atajo de Shortcuts y, opcionalmente, la automatización por WiFi.

## ¿Ya quedó funcionando?

- Verifica en la pestaña Perfiles que tu perfil muestre su carpeta destino.
- Corre el Atajo en tu iPhone una vez de prueba.
- Revisa la carpeta que elegiste — deberían aparecer subcarpetas por Año/Mes
  con tus fotos.

Si algo no funciona, consulta el **Manual de solución de problemas**.
