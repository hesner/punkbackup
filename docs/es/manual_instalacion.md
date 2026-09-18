# PunkBackup — Manual de instalación

## Qué es este sistema

Respalda automáticamente las fotos y videos de uno o varios iPhone/iPad hacia
tu PC Windows, por WiFi local, sin cable y sin depender de iCloud. Cada
persona/dispositivo tiene su propio perfil con su propia carpeta destino.

## ⚠ Importante: esta app no tiene firma digital de pago

PunkBackup es un proyecto independiente y pequeño — el `.exe` **no** tiene
firma digital de pago (ese certificado cuesta dinero; más abajo hay notas
sobre eso por si te interesa). Esto tiene dos consecuencias reales y
esperadas:

- **Windows SmartScreen** te va a avisar una vez al instalar (ver Paso 2).
  Es normal y no representa ningún riesgo — sigue los pasos de abajo.
- **Tu antivirus puede ir más allá de solo avisar.** Los antivirus usan
  heurísticas (patrones de comportamiento), no solo listas de virus
  conocidos, y un programa nuevo sin firma que habla con la red puede
  disparar esas heurísticas — aunque PunkBackup solo habla con tu propio
  iPhone en tu propia WiFi y nunca manda nada a ningún otro lado. **Se ha
  visto específicamente a Avast cerrar PunkBackup en silencio poco después
  de abrirlo**, sin ningún mensaje de error de la app (simplemente
  desaparece). Si te pasa esto, es Avast, no un error de PunkBackup — mira
  el arreglo abajo.

Puedes revisar el código fuente completo tú mismo (es un proyecto de código
abierto) si quieres verificar exactamente qué hace antes de confiar en él.

### Arreglo: "Avast me sigue cerrando la app"

1. Abre **Avast** → **Menú → Cuarentena** (o "Virus Chest") — si aparece
   `PunkBackup.exe` ahí, restáuralo y agrega una excepción para que no lo
   vuelva a agarrar.
2. O bien: **Avast → Menú → Configuración → General → Excepciones** →
   agrega la carpeta de instalación (por defecto
   `C:\Program Files\PunkBackup\`) para que Avast la deje de escanear/bloquear
   por completo.
3. Vuelve a abrir PunkBackup desde el ícono del Escritorio — ahora debería
   quedarse abierta.

Es el mismo arreglo para otros antivirus que se comporten así (Windows
Defender, Norton, etc.) — agrega una excepción para la carpeta de
instalación de PunkBackup.

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
   > ⚠️ **No asumas que todo está bien solo porque no salió ningún
   > aviso.** Algunas PC tienen desactivada la opción "avisarme cuando el
   > Firewall bloquee una app nueva" de Windows (común en equipos de
   > trabajo administrados), o la red está configurada como "Pública" en
   > vez de "Privada" — en cualquiera de los dos casos, Windows puede
   > bloquear la conexión en silencio, sin ningún aviso. Si más adelante
   > tu iPhone no puede conectarse al servidor y nunca viste este aviso,
   > ve directo a la sección "El iPhone no puede conectarse al servidor"
   > del **Manual de solución de problemas** y revisa/agrega la regla de
   > Firewall a mano — no asumas que la regla existe solo porque la
   > instalación terminó sin errores.
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
