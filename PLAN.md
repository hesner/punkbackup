# Plan: Backup de Fotos/Videos iPhone → PC (vía WiFi local)

## 1. Objetivo

Respaldar automáticamente (o manualmente) las fotos y videos del iPhone/iPad
de varias personas hacia un disco en la PC Windows `DELL-IOESTUDIO`, sin
cable USB y sin depender de iCloud, usando la red WiFi local de la casa.

## 2. Arquitectura

```
┌─────────────────────────┐          WiFi local (LAN)          ┌───────────────────────────────────┐
│   iPhone / iPad          │ ───────────────────────────────▶   │        PC Windows (servidor)       │
│   (un perfil por         │   HTTP POST /upload                │                                     │
│    dispositivo)          │   (foto/video + metadata           │  ┌───────────────────────────────┐  │
│                          │    + token DEL PERFIL)             │  │  Servidor local (FastAPI)      │  │
│  App Atajos (Shortcuts) │ ◀── /check (liviano, sin ─────── │  │  http://DELL-IOESTUDIO.local:PORT│  │
│  - Nativa de iOS,        │     archivo) responde si          │  │  - token → identifica el perfil │  │
│    no requiere instalar  │     already_backed_up             │  │  - /check: ¿existe ya en el     │  │
│    nada extra            │                                     │  │    destino ACTUAL de ese perfil?│  │
│  (sin álbum "ya          │ ◀─────────────────────────────── │  │  - Calcula hash, evita duplic.  │  │
│   respaldado" — la       │   GET /status                      │  │  - Guarda organizado por perfil │  │
│   verdad vive en el      │                                     │  │    y Año/Mes                    │  │
│   destino de la PC)      │                                     │  │  - Registra en índice (SQLite)  │  │
│                          │                                     │  └───────────────────────────────┘  │
│  Automatización:          │                                     │              │                        │
│  "Al conectar a WiFi de  │                                     │  ┌───────────────────────────────┐  │
│   casa" → correr Atajo   │                                     │  │  Dashboard GUI (CustomTkinter) │  │
│  (o se corre a mano)     │                                     │  │  - Iniciar / detener servidor   │  │
└──────────────────────────┘                                     │  │  - Gestionar perfiles (+ token) │  │
                                                                   │  │  - Ver progreso y log (oculto   │  │
  (repite: cada persona/dispositivo                               │  │    por defecto, desplegable)    │  │
   tiene su propio Atajo con su                                   │  │  - Configurar carpeta destino   │  │
   propio token)                                                  │  └───────────────────────────────┘  │
                                                                   │              │                        │
                                                                   │              ▼                        │
                                                                   │   <destino>/iphone-de-laura/2026/09/  │
                                                                   │   <destino>/ipad-de-hesner/2026/09/   │
                                                                   └───────────────────────────────────┘
```

## 3. Flujo general

### 3.1 Configuración inicial (una vez por PC)
1. Se instala Python en la PC (✅ hecho).
2. Se abre la app GUI y se elige la carpeta destino del backup (cualquier
   carpeta, en cualquier disco interno o USB externo — el explorador nativo
   de Windows permite navegar a cualquier subcarpeta, no solo a la raíz de
   una unidad).
3. Se agrega una regla de Firewall de Windows que permite tráfico entrante
   solo en el puerto elegido (ej. 8787), solo desde redes privadas (✅ hecho).
4. Se crea un **perfil por cada persona/dispositivo** desde la GUI (ej.
   "iPhone de Laura", "iPad de Hesner") — cada uno genera su propio token.
5. En cada iPhone/iPad, se crea (siguiendo instrucciones paso a paso) un
   **Atajo de Shortcuts** que, para cada foto/video de la Fototeca:
   - Primero pregunta al servidor (`/check`, liviano, sin mandar el archivo)
     si esa foto ya existe en la carpeta destino ACTUAL de ese perfil.
   - Solo si el servidor dice que falta, la sube (`/upload`) con el token
     **de ese perfil**.
   - No usa ningún álbum ni marcador en el iPhone — la verdad de "qué ya
     está respaldado" vive únicamente en la carpeta destino de la PC (ver
     sección 5), así que cambiar de USB/carpeta en la PC se refleja solo,
     sin configurar nada distinto en el iPhone.
6. Se crea una **Automatización personal** en cada dispositivo: "Cuando me
   conecte a la WiFi de casa → correr el Atajo" (sin pedir confirmación).

### 3.2 Backup automático (uso diario)
1. Cualquier persona llega a casa, su dispositivo se conecta a la WiFi.
2. Su automatización dispara su Atajo solo (no necesita abrir nada), usando
   su propio token — no importa el orden entre distintas personas.
3. Alguien en la casa abre la GUI en la PC cuando quiera (el servidor **no**
   arranca solo con Windows — se enciende manualmente desde la app y desde
   un acceso directo del Escritorio).
4. Mientras el servidor esté encendido y el dispositivo esté en la misma
   WiFi, sus fotos nuevas se suben a **su propia carpeta**, organizadas
   por Año/Mes — el servidor decide qué falta comparando contra lo que
   realmente existe ahí en ese momento.

### 3.3 Backup manual
- Se toca el Atajo directamente desde la pantalla de inicio (o por Siri) en
  cualquier momento, con el servidor encendido.

## 4. Estructura del proyecto

```
Backup photos/
├── PLAN.md
├── README.md                    (GitHub, en inglés)
├── LICENSE                      (MIT)
├── AGENTS.md                    (instrucciones de reconstrucción para un agente de IA)
├── requirements.txt
├── main.py                      (entry point de la GUI)
├── .venv/                       (entorno virtual, no se versiona)
├── config/
│   ├── config.example.json      (puerto, última carpeta usada — plantilla)
│   ├── config.json              (real, gitignored)
│   └── profiles.json            (real, gitignored — perfiles + tokens)
├── server/
│   ├── app.py                   (FastAPI: /upload, /check, /health, /status, /run/*)
│   ├── profiles.py              (ProfileStore: perfiles + historial de USB/carpetas)
│   ├── diskinfo.py              (etiqueta/serie/espacio del volumen de Windows, vía ctypes)
│   ├── manifest_db.py           (SQLite: índice incremental, uno por perfil)
│   ├── storage.py               (motor de backup: organiza, deduplica, resuelve conflictos, /check)
│   ├── runner.py                (arranca/detiene uvicorn bajo demanda)
│   └── run_dev.py               (runner manual para pruebas por terminal)
├── gui/
│   └── main_window.py           (CustomTkinter: perfiles, historial USB, iniciar/detener, log colapsable)
├── shortcuts/
│   ├── INSTRUCCIONES_ATAJO.md   (ES — plantilla genérica)
│   └── SHORTCUT_INSTRUCTIONS.md (EN — plantilla genérica)
├── docs/                        (manuales en PDF, landing page GitHub Pages)
├── installer/                   (PunkBackup.iss — Inno Setup, empaqueta dist/ de PyInstaller)
└── tests/
    ├── test_backup_engine.py
    ├── test_api.py
    └── test_profiles.py
```

## 4.1 Perfiles (multi-usuario / multi-dispositivo)

El sistema soporta **múltiples perfiles** dentro de la misma instalación en
la PC — cada perfil representa una persona o un dispositivo (ej. "iPhone de
Laura", "iPad de Hesner"). Diseño:

- Cada perfil tiene **su propio token secreto** (ya no hay un token único
  para toda la PC). El header `X-Backup-Token` que manda el Atajo identifica
  automáticamente de qué perfil se trata — el servidor no necesita que se
  "seleccione" un perfil activo de antemano.
- Cada perfil tiene **su propia carpeta destino independiente**, elegida al
  crear el perfil (o después, desde "⚙ Configuración"): `<carpeta del
  perfil>/<YYYY>/<MM>/archivo`. Puede ser un USB distinto para cada persona
  — no hay una carpeta compartida entre perfiles, ni necesitan sincronizarse.
- Cada perfil tiene **su propio índice incremental** (vive dentro de su
  propia carpeta, igual que en la sección 5), así que el progreso de Laura y
  el de Hesner son completamente independientes.
- Si el disco de un perfil no está conectado, ese perfil simplemente no
  puede recibir en ese momento (error claro, 503) — los demás perfiles
  siguen funcionando normal.
- Cada vez que se elige/cambia la carpeta destino de un perfil, se guarda un
  **historial de volúmenes** (etiqueta del USB, número de serie, capacidad,
  espacio libre, fecha) — botón "Historial USB" en "⚙ Configuración" —
  para que el usuario recuerde qué disco físico es cuál, aunque Windows le
  asigne una letra de unidad distinta cada vez que lo conecta.
- **Cualquier perfil puede respaldar en cualquier momento**: mientras el
  servidor esté encendido, no importa el orden — hoy corre el Atajo de
  Laura, mañana el de Hesner, sin que el usuario de la PC tenga que cambiar
  nada en la GUI.
- Gestión de perfiles (crear/renombrar/renovar token/eliminar) se hace
  **solo desde la GUI de la PC**, nunca por red — así un dispositivo ajeno
  en la WiFi jamás puede crearse un perfil por su cuenta.
- Eliminar un perfil solo revoca su token; **nunca borra los archivos ya
  respaldados** de esa persona/dispositivo.

## 5. Reglas de backup incremental (clave del sistema)

- El destino del backup **se elige por perfil, desde la pestaña "Perfiles"**
  (puede ser un disco externo distinto para cada persona/dispositivo; no es
  necesario que los distintos USB estén sincronizados entre sí).
- Dentro de la carpeta de cada perfil se guarda un índice local
  (`.iphone_backup_index/index.sqlite`) que viaja con ese disco.
- Al elegir una carpeta destino que ya tiene backups (nuestros o de otro origen),
  el sistema **respeta la estructura existente**: solo re-hashea un archivo
  cuando hay una colisión real de nombre, no escanea todo el árbol de antemano.
- **La fuente de verdad de "qué ya está respaldado" es SIEMPRE la carpeta
  destino actual, nunca un marcador guardado en el iPhone.** Por eso el
  Atajo no usa ningún álbum de "ya subido": antes de mandar cada archivo,
  llama a `POST /check` (solo nombre + tamaño + fecha, sin el archivo) y el
  servidor responde comparando contra lo que existe ahí mismo, en ese
  momento. Si cambias la carpeta/USB de un perfil, el chequeo
  automáticamente vuelve a reportar todo como "falta" para la carpeta
  nueva — sin ningún paso adicional en el iPhone.
- Para cada archivo que sí se sube (`POST /upload`):
  1. Si el nombre **y** el hash coinciden con algo ya existente → **no hace nada**
     (ya está respaldado).
  2. Si el nombre coincide pero el hash es distinto (discrepancia real) →
     **conserva ambos**: el archivo nuevo se guarda con un sufijo
     (ej. `IMG_1234__20260910-1832.HEIC`), nunca se sobrescribe el existente.
  3. Si el nombre no existe → se copia normal.
- **Dirección única**: iPhone → PC. El sistema nunca borra, mueve ni modifica
  nada en el iPhone. Solo lee y sube.
- **Estado consultable desde el iPhone**: el Atajo llama a `GET /status` antes
  y después de correr, y muestra (vía notificación en el propio iPhone):
  fecha/hora del último backup, cantidad de archivos copiados en esa
  corrida, y estado general — todo por perfil.

### 5.1 Bibliotecas grandes: barrido por bloques hacia atrás — HECHO

`Find Photos` de Shortcuts no tiene paginación nativa. Comprobado en el
dispositivo real: sin `Limit`, la acción falla directamente (incluso solo
contando resultados, sin ningún procesamiento) — así que un `Limit` es
obligatorio, no una optimización. Con un `Limit` fijo y sin forma de avanzar,
el Atajo revisaría siempre el mismo conjunto de fotos más viejas, sin nunca
llegar al resto de una biblioteca grande.

**Solución implementada** (ver `shortcuts/SHORTCUT_INSTRUCTIONS.md` /
`shortcuts/INSTRUCCIONES_ATAJO.md` para el paso a paso completo): dentro de
**una sola ejecución** del Atajo, un loop externo (`Repeat Repeticiones
times`) barre la biblioteca de la foto más nueva hacia la más vieja, en
bloques de 50 (`Find Photos` con `Date Taken is before Limite`, `Latest
First`, `Limit 50`). Al terminar cada bloque, `Limite` se actualiza a la
fecha del ítem más viejo del bloque (menos 1 minuto de colchón, para no
perder fotos con el mismo timestamp exacto en el borde de dos bloques —
ráfagas). Si un bloque viene vacío, el Atajo se detiene (`Stop This
Shortcut`) — ya pasó la foto más vieja.

Este límite y cursor viven **enteramente en el Atajo** — no hay ningún
endpoint de servidor dedicado a esto (se descartó un diseño anterior con un
endpoint `/resume_cursor` basado en `MAX(taken_at)`, por tener una falla
real: `Date Taken` no es monótono — una foto vieja reenviada por WhatsApp o
descargada de Google Photos puede entrar a la librería hoy con una fecha de
captura de hace años, y un cursor basado en esa fecha la saltaría para
siempre). Como el barrido siempre arranca desde "mañana" y avanza hacia
atrás dentro de la misma corrida, no hay ese punto ciego: cualquier foto,
sin importar su fecha, se revisa dentro de esa misma ejecución.

**Probado con carga real**: `Repeticiones` hasta 50 (≈2500 fotos revisadas
en una corrida) subiendo archivos reales sin errores. El límite superior de
cuántos bloques aguanta una sola ejecución de iOS no está confirmado —
queda como trabajo futuro probarlo hasta las ~180 vueltas que cubrirían una
biblioteca de ~9000 fotos.

**Protección contra archivos vacíos**: se confirmó (captura de depuración
directa al servidor) que el iPhone a veces envía un cuerpo vacío (0 bytes)
al `/upload` — sobre todo cuando el Atajo corre con la pantalla bloqueada o
en segundo plano (`User-Agent: BackgroundShortcutRunner`, el mismo modo en
que corre la automatización por WiFi). El servidor (`BackupEngine.
finalize_upload`) ahora **rechaza y no registra** un cuerpo de 0 bytes en
vez de guardarlo como "respaldado" — así `/check` lo sigue reportando como
"falta" y una corrida futura lo reintenta solo, sin envenenar el índice
para siempre. Confirmado con carga real: las fotos suben al 100% de
fiabilidad, en primer plano y en segundo plano. **Los videos, en cambio,
fallan de forma sistemática — no intermitente** (en una sesión de prueba
completa, cero videos lograron subir con contenido real, todos los
intentos dieron 0 bytes) — la causa exacta sigue sin determinar (descartado
iCloud, que estaba apagado; descartado que Google Fotos reemplace el
original local; mantener la app en primer plano NO lo arregla de forma
confiable). Gracias a la protección del servidor esto no representa
pérdida de datos ni corrupción — cada video queda pendiente y se reintenta
solo — pero **el respaldo de videos es, a la fecha, un problema abierto sin
resolver**, no una molestia menor.

**Diagnóstico agregado para investigar los videos** (`server/app.py`): cuando
llega un cuerpo de 0 bytes, el servidor ahora registra en el log de
actividad (reutiliza el logger `"backup_engine"` para que aparezca en el
panel de la GUI) el `Content-Length`/`Content-Type`/`User-Agent`/
`Transfer-Encoding` que declaró el teléfono. Se confirmó que `/upload` ya
cuenta los bytes realmente recibidos en el stream (no confía en el header
`Content-Length`), así que "0 bytes" significa que el cuerpo llegó
genuinamente vacío de principio a fin, no un problema de parseo de headers.
Hipótesis principal sin confirmar: un video grande (HEVC) necesita
exportarse/transcodificarse a un archivo temporal antes de que Shortcuts
pueda adjuntarlo, y esa exportación puede no terminar antes de que la
acción de red dispare — lo que explicaría por qué es independiente de
primer/segundo plano y siempre da exactamente 0 bytes en vez de datos
parciales.

### 5.2 Bug real: `taken_at` vacío misarchivó ~2000 fotos — RESUELTO

El chip dentro de la acción **Formatear fecha** que construye `TomadaEn`
se reconfiguró en silencio para apuntar a "Nombre" en vez de "Fecha de
captura" (ver AGENTS.md §5 punto 9) — probablemente al insertar el paso de
captura de `UltimaFecha` justo antes en el mismo loop del barrido por
bloques. El servidor recibió `taken_at` vacío para ~2116 archivos durante
varios días y, como `_year_month_dir()` usa "ahora" como respaldo cuando la
fecha es vacía o no parseable, todos terminaron amontonados en la carpeta
del mes en curso en vez de su mes real.

**Arreglo del Atajo**: el usuario volvió a seleccionar "Fecha de captura"
en ese chip — confirmado que las subidas nuevas ya llegan con fecha real.

**Recuperación de lo ya mal archivado**: se hizo con un script de
mantenimiento puntual (no forma parte del repo, fue descartable) que leyó
el EXIF real (`DateTimeOriginal`, tag `36867`) directamente de cada
archivo con Pillow + `pillow-heif`, y movió/actualizó el índice para los
que sí tenían ese dato — 714 de 2116. Los 1330 restantes (sobre todo
`.jpeg` de apps como WhatsApp, que iOS guarda sin metadatos) no tenían
ningún EXIF recuperable del archivo en sí. Para esos, en vez de intentar
recuperarlos desde el archivo, se **borraron del índice y del disco** —
la app de Fotos del iPhone sí conserva un "Date Taken" interno para
cualquier foto, tenga o no EXIF, así que al volver a correr el Atajo (ya
arreglado) sobre la biblioteca completa, el mecanismo normal de
`/check`+`/upload` los vuelve a subir solos, esta vez a su carpeta
correcta — sin necesidad de un script de "reparación" separado. El
respaldo es de un solo sentido y nunca toca el iPhone, así que borrar la
copia del PC es seguro: el original siempre sigue estando en el teléfono.

**Lección operativa**: cualquier script que escriba en `index.sqlite`
mientras la app pueda estar corriendo necesita reintentos reales alrededor
de cada `commit()` (no solo `PRAGMA busy_timeout`) — la GUI sondea el
estado cada 1.5s y la carpeta destino suele ser una USB externa lenta; ver
AGENTS.md §5 punto 10 para el detalle completo.

## 6. Modelo de datos (índice SQLite, uno por perfil)

Tabla `backed_up_files`:
| campo | tipo | descripción |
|---|---|---|
| id | INTEGER PK | |
| filename | TEXT | nombre original |
| sha256 | TEXT | hash del contenido (evita duplicados reales) |
| taken_at | TEXT | fecha de la foto/video |
| received_at | TEXT | fecha en que llegó al servidor |
| dest_path | TEXT | ruta final donde quedó guardado |
| size_bytes | INTEGER | |

Tabla `runs` (una corrida de backup, para `/status`):
| campo | tipo | descripción |
|---|---|---|
| id | TEXT PK | uuid |
| started_at / finished_at | TEXT | |
| files_new / files_skipped / files_conflict / files_error | INTEGER | contadores |

## 7. Arranque del sistema (definitivo)
- **Sin autoarranque.** El servidor y la GUI están 100% apagados al prender Windows.
- Se crea un **acceso directo en el Escritorio** que al hacer doble clic abre
  la GUI; desde ahí el usuario decide cuándo encender el servidor.

## 8. Distribución / instalador — HECHO
- `PunkBackupSetup.exe`, construido con PyInstaller (`--onedir --windowed`,
  ver comando exacto en `installer/PunkBackup.iss`) + Inno Setup
  (`installer/PunkBackup.iss`). Publicado como asset en
  https://github.com/hesner/punkbackup/releases/latest.
- Copia los archivos del programa a `Program Files\PunkBackup` (requiere
  admin — un solo UAC durante la instalación).
- Crea accesos directos del Escritorio y Menú Inicio, con el ícono real.
- Agrega/quita la regla de Firewall (`netsh advfirewall`, nombre de regla
  `"PunkBackup"`) como tarea opcional marcada por defecto.
- Desinstalador limpio registrado en "Agregar o quitar programas": borra
  programa + accesos directos + regla de Firewall; conserva a propósito
  `%APPDATA%\PunkBackup` (perfiles/tokens) para que sobreviva a una
  reinstalación.
- Detalle no obvio de PyInstaller 6+: en modo `--onedir`, todo excepto el
  `.exe` lanzador vive bajo `_internal\` (incluidos los assets agregados
  con `--add-data`) — `sys._MEIPASS` en frío apunta ahí, no a la carpeta
  del `.exe`. El `.iss` referencia los íconos como
  `{app}\_internal\assets\punkbackup.ico`, no `{app}\assets\...`.
- Detalle no obvio de Inno Setup: recuerda el estado de las casillas de
  `[Tasks]` entre instalaciones del mismo AppId y las pre-marca según la
  elección anterior — si el usuario no marcó "crear ícono de Escritorio"
  la primera vez, instalaciones posteriores pueden aparecer con esa
  casilla desmarcada por defecto aunque el usuario la vea marcada por
  costumbre. Por eso `[UninstallDelete]` borra el acceso directo del
  Escritorio incondicionalmente, sin depender de que Inno lo tenga
  registrado como creado por esa instalación.

## 9. Documentación a entregar
- `README.md` (GitHub, en inglés, estándar de la plataforma).
- **Manual de instalación** (PDF) — Español e Inglés.
- **Manual de troubleshooting** (PDF) — Español e Inglés.
- **Manual de desinstalación** (PDF) — Español e Inglés.
- **Manual de configuración del iPhone** (PDF, independiente de los anteriores)
  — Español e Inglés — paso a paso para crear el Atajo y la Automatización,
  incluye cómo crear un perfil nuevo por cada dispositivo.
- `AGENTS.md` / `BUILD_FROM_SCRATCH.md` — instrucciones completas para que un
  agente de IA (u otro desarrollador) pueda reconstruir el sistema completo
  desde cero: arquitectura, decisiones de diseño, orden de construcción,
  contratos de la API, esquema del índice, y criterios de aceptación.
- `LICENSE` — MIT.

## 10. Calidad y pruebas
- **Pruebas de consumo de recursos**: medir CPU/RAM del servidor en reposo y
  durante transferencias grandes (ej. 1000+ fotos, múltiples perfiles a la
  vez), para asegurar que no sature la PC.
- **Pruebas de consistencia**: repetir el mismo backup varias veces y verificar
  idempotencia; verificar que dos perfiles nunca mezclan archivos entre sí.
- **Pruebas de casos límite**: corte de WiFi a mitad de transferencia, archivo
  corrupto/incompleto, disco destino lleno, mismo archivo enviado dos veces
  seguidas, carpeta destino con backups previos de otra herramienta, token
  revocado a mitad de una corrida.
- Al final de las pruebas: reporte de hallazgos + propuestas concretas de mejora.

## 11. Nombre del proyecto: **PunkBackup** ✅ (decidido y aplicado)
- Concepto: "Tus recuerdos. Tu USB. Cero dependencia de la nube." — actitud
  deliberadamente rebelde/independiente (nada de nube, nada de suscripción).
- Dirección visual: **tema oscuro** con estética punk/industrial — aplicado
  en `gui/main_window.py` (reemplazó el tema claro forzado inicial).
- Ícono real de la app: una nube enojada con cresta punk fusionada a un
  conector USB (a partir de arte de referencia del usuario, procesado con
  Pillow — fondo recortado a transparencia, compuesto sobre una base
  oscura redondeada, exportado como `.ico` multi-resolución en
  `assets/punkbackup.ico`). Aplicado como ícono de la ventana
  (`iconbitmap`) y del acceso directo del Escritorio.
- Renombrado en el código: `APP_TITLE` en `gui/main_window.py`, `title=` de
  FastAPI en `server/app.py`. Repo en GitHub: `hesner/punkbackup`.

## 12. Estado de aprobaciones
- [x] Arquitectura general aprobada (incluye multi-perfil).
- [x] Licencia: MIT.
- [x] Regla de Firewall agregada y verificada (puerto 8787, red privada).
- [x] Carpeta destino: independiente por perfil, se elige desde "⚙ Configuración".
- [x] Interfaz: tema oscuro/punk, 2 pantallas (Principal / ⚙ Configuración —
      esta última agrupa Idioma + gestión de Perfiles).
- [x] Selector de idioma ES/EN en vivo (sin reiniciar), persistido en
      `config/config.json` (`language`), vía `gui/i18n.py`.
- [x] Switch Activo/Pausado por perfil (independiente del encendido general del servidor).
- [x] Puerto: **8787**.
- [x] Sin álbum de iOS — el Atajo pregunta al servidor vía `/check` (la
      carpeta destino de la PC es la única fuente de verdad).
- [x] WiFi de casa (para la automatización personal del usuario): `IOESTUDIO`.
- [x] Historial de volúmenes por perfil (etiqueta, serie, espacio libre).
- [x] Nombre final del proyecto: **PunkBackup**.
- [x] Tema oscuro/punk aplicado.
- [x] Publicado en GitHub (`hesner/punkbackup`, público, MIT) + GitHub Pages
      (`hesner.github.io/punkbackup`).
- [x] Instalador Windows (`PunkBackupSetup.exe`, Inno Setup) — publicado en
      GitHub Releases, probado de punta a punta (instalar/actualizar/
      desinstalar) en la PC real del usuario. Ver sección 8.
- [x] Diálogos propios oscuros (`gui/dialogs.py`) reemplazando el
      `messagebox`/`CTkInputDialog` nativos, que rompían el tema oscuro.
- [x] Backfill de bibliotecas grandes: barrido por bloques hacia atrás
      dentro de una sola corrida del Atajo, probado con carga real
      (`Repeticiones` hasta 50, ≈2500 fotos, sin errores). Ver sección 5.1.
- [x] Protección del servidor contra subidas vacías (0 bytes) — se
      rechazan en vez de registrarse, autorreparación vía reintento.
- [x] Hora local (no UTC) en la GUI; panel de actividad expandible.
- [x] Bug del chip `Formatear fecha` (misarchivo de ~2000 fotos) diagnosticado,
      arreglado en el Atajo, y los archivos ya mal archivados recuperados o
      re-encolados para resubirse. Ver sección 5.2.
- [ ] Diagnóstico de headers para el 0-byte de videos agregado
      (`server/app.py`), pero **la causa raíz de los videos sigue sin
      resolver** — sigue siendo el problema abierto más importante.
- [ ] Pendiente en la GUI (pedido por el usuario, no iniciado): marcar en el
      log cuándo inicia/termina cada corrida de backup, mostrar cuántos
      archivos se guardaron en la ÚLTIMA corrida específicamente (no el
      acumulado), y mostrar en algún otro lugar el total de archivos
      actualmente en la carpeta destino del perfil.
- [ ] Automatización WiFi en el iPhone del usuario (al final).
- [ ] Compartir el Atajo a otro iPhone/perfil (al final).
