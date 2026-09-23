# Plan: Backup de Fotos/Videos iPhone → PC (vía WiFi local)

## 1. Objetivo

Respaldar automáticamente (o manualmente) las fotos y videos del iPhone/iPad
de varias personas hacia un disco en tu PC Windows, sin cable USB y sin
depender de iCloud, usando la red WiFi local de la casa.

## 2. Arquitectura

```
┌─────────────────────────┐          WiFi local (LAN)          ┌───────────────────────────────────┐
│   iPhone / iPad          │ ───────────────────────────────▶   │        PC Windows (servidor)       │
│   (un perfil por         │   HTTP POST /upload                │                                     │
│    dispositivo)          │   (foto/video + metadata           │  ┌───────────────────────────────┐  │
│                          │    + token DEL PERFIL)             │  │  Servidor local (FastAPI)      │  │
│  App Atajos (Shortcuts) │ ◀── /check (liviano, sin ─────── │  │  http://[TU-PC].local:PORT      │  │
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
                                                                   │   <destino>/iphone-de-maria/2026/09/  │
                                                                   │   <destino>/ipad-de-diego/2026/09/    │
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
   "iPhone de María", "iPad de Diego") — cada uno genera su propio token.
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
│   ├── manifest_db.py           (SQLite: índice incremental, uno por perfil; reapea runs huérfanos)
│   ├── storage.py               (motor de backup: organiza, deduplica, resuelve conflictos, /check,
│   │                              detección de extensión por contenido + respaldo de fecha por EXIF)
│   ├── runner.py                (arranca/detiene uvicorn bajo demanda; verifica el bind de verdad,
│   │                              reintenta ante conflictos transitorios de puerto)
│   ├── video_metadata.py        (corrige el creation_time real dentro del contenedor de video)
│   ├── mirror.py                (segunda copia opcional: sync_mirror() PC-side, hacia otra carpeta/USB)
│   ├── config.py                (AppConfig: puerto, idioma, preferencias de inicio, timeout de inactividad)
│   ├── paths.py                 (rutas dev vs. instalado — app_root()/user_data_dir())
│   └── run_dev.py               (runner manual para pruebas por terminal)
├── gui/
│   ├── main_window.py           (CustomTkinter: perfiles, historial USB, iniciar/detener, log colapsable
│   │                              + persistido en disco, Preferencias)
│   ├── i18n.py                  (traducciones ES/EN, cambio de idioma en vivo)
│   ├── dialogs.py               (diálogos propios oscuros — reemplazan messagebox nativo)
│   └── autostart.py             (inicio con Windows vía el Run key de HKCU)
├── shortcuts/
│   ├── INSTRUCCIONES_ATAJO.md         (ES — manual principal, instala el .shortcut)
│   ├── SHORTCUT_INSTRUCTIONS.md       (EN — manual principal, instala el .shortcut)
│   ├── INSTRUCCIONES_ATAJO_MANUAL.md  (ES — manual alternativo, construcción a mano)
│   ├── MANUAL_BUILD_INSTRUCTIONS.md   (EN — manual alternativo, construcción a mano)
│   └── PunkBackup.shortcut      (Atajo exportado, listo para importar — placeholders genéricos)
├── docs/                        (manuales en PDF, landing page GitHub Pages)
├── installer/                   (PunkBackup.iss — Inno Setup, empaqueta dist/ de PyInstaller)
└── tests/
    ├── test_backup_engine.py
    ├── test_api.py
    ├── test_profiles.py
    ├── test_runner.py
    ├── test_video_metadata.py
    └── test_mirror.py
```

## 4.1 Perfiles (multi-usuario / multi-dispositivo)

El sistema soporta **múltiples perfiles** dentro de la misma instalación en
la PC — cada perfil representa una persona o un dispositivo (ej. "iPhone de
María", "iPad de Diego"). Diseño:

- Cada perfil tiene **su propio token secreto** (ya no hay un token único
  para toda la PC). El header `X-Backup-Token` que manda el Atajo identifica
  automáticamente de qué perfil se trata — el servidor no necesita que se
  "seleccione" un perfil activo de antemano.
- Cada perfil tiene **su propia carpeta destino independiente**, elegida al
  crear el perfil (o después, desde "⚙ Configuración"): `<carpeta del
  perfil>/<YYYY>/<MM>/archivo`. Puede ser un USB distinto para cada persona
  — no hay una carpeta compartida entre perfiles, ni necesitan sincronizarse.
- Cada perfil tiene **su propio índice incremental** (vive dentro de su
  propia carpeta, igual que en la sección 5), así que el progreso de un
  perfil y el de otro son completamente independientes.
- Si el disco de un perfil no está conectado, ese perfil simplemente no
  puede recibir en ese momento (error claro, 503) — los demás perfiles
  siguen funcionando normal.
- Cada vez que se elige/cambia la carpeta destino de un perfil, se guarda un
  **historial de volúmenes** (etiqueta del USB, número de serie, capacidad,
  espacio libre, fecha) — botón "Historial USB" en "⚙ Configuración" —
  para que el usuario recuerde qué disco físico es cuál, aunque Windows le
  asigne una letra de unidad distinta cada vez que lo conecta.
- **Cualquier perfil puede respaldar en cualquier momento**: mientras el
  servidor esté encendido, no importa el orden — hoy corre el Atajo de un
  perfil, mañana el de otro, sin que el usuario de la PC tenga que cambiar
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
fiabilidad, en primer plano y en segundo plano.

**Los videos, en cambio, fallaban de forma sistemática — no intermitente**
(en una sesión de prueba completa, cero videos lograron subir con
contenido real, todos los intentos dieron 0 bytes). Diagnóstico agregado
en `server/app.py`: cuando llega un cuerpo de 0 bytes, el servidor registra
en el log de actividad (reutiliza el logger `"backup_engine"` para que
aparezca en el panel de la GUI) el `Content-Length`/`Content-Type`/
`User-Agent`/`Transfer-Encoding` que declaró el teléfono. Se confirmó que
`/upload` ya cuenta los bytes realmente recibidos en el stream (no confía
en el header `Content-Length`), así que "0 bytes" significa que el cuerpo
llegó genuinamente vacío de principio a fin — Shortcuts nunca llegó a
materializar los datos reales del video antes de armar la petición.

**RESUELTO (2026-09-16): causa raíz encontrada y arreglo confirmado con
evidencia real de servidor.** Investigación en vivo con un Atajo de
prueba descartó, una por una: `Guardar archivo` (Save File) tanto a
iCloud Drive como a almacenamiento local ("En este iPhone") — falla para
video en ambos casos, incluso con un video de cámara viejo que sí sube
bien por la vía normal; esperar unos segundos antes de subir — mismo
resultado; duplicar el ítem en Fotos — la acción no existe en Shortcuts.
**La única acción que sí logra materializar el video es `Encode Media`**
(búscala como "Encode", no existe una acción llamada "Convert Video").
Usada con `Size: Passthrough`, un video que consistentemente subía como
0 bytes se subió con éxito real: `test-convert-video.mp4`, 7,096,331
bytes, verificado directamente en `backed_up_files` — no solo una vista
previa del teléfono (las vistas previas de Quick Look demostraron ser
poco confiables durante toda esta investigación: mostraban "No Items"
para ítems que sí tenían datos reales, así que se abandonaron como señal
de diagnóstico a favor de verificar siempre contra la base de datos real
del servidor).

**Comparación técnica del video original vs. el procesado con `Encode
Media` (Size: Passthrough)**, hecha con `ffprobe` sobre el mismo archivo
descargado directo del iPhone sin modificar vs. el que pasó por Encode
Media:

| | Original (iPhone) | Encode Media (Passthrough) |
|---|---|---|
| Códec de video | H.264, perfil High | H.264, perfil High — igual |
| Resolución | 1920×1080 | 1920×1080 — igual |
| Frame rate | 30 fps (2008 cuadros) | 30 fps (2008 cuadros) — igual |
| Bitrate de video | 648,976 bps | 648,976 bps — igual |
| Códec/bitrate de audio | AAC 44.1kHz estéreo, 193,519 bps | idéntico |
| Duración | 67.07 s | 67.07 s — igual |
| Tamaño | 7,096,486 bytes | 7,096,331 bytes (0.002% menos) |

Únicas diferencias reales encontradas: el orden de los streams (Encode
Media pone el video primero, el original trae el audio primero — sin
efecto perceptible) y la etiqueta de metadata
`com.apple.quicktime.creationdate` (la fecha real de captura embebida en
el archivo) que Encode Media no conserva. Esto último **no afecta la
fecha del backup** porque `taken_at` se captura por separado desde
Shortcuts (atributo "Date Taken" de Fotos) antes de tocar el video, no
depende de esa metadata interna del archivo. **Conclusión: "Passthrough"
es, en la práctica, sin pérdida real de calidad** — mismo códec, misma
resolución, mismo bitrate, mismos cuadros exactos, solo reempaqueta el
contenedor.

**Diseño del arreglo para el Atajo real** (reintento condicional, NO
conversión de todos los videos): en el paso c) del barrido por bloques,
justo después del `Obtener contenido de URL` que sube el archivo —
`Obtener valor de diccionario` → clave `detail` → sobre esa respuesta →
`Si` tiene algún valor (la subida directa falló) → `Encode Media` sobre
`Elemento de repetición` (`Size: Passthrough`) → un segundo
`Obtener contenido de URL` idéntico al primero pero con el resultado de
`Encode Media` como cuerpo. Así, las fotos y los videos de cámara que ya
suben bien (confirmado: 11 videos `IMG_XXXX` subidos con éxito antes de
esta investigación) nunca tocan `Encode Media` — solo pagan el costo de
recodificación los videos que realmente lo necesitan (en la práctica,
videos importados de otras apps como WhatsApp, con nombre tipo UUID en
vez de `IMG_XXXX`).

**CONFIRMADO EN PRODUCCIÓN (2026-09-17): 7 de 7 videos que fallaban antes
ahora suben completos.** Construido en el Atajo real, verificado con una
prueba controlada real (no un atajo de prueba desechable) — resultado
directo de `backed_up_files`:

| Archivo | Tamaño real recibido |
|---|---|
| IMG_0640.mov | 6.3 MB |
| 5450c81e-...mp4 | 11.6 MB |
| ScreenRecording_09-14-2026 | 45.6 MB |
| IMG_0455.mov | 5.4 MB |
| e065584b-...mp4 | 11.6 MB |
| 3621fdc3-...mp4 | 5.3 MB |
| IMG_0398.mov | 6.2 MB |

**Bug adicional encontrado y arreglado en el camino**: la primera versión
del arreglo devolvía HTTP 422 para el rechazo de 0 bytes — confirmado en
dispositivo real que un código de error HTTP hace que Shortcuts aborte en
silencio el resto de esa vuelta del loop (todo lo agregado después:
`Obtener valor de diccionario` → `Si` → `Encode Media` → reintento nunca
se ejecutaba). Arreglado en `server/app.py`: el rechazo de 0 bytes ahora
responde **200** con el error solo en el campo `detail` del cuerpo, igual
que `/check` ya hacía con `missing` — nunca un código de error HTTP para
este caso, aunque el archivo sigue sin registrarse como respaldado.

**Detalle cosmético también arreglado**: como cada video que necesita el
reintento genera un "error" real en su primer intento (por diseño), el
contador `files_error` quedaba inflado con reintentos que en realidad sí
tuvieron éxito. `ManifestDB.mark_error()`/`resolve_error()` ahora
recuerdan qué archivo falló en qué corrida y descuentan ese error si el
mismo archivo se sube con éxito más adelante en la misma corrida — el
contador en vivo ya no cuenta como "error permanente" algo que se
autorreparó al toque.

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

### 5.3 Bug histórico: notificación final vacía / `finished_at` nunca se completaba — RESUELTO

Desde el inicio del proyecto, prácticamente ninguna corrida completaba
`/run/finish` (`finished_at` quedaba `NULL` en la tabla `runs`, y la
notificación final mostraba "Nuevos: / Ya existían: / Conflictos:" sin
ningún número). Se documentaba como "cosmético, baja prioridad" sin causa
raíz conocida.

**Causa real encontrada (2026-09-17)**: en el `Get Contents of URL` hacia
`/run/finish`, el header `X-Backup-Token` estaba puesto por error dentro
de **Request Body → Form** en vez de en **Headers**, y el campo de
formulario `run_id` (obligatorio en el servidor, `Form(...)`) **no
existía en absoluto**. El servidor rechazaba la petición (falta un campo
requerido), Shortcuts abortaba el resto de esa sección en silencio —mismo
mecanismo que el bug de los videos— y ninguna de las variables
`FilesNew`/`FilesSkipped`/`FilesConflict` llegaba a tener valor.

**Arreglo**: mover `X-Backup-Token` a **Headers**, agregar el campo de
formulario `run_id` → variable `RunID`. Confirmado con evidencia real de
servidor — el log ahora muestra la línea `=== Backup run finished ... — N
new, N already had, N conflicts, N errors ===` que nunca había aparecido
en todo el historial del proyecto, y la notificación en el teléfono
muestra los números reales.

### 5.4 Ítems sin `Date Taken` NI extensión — causa raíz atacada del lado del servidor (2026-09-18)

Se detectaron duplicados repetidos de un mismo `ScreenRecording_09-14-2026`
(6 copias) y dos versiones del mismo screenshot guardado desde Facebook
(una con extensión `.jpg`, otra sin extensión). Investigado a fondo:

- **Causa**: estos ítems no tienen ningún valor de `Date Taken` legible
  por Shortcuts (llega `NULL` al servidor, no solo vacío) — parece
  específico de grabaciones de pantalla y de algunas imágenes importadas
  desde otras apps (Facebook, en este caso), que no traen la metadata de
  captura estándar de Fotos.
- **Efecto 1**: sin fecha real, `_year_month_dir()` usa "hoy" como
  respaldo — estos ítems siempre caen en el mes en curso en vez de su
  fecha real (que probablemente ni existe).
- **Efecto 2 (hipótesis, no confirmada en dispositivo)**: al no tener
  `Date Taken`, es probable que el barrido "Más reciente primero" los
  ubique siempre cerca del principio, así que cada corrida nueva los
  vuelve a encontrar sin importar cuánto haya avanzado `Limite` en
  corridas anteriores — y como cada vez pasan por el reintento de
  `Encode Media` (que reescribe metadata interna, cambiando el hash),
  el sistema los trata como contenido nuevo y genera otra copia con
  sufijo en vez de reconocerlos como ya respaldados.

**Alcance original, medido (2026-09-16)**: 3 archivos distintos de 2232 en
total (0.13%) — no parecía un problema generalizado. **Decisión del
usuario en ese momento**: no modificar el Atajo (el arreglo propuesto era
usar `Date Created` como respaldo cuando `Date Taken` no tiene valor) —
quedó documentado como limitación conocida y aceptada.

**Ampliación del hallazgo (2026-09-18)**: una consulta directa a
`backed_up_files` mostró que el problema es más amplio de lo medido
originalmente — **37 filas con filename sin NINGÚN punto** (ni una sola
extensión), no solo las grabaciones de pantalla: también 9 fotos
`IMG_XXXX` normales y un archivo con nombre UUID, todas con `taken_at
IS NULL` también. Confirmado leyendo los bytes reales de varios de estos
archivos (firma binaria): el contenido está intacto (JPEG y MOV
válidos) — el problema es puramente de metadata que Shortcuts no logra
leer para ciertos ítems, nunca corrupción de datos.

**Arreglo de causa raíz, del lado del servidor** (`server/storage.py`,
`finalize_upload()`), en vez de seguir intentando parchar el Atajo
(que ya ha demostrado fallar en silencio repetidas veces en este
proyecto):
- **Extensión faltante → detectada por firma binaria del contenido**
  (`_detect_extension()`): JPEG (`FF D8 FF`), PNG, GIF, y contenedores
  `ftyp` (MOV/MP4/HEIC según el "brand" de 4 bytes) — solo se usa cuando
  el nombre que mandó el Atajo no trae NINGUNA extensión; nunca sobrescribe
  una que el cliente sí envió, aunque el contenido real no coincida.
- **`taken_at` faltante → respaldo leyendo el EXIF real del archivo**
  (`_read_exif_taken_at()`, vía `Pillow` + `pillow-heif`, ya usadas una
  vez en este proyecto para el script puntual de reorganización de 714
  archivos): lee `DateTimeOriginal` directo de los bytes, independiente
  de lo que Shortcuts haya reportado. Solo funciona para formatos con
  EXIF (JPEG/HEIC) — videos siguen sin fecha real disponible por esta vía,
  caen en el respaldo de "ahora" como antes.
- Ambos son best-effort y no rompen nada existente: si no se puede
  detectar/leer nada, el comportamiento es idéntico al de antes (nombre
  tal cual llegó, fecha "ahora").
- 4 tests nuevos en `tests/test_backup_engine.py` (30/30 pasando):
  detección de extensión para foto y para video, extensión NUNCA
  sobrescrita cuando ya viene puesta, y respaldo de fecha por EXIF.
- Nuevas dependencias declaradas en `requirements.txt`: `pillow==12.3.0`,
  `pillow-heif==1.7.0` (ya estaban instaladas en el entorno de una sesión
  anterior, solo faltaba declararlas).

**Limpieza retroactiva de los 38 archivos ya existentes**: hecha el mismo
día con un script puntual (no versionado en el repo, mismo patrón que
`reorganize_by_exif.py` de una sesión anterior) que reutiliza
`_detect_extension()`/`_read_exif_taken_at()` tal cual —ninguna lógica
nueva, solo aplicada retroactivamente. Resultado: **38/38 corregidos, 0
omitidos** — extensión agregada a todos, y 8 fotos además reubicadas a
su carpeta de fecha real (recuperada del EXIF). Verificado en disco:
los archivos nuevos existen con su extensión correcta, los viejos
sin extensión ya no están.

### 5.4.1 Hipótesis del §5.4 confirmada y corregida de raíz: duplicados sin fin de video por `Encode Media` (2026-09-22)

La hipótesis del "Efecto 2" de arriba (no confirmada en 2026-09-18) se
confirmó con evidencia real: el usuario reportó timeouts todo el día
2026-09-22 y, revisando la base de datos, `ScreenRecording_09-14-2026.mov`
tenía **54 copias duplicadas (2.46 GB desperdiciados)** — cada barrido
del Atajo lo volvía a encontrar cerca del principio (sin `taken_at`,
siempre "reciente"), pasaba por el reintento de `Encode Media`, y como
la lógica de conflicto (`server/storage.py`) compara `sha256` crudo, un
hash distinto en cada re-encode se traducía en "contenido diferente,
conservar ambos" — sin límite.

**Verificación byte a byte contra los 54 duplicados reales** (antes de
tocar código): tamaño idéntico en los 54, y las únicas diferencias caían
en el `moov` (metadata del contenedor) — el `mdat` (los bytes reales de
audio/video) era **100% idéntico** en los 55 archivos. Primer intento de
arreglo (enmascarar solo los campos `creation_time`/`modification_time`
de `mvhd`/`mdhd`, reutilizando el parser de `video_metadata.py` ya
existente para `fix_creation_time`) **no fue suficiente** — verificado
contra los 55 archivos reales, seguía dando 55 firmas distintas: Encode
Media reescribe más metadata de la que esos dos campos cubren. El
arreglo correcto y robusto, confirmado con los mismos 55 archivos reales
(**1 sola firma para los 55**): comparar solo el contenido de `mdat`,
ignorando el contenedor completo.

**Arreglo (`server/video_metadata.py::content_signature()`,
`server/storage.py::finalize_upload()`, v1.7.4)**: cuando el `sha256`
crudo no coincide Y la extensión es de video, se compara además el
`content_signature` (hash de solo `mdat`) del archivo entrante contra el
ya existente — si coinciden, se trata como "ya respaldado" (se descarta
la subida entrante, no se crea copia nueva) en vez de "conservar ambos".
6 tests nuevos (`tests/test_video_metadata.py`,
`tests/test_backup_engine.py`, sintéticos — nunca contenido real de
usuario en el repo): mismo contenido con timestamps distintos → misma
firma; contenido genuinamente distinto → firma distinta (para no volverse
demasiado permisivo); `None` para archivos no-ISO-BMFF.

**Limpieza retroactiva de los 54 duplicados**: verificados con
`content_signature` (55/55 idénticos, confirmado antes de borrar nada),
conservado solo `ScreenRecording_09-14-2026.mov` (el nombre canónico sin
sufijo), borrados los otros 54 archivos + sus 54 filas en
`backed_up_files`. **2.46 GB liberados en D:**. Verificado
post-limpieza: 1 fila en la base de datos, 1 archivo en disco.

**Validado en vivo el mismo día, con la app reconstruida e instalada
(v1.7.4)**: durante una prueba real desde el iPhone, tanto
`ScreenRecording_09-14-2026` como otro video previamente problemático
(`ScreenRecording_02-16-2026`) pasaron por el reintento de `Encode
Media` y salieron correctamente como `already backed up (re-encoded
copy, content unchanged), skipped` — cero duplicados nuevos.

**Nota operativa importante que costó tiempo real este día**: el primer
intento de probar el fix en vivo pareció fallar (se generó OTRO
duplicado) — la causa no era el código sino que **la app instalada
(`C:\Program Files\PunkBackup`) seguía siendo el build de antes del
fix** (el commit del fix quedó después del último build/instalación).
Sin reconstruir (`PyInstaller`) y reinstalar (`Inno Setup`), cualquier
cambio de código no tiene ningún efecto en la app que corre de verdad —
lección ya existía implícitamente en el proyecto pero vale la pena
tenerla explícita: **antes de dar un fix por probado en vivo, confirmar
la fecha de build del `.exe` instalado contra la fecha del commit.**

### 5.4.2 `/check` no reconocía como respaldados los ítems sin extensión — corregido de raíz (2026-09-22, v1.7.5)

Pregunta del usuario, tras confirmar el fix de §5.4.1: **¿tendría sentido
revisar si un archivo ya fue copiado ANTES de hacer conversiones/análisis
de extensión, para agilizar el skip?** — es exactamente lo que `/check`
ya debería hacer (existe justo para eso, un chequeo barato sin bytes
antes de subir nada), así que investigar por qué no lo estaba logrando
para este archivo llevó a una causa raíz real y distinta de la de
§5.4.1.

**Confirmado con evidencia real**: `POST /check` con
`filename=ScreenRecording_09-14-2026` (sin extensión, tal cual lo manda
el Atajo) devolvía `{"missing": true}` — pero el mismo `/check` con
`filename=ScreenRecording_09-14-2026.mov` (con extensión) devolvía `{}`
(ya existe). **Causa**: `check_exists()` solo compara la ruta exacta
`año/mes/<nombre-tal-cual-lo-mandó-el-Atajo>`; la extensión de este
archivo se detecta y se agrega **únicamente del lado del servidor**,
durante `/upload` (nunca durante `/check`, que es deliberadamente sin
bytes) — así que la ruta que `check_exists()` busca nunca coincide con
la que realmente existe en disco, para siempre, para cualquier ítem sin
extensión. Efecto práctico: aunque el archivo ya esté respaldado, el
Atajo lo sigue intentando subir en TODOS los barridos futuros — y para
un video problemático de la categoría de §5.4/§5.4.1, eso significa
seguir pagando el costo de `Encode Media` cada vez, sin fin, aunque el
servidor ya lo reconozca y lo descarte correctamente después de recibirlo.

**Arreglo descartado por riesgo real**: la solución obvia (buscar
"cualquier archivo con ese nombre, sin importar la extensión") se
descartó — estos ítems ya no tienen NINGÚN otro dato que los distinga
(sin `taken_at`, ver §5.4), así que dos elementos genuinamente distintos
que compartieran el mismo nombre base (posible para grabaciones de
pantalla sin sufijo de hora) se fusionarían en uno solo — el segundo
jamás se subiría, pérdida silenciosa de un archivo real.

**Arreglo implementado (seguro)**: `backed_up_files` gana una columna
`original_filename` (migración automática vía `ALTER TABLE` en
`ManifestDB.__init__`, para bases de datos ya existentes) que guarda el
nombre EXACTO tal como lo mandó el Atajo la primera vez que este ítem se
subió/reconoció de verdad — nunca una suposición. `check_exists()`
consulta primero la ruta exacta (como antes) y, si el nombre no trae
extensión, cae a un segundo chequeo por `original_filename` exacto
(`ManifestDB.find_by_original_filename()`). Los caminos de "ya
respaldado" (hash idéntico, y el de §5.4.1 de video re-encodeado)
además hacen `backfill_original_filename()` sobre la fila existente —
así un archivo que ya estaba respaldado ANTES de este fix (sin la
columna poblada) se autocorrige la próxima vez que se lo vuelva a
encontrar, sin necesitar ningún script de migración de datos.

**Validado en vivo (v1.7.5)**: `ScreenRecording_09-14-2026` pasó una
última vez por el ciclo de 0-byte/`Encode Media` (esperado — su fila aún
no tenía `original_filename`), salió como `already backed up (re-encoded
copy...)`, y el backfill se aplicó — confirmado con
`SELECT filename, original_filename ...` mostrando
`('ScreenRecording_09-14-2026.mov', 'ScreenRecording_09-14-2026')`, y
`/check` con el nombre sin extensión pasó de `{"missing": true}` a `{}`
en la siguiente consulta. El mismo backfill se confirmó también para
varias fotos normales (`IMG_6619.jpg`, etc.) que el Atajo también manda
sin extensión — su "skip" en sí no se vuelve más rápido (nunca pasaban
por `Encode Media`, eso es solo de video), pero desde el próximo barrido
deberían dejar de intentarse subir por completo.

2 tests nuevos en `tests/test_backup_engine.py` (67/67 pasando):
reconocimiento vía `original_filename` para un ítem sin extensión, y
auto-sanación del backfill para una fila simulada como "anterior al fix"
(sin migración de datos real, solo NULL-eada a propósito en la prueba).

### 5.5 Bug: el aviso de inactividad se disparaba solo con abrir la app — RESUELTO

Tras agregar el aviso de "backup inactivo 5+ minutos" (§ este mismo doc,
feature de la GUI), un usuario reportó que el aviso salía apenas 5 minutos
después de abrir la app, sin que ningún backup real hubiera corrido esa
sesión.

**Causa real**: `ManifestDB.get_status()` calcula `state` mirando si el
run más reciente tiene `finished_at IS NULL`, sin importar qué tan viejo
sea ese run. Si la app se cierra (o el proceso muere) a mitad de una
corrida, ese run queda "running" en la base de datos **para siempre** —
ninguna corrida futura puede llamar a `/run/finish` con ese `run_id`
(`RunID` es una variable local del Atajo, no sobrevive a esa ejecución).
Cada vez que la app se reabre, `state` vuelve a reportar "running"
inmediatamente por ese run viejo, y 5 minutos después el aviso de
inactividad se dispara — sobre un run que en realidad se abandonó horas
antes, no que se acaba de estancar.

**Arreglo**: `ManifestDB.__init__` ahora cierra automáticamente
cualquier run que siga con `finished_at IS NULL` la primera vez que se
abre la base de datos de ese perfil en un proceso nuevo (`UPDATE runs SET
finished_at = NOW() WHERE finished_at IS NULL`). Es seguro porque un
`run_id` de una ejecución de un proceso anterior nunca puede volver a
recibir su `/run/finish` real. Test:
`test_reopening_reaps_a_run_left_running_by_a_previous_process`.

### 5.6 Hallazgo: la automatización WiFi puede re-dispararse tras un corte breve de conexión

Probado deliberadamente (2026-09-17): con un backup real corriendo,
apagar el WiFi del iPhone ~10 segundos y volver a encenderlo.

**Resultado bueno, confirmado**: ningún archivo se perdió. Hubo un hueco
real de ~99 segundos sin subidas (más que los 10s reales, por el tiempo
que toma a iOS reconectar/reintentar DNS), y las subidas se reanudaron
solas después, sin intervención — el diseño autosanador (`/check` contra
el estado real del destino) cubre esto sin problema.

**Hallazgo colateral**: justo en medio de ese hueco apareció un `run_id`
**nuevo** en la tabla `runs` — es decir, se volvió a llamar `/run/start`
a mitad de lo que debería haber sido una sola ejecución continua del
Atajo. Hipótesis mejor sustentada (no confirmada al 100%, pero consistente
con TODA la evidencia observada, incluyendo 4 corridas separadas la misma
mañana sin `/run/finish`, cada ~20-40 min): la automatización personal
está configurada con la condición **"Wi-Fi Connects"** — y volver a
encender el WiFi cuenta como una nueva conexión, así que la automatización
se re-dispara, lanzando una SEGUNDA ejecución del Atajo encima de la que
ya estaba corriendo (o se acababa de cortar).

**Impacto real**: ninguno en los datos (el diseño de deduplicación por
nombre+hash hace que dos corridas superpuestas no corrompan ni dupliquen
nada, en el peor caso reintentan lo mismo). El costo es tiempo/batería
extra y un historial de corridas más confuso de leer (varios `run_id`
cortos entrelazados en vez de una corrida limpia). **No se tomó ninguna
acción correctiva** — el usuario decidió dejarlo así por ahora dado que
no hay pérdida de datos; queda documentado como comportamiento conocido,
no como bug a resolver.

### 5.7 Bug real: el aviso de inactividad no siempre se disparaba — CORREGIDO (2026-09-18)

Confirmado con evidencia directa (screenshot con timestamps exactos): con
el timeout configurado en 10 minutos, una corrida real (`run_id
d4a613e3...`) tuvo un hueco de **14 minutos 34 segundos** sin ninguna
línea de log mientras seguía en estado "running" — y el aviso de
inactividad nunca apareció.

**Causa raíz encontrada**: `_check_idle_backups()` compartía el mismo
ciclo `after()` cada 1.5s (y el mismo bloque `try/except: pass`) que las
otras 3 funciones de refresco de estadísticas de la GUI
(`_refresh_status_loop`). Si cualquiera de esas otras funciones lanzaba
una excepción (ej. contención de SQLite durante una ráfaga de subidas —
ya documentado como riesgo real en este proyecto), **toda la
verificación de inactividad se saltaba en silencio esa vuelta**, sin
dejar ningún rastro — mientras el log de subidas seguía funcionando
normal porque es un mecanismo completamente aparte (`_drain_log_queue`,
alimentado directamente por el logger del servidor).

**Arreglo**: `_check_idle_backups()` ahora corre en su **propio ciclo
`after()` independiente** (`_idle_check_loop`), separado del refresco de
estadísticas — una falla en uno nunca puede volver a bloquear al otro.
Además, **ya no se tragan excepciones en silencio**: tanto
`_refresh_status_loop` como `_idle_check_loop` ahora registran cualquier
error real en el log de actividad (visible en pantalla y persistido en
disco, ver más abajo) en vez de un `except: pass` ciego.

**Confirmado funcionando en producción, el mismo día**: en una corrida
real, el aviso `⏸ "iphone de Hes": sin actividad hace 10+ minutos...`
apareció exactamente a los 10 minutos (12:38:06, 10 minutos después de
la última subida a las 12:28:06) — el timeout configurado por el
usuario. Cierra el ciclo de este bug de punta a punta: reportado,
diagnosticado, corregido, y verificado con evidencia real.

### 5.8 Nuevo: log de actividad persistido en disco, con limpieza automática (2026-09-18)

El log de actividad de la GUI vivía únicamente en memoria (el widget de
texto) — se perdía por completo al cerrar la app, haciendo imposible
verificar después del hecho si algo como el bug de la sección 5.7
realmente ocurrió o no. Pedido explícito del usuario tras justo ese caso:
"guarda el log en algún lugar con autolimpieza para que no sea eterno".

**Regresión encontrada y corregida el mismo día, minutos después de
publicar el fix de 5.7**: reportar cada excepción real (en vez de
tragarla en silencio) hizo evidente algo que antes pasaba desapercibido
— un perfil sin carpeta destino configurada (`HTTPException 409`, una
condición completamente normal, no un bug) generaba una traza de error
cada 1.5 segundos, para siempre, inundando el log. Corregido en
`_check_idle_backups()`: cualquier excepción ahora se registra **una
sola vez por racha** (se resetea en cuanto la llamada vuelve a tener
éxito), igual que ya se hacía con el propio aviso de inactividad — así
un problema real nunca queda en silencio, pero una condición esperada
tampoco satura el log.

### 5.9 Ambigüedad real: no se podía distinguir un `/run/finish` genuino de un "reap" — CORREGIDO (2026-09-18)

El usuario preguntó cómo sabía que una corrida "terminó limpia". Revisando
el log completo de hoy, la línea `=== Backup run finished ... ===` (la
que confirma una llamada real a `/run/finish` desde el Atajo) **nunca
había aparecido ni una sola vez**, a pesar de que varias corridas sí
mostraban `finished_at` con valor — es decir, no había forma de saber si
esas corridas terminaron de verdad o si simplemente fueron cerradas por
el mecanismo de "reap" (§5.5) al reabrir la app tras cada reinstalación
de hoy. Ambos casos dejaban el mismo rastro en la base de datos.

**Arreglo**: `ManifestDB.__init__` ahora registra explícitamente en el
log, vía `logger.warning(...)`, cada vez que reapa una corrida —
mencionando el `run_id` y aclarando que **no** es un `/run/finish` real,
así que su conteo final puede estar incompleto. Test:
`test_reap_logs_a_warning_distinct_from_a_real_run_finish` (31/31
pasando). Con esto, cualquier corrida futura que termine se puede
distinguir con certeza: si aparece `=== Backup run finished ... ===`,
el Atajo llegó al final de verdad; si aparece `!! Run ... was left
"running" by a previous session ...`, se cerró a la fuerza al reabrir
la app.

### 5.10 Bug serio: el servidor podía "fallar en silencio" al iniciar — CORREGIDO (2026-09-18)

Reportado en vivo por el usuario: "todo está corriendo" en la PC, pero el
iPhone decía **"Could not connect to the server"**. Investigado en el
momento: `netstat` confirmó que **nada** tenía el puerto 8787 abierto,
aunque el log ya mostraba `Servidor iniciado. A darle.` y la pantalla
decía "Escuchando en el puerto 8787".

**Causa raíz**: `ServerController.start()` lanza uvicorn en un hilo en
segundo plano y regresa de inmediato, **sin esperar confirmación** de que
el bind al puerto haya funcionado. Si falla (puerto ocupado, permisos,
etc.), uvicorn internamente hace `sys.exit(1)` dentro de ese hilo — una
`SystemExit`, que ni siquiera un `except Exception` genérico captura. Y
como la app corre vía `pythonw.exe`, `sys.stderr` está redirigido a un
buffer en memoria que nadie lee (ver `main.py`) — el error desaparece por
completo, sin dejar rastro en ningún lado. La GUI, mientras tanto, ya
había actualizado la pantalla a "Escuchando" un instante antes, sin
verificar nada.

**Arreglo** (`server/runner.py`, `gui/main_window.py`):
- `ServerController._run()` ahora captura `BaseException` (no solo
  `Exception`, precisamente para atrapar el `SystemExit` de uvicorn) y
  registra el motivo real vía el logger `backup_engine` — visible en el
  log y persistido en disco.
- Nuevo `ServerController.wait_until_listening(timeout=5.0)`: bloquea
  brevemente hasta confirmar que `uvicorn.Server.started` es `True` (el
  bind realmente ocurrió) o hasta que el hilo muere.
- `_start_server()` en la GUI ahora **espera esa confirmación antes de
  decir "Escuchando"** — si falla, revierte a "Detenido" y muestra un
  diálogo de error real con la causa, en vez de mentir sobre el estado.
- 2 tests nuevos en `tests/test_runner.py` (33/33 pasando):
  arranque exitoso confirmado con una conexión real, y conflicto de
  puerto detectado explícitamente (no en silencio) al levantar dos
  servidores en el mismo puerto.

**Mejora del mismo día, tras ver el error real en pantalla**: el primer
diálogo de error mostraba solo `"1"` como detalle — `str(SystemExit(1))`,
el código de salida que usa uvicorn internamente al fallar el bind, sin
ningún mensaje humano. Agregado `ServerController._preflight_bind_error()`:
antes de lanzar uvicorn, intenta un bind de un socket plano al mismo
host/puerto — si falla, captura el mensaje real de Windows (ej.
`[WinError 10048] Only one usage of each socket address...`) en vez del
código genérico. Chequeo síncrono, inmediato, sin necesidad de esperar al
hilo de uvicorn para el caso de fallo.

**Mejora adicional el mismo día, con hipótesis del usuario confirmada en
la práctica**: el primer `[WinError 10048]` real capturado en pantalla
coincidió con Avast interceptando el `.exe` recién lanzado (lo escanea,
a veces lo cierra y lo reabre — ver la sección de firma de código) — el
usuario planteó que la segunda apertura probablemente encuentra el
puerto todavía "ocupado" por el cierre abrupto del primer intento, aunque
nada lo esté usando realmente unos segundos después. Confirmado: momentos
después de ese error, el puerto ya estaba completamente libre.

**Arreglo**: `ServerController.start_with_retry(attempts=4,
retry_delay=2.0)` — reintenta el bind unas pocas veces con una pequeña
espera entre intentos antes de rendirse. La GUI ahora corre esto en un
hilo de fondo (no bloquea la ventana) mientras muestra **"Estado:
Iniciando backup..."** y deshabilita el botón para evitar doble clic;
solo si los 4 intentos fallan se muestra el diálogo de error real. 2
tests nuevos en `tests/test_runner.py` (35/35 pasando): uno confirma que
un conflicto transitorio (el puerto se libera a los 0.3s) se resuelve
solo vía el reintento, otro confirma que un conflicto permanente sigue
fallando limpiamente tras agotar los intentos.

**Hallazgo secundario, limpiado de paso**: la regla de Firewall
"PunkBackup" estaba **duplicada 10 veces** en esta PC — `netsh ... add
rule` no tiene modo "reemplazar si existe", así que cada reinstalación
de hoy agregó una copia más. Inofensivo funcionalmente (todas son
idénticas, Allow), pero acumulaba basura. `installer/PunkBackup.iss`
ahora borra la regla antes de agregarla en cada instalación, haciendo el
proceso idempotente.

**Implementación**: cada línea que llega a `_drain_log_queue` (el único
punto donde confluyen tanto los mensajes del servidor como los propios
de la GUI) también se escribe a
`%APPDATA%\PunkBackup\logs\activity.log` vía un
`logging.handlers.TimedRotatingFileHandler` (rota a medianoche,
`backupCount=180` → conserva ~6 meses, borra automáticamente lo más
viejo). Mismo formato de timestamp que la pantalla
(`dd-MM-yyyy HH:MM:SS`). Best-effort: si escribir a disco falla por
cualquier razón, no afecta la visualización en vivo.

### 5.11 Bug real: videos con fecha "hoy" en apps externas (PhotoPrism) — CORREGIDO (2026-09-18)

Reportado por el usuario: en PhotoPrism, muchos videos de hoy aparecían
con fecha de creación "hoy", aunque la carpeta Año/Mes donde quedaron
guardados sí era la correcta.

**Causa raíz**: cuando un video falla en 0 bytes y se reintenta con
**Encode Media (Passthrough)** (§5.1/AGENTS.md lección 12), ese proceso
reescribe el contenedor del video y **estampa el campo `creation_time`
del contenedor con el momento del reintento** (hoy), no la fecha real de
grabación — aunque el video/audio en sí queden sin pérdida. `taken_at` (lo
que usa PunkBackup para la carpeta y la base de datos) se captura de
Shortcuts *antes* de tocar el video, así que siempre fue correcto — el
problema es que herramientas externas como PhotoPrism leen la fecha
**dentro del archivo**, no la carpeta.

**Investigación**: `mutagen` no sirve — esos campos no son tags estilo
iTunes, son campos binarios dentro de la estructura ISO-BMFF (`moov >
mvhd` y `moov > trak > mdia > mdhd`, uno de estos últimos por cada pista
— 7 en total en un video típico de iPhone: video, audio, y 5 pistas de
metadata). Dos caminos evaluados: empaquetar `ffmpeg.exe` (simple pero
~80-100MB extra + complejidad de licencia), o parchar el contenedor
directamente en Python puro (sin dependencias nuevas). Se eligió la
segunda, validada con una prueba de calidad rigurosa antes de aplicarla a
cualquier archivo real: sobre un video real de 18.5MB, el parche cambió
**exactamente 64 bytes** (8 campos de fecha de 8 bytes cada uno), tamaño
de archivo idéntico, resto del `ffprobe` (códec, resolución, bitrate,
duración, todas las pistas) **100% idéntico**, y decodificación completa
sin errores.

**Arreglo**: `server/video_metadata.py` — `fix_creation_time()` reescribe
`mvhd` + cada `mdhd` en el mismo lugar (sin redimensionar, sin tocar
`mdat`/los datos reales del video), soporta boxes versión 0 y 1
(campos de 32 y 64 bits), y nunca lanza excepción (best-effort: si el
archivo no es un contenedor ISO-BMFF reconocible, simplemente no hace
nada). Conectado en `finalize_upload()` (`server/storage.py`): se aplica
a toda subida de video nueva con `taken_at` conocido, justo después de
que el archivo llega a su carpeta final. 4 tests nuevos con un archivo
MP4 sintético construido a mano (39/39 pasando).

**Corrección retroactiva**: script puntual (no versionado, mismo patrón
que los anteriores) aplicado a los 387 videos existentes con `taken_at`
conocido — **376 corregidos**, 0 archivos faltantes, 0 fechas
no interpretables, 11 sin caja `moov` (no son contenedores ISO-BMFF
reconocibles — pendiente de investigar si vale la pena, alcance menor al
2% del total).

### 5.12 Velocidad de subida medida en el ambiente real (2026-09-21)

Petición del usuario: documentar cuánto tarda un respaldo de verdad en el
ambiente de prueba actual — iPhone 15, WiFi de casa, PC Dell — con un
cuadro por tipo de archivo y una proyección para bibliotecas de 1.000,
5.000 y 10.000 elementos.

**Metodología** (datos reales, no estimación): se consultó de forma
solo-lectura (`sqlite3.connect(f"file:{path}?mode=ro", uri=True)` — nunca
`ManifestDB()` directo, ver punto de la sección 6/AGENTS.md sobre el efecto
secundario de "reap") la tabla `backed_up_files` del índice SQLite real de
este proyecto (`D:\Backup Fotos y Videos\.iphone_backup_index\index.sqlite`,
7.223 archivos reales acumulados desde el 2026-09-10). Para cada extensión,
se calculó la mediana del intervalo entre `received_at` de archivos
consecutivos (filtrando saltos >120s, que corresponden a huecos entre
corridas distintas, no a tiempo de subida real) — esto aproxima el tiempo
real punta a punta por archivo (incluye el round-trip de `/check` +
`/upload`, no solo la transferencia de red pura).

**Nota metodológica importante, descartada a propósito**: la duración
`started_at`→`finished_at` de la tabla `runs` NO es confiable para esto —
varias corridas muestran duraciones de horas/días que en realidad
corresponden a corridas nunca cerradas por el Atajo y luego "reapeadas" al
reabrir la app (ver sección 5.9), no tiempo real de backup. Por eso el
análisis usa únicamente los timestamps de archivo individual
(`received_at`), que no sufren ese problema.

**Resultado inicial** (con todo el histórico, 7.223 archivos desde
2026-09-10): tiempo mediano por archivo — JPEG ~2s, HEIC ~5.5s, PNG ~5.3s,
MP4 ~10s, MOV ~19s. La mayor parte del tiempo en fotos chicas es overhead
fijo de las 2 peticiones HTTP por elemento (no transferencia de red pura)
— por eso el tiempo por archivo no escala linealmente con el tamaño. Con
la mezcla real de esta biblioteca (55% JPEG, 33% HEIC, 5% PNG, 4% MP4, 3%
MOV), el promedio ponderado dio **~4.2s/elemento**.

**Corrección posterior (mismo día, misma conversación)**: el usuario pidió
rectificar con los logs más recientes (en vez de todo el histórico) y
desglosar la proyección por `Repeticiones` en vez de por tamaño de
biblioteca genérico, con columnas por tipo de archivo. Se recalculó usando
solo los últimos ~3 días (≥2026-09-19, 1.338 archivos) — el promedio
ponderado resultante fue casi idéntico (~4.23s/elemento), aunque los
tiempos por tipo individual sí cambiaron de forma notable (JPEG bajó a
~1.7s, HEIC subió a ~6.5s, MOV bajó a ~16.7s) — variación esperable entre
ventanas de tiempo distintas, no un error de metodología. Se publicó una
tabla `Repeticiones → elementos totales → desglose por tipo → tiempo`
(10 a 250 repeticiones) en el Manual de solución de problemas (EN/ES),
marcando 50 y 180 como los únicos valores confirmados funcionando de
verdad en un dispositivo real (180 confirmado por el usuario ese mismo
día — corre sin fallar, aunque el usuario no ha dejado una corrida
terminar completa por detenerla seguido).

**Hallazgo real, no resuelto, encontrado durante esta corrección**: se
midieron también los intervalos entre líneas de log consecutivas de tipo
"ya respaldado, se salta" (`activity.log`, patrón `> = `), no solo las de
archivo nuevo (`> + `). Resultado: salto→salto tiene una mediana de
**~20.5s** (n=26, ruidoso, máximo 496s) — nada cercano a "casi instantáneo,
sin transferir archivo" como asumía la documentación anterior de
`Repeticiones`. Esto **contradice** la suposición de que re-revisar
bloques ya completos es prácticamente gratis, y es la explicación más
probable de por qué las corridas del usuario con `Repeticiones = 180` no
han llegado a terminar en sesiones normales de uso, más allá de haberlas
detenido manualmente. Causa raíz no confirmada — candidatos: overhead fijo
por acción de la propia app Atajos (cada `Get Contents of URL` tiene
latencia propia, documentado ya en AGENTS.md punto 2 para "File Size"),
o que `Find Photos` re-escanea la biblioteca completa en cada bloque
conforme el límite de fecha se mueve más atrás. **Pendiente**: investigar
la causa con más muestra antes de intentar arreglarlo — por ahora solo
está documentado como advertencia honesta en el Manual de solución de
problemas y en la nota "Tuning `Repeticiones`" de ambos manuales de
construcción manual.

**Decisión**: sí vale la pena documentarlo — responde una pregunta real
("¿esto se va a demorar para siempre?") con datos reales de producción, no
una promesa genérica. Publicado en ambos manuales de troubleshooting
(EN/ES) con las salvedades correspondientes (varía según mezcla foto/video
del usuario, señal WiFi, y el límite de `Repeticiones` por corrida).

### 5.13 Bug real: la USB A llena a mitad de un respaldo fallaba en silencio — CORREGIDO (2026-09-21)

Encontrado por revisión de código (no por reporte del usuario), mientras se
diseñaba la funcionalidad de segunda copia (sección de "diseño en curso"
más abajo) — el usuario pidió explícitamente que el sistema "igual lo
intentará hasta su llenado" cuando el destino no tiene espacio suficiente,
lo cual ya era cierto (no existe ningún cálculo previo de espacio total
contra toda la biblioteca), pero al revisar qué pasaba cuando el disco
realmente se llena a mitad de escribir un archivo se encontró que el
`OSError` (`ENOSPC`) se re-lanzaba sin convertirse en una respuesta
controlada — el mismo patrón de bug ya corregido varias veces esta semana
(server-bind, idle-notice): según la lección más importante de este
proyecto (una respuesta que no sea 2xx aborta en silencio el resto de esa
vuelta del loop del Atajo — ver punto 11 de AGENTS.md), esto significaba
que cada foto restante de ese bloque fallaba en silencio, sin ningún
mensaje de "se llenó el disco" visible para el usuario.

**Corregido** en `server/app.py` (`/upload`, el camino real que usa el
iPhone) y en `server/storage.py` (`BackupEngine.process_upload`/
`stage_bytes`, el camino que usan las pruebas): ambos ahora capturan
`OSError` específicamente y devuelven el mismo patrón ya establecido para
el caso de 0 bytes — una respuesta 200 con `detail` explicando el error,
nunca registrado como respaldado, así que `/check` lo sigue reportando
como faltante y una corrida posterior (una vez se libere espacio) lo
reintenta solo. De paso se corrigió una fuga menor relacionada:
`stage_bytes` dejaba el archivo parcial (`.part`) huérfano en la carpeta
de staging cuando la escritura fallaba a mitad de camino — ahora se
limpia siempre.

**Probado sin ningún dispositivo real**, simulando el disco lleno con
`monkeypatch` sobre `open()` (el archivo se crea de verdad en disco, pero
`write()` falla igual que un disco realmente lleno) — 2 pruebas nuevas
(`tests/test_api.py::test_disk_full_during_upload_returns_graceful_error`,
`tests/test_backup_engine.py::test_disk_full_during_write_is_not_recorded_as_backed_up`),
verificadas primero fallando contra el código SIN el fix (confirmando que
sí detectan el bug real) y luego pasando con el fix aplicado. 41/41 pruebas
pasando en total.

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
  `"PunkBackup"`) como tarea opcional marcada por defecto — **borra antes
  de agregar** en cada instalación (idempotente; antes se duplicaba en
  cada reinstalación, llegó a acumular 10 copias idénticas en una sesión
  de pruebas intensiva).
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
- Mismo problema, variante encontrada después: el acceso directo de
  **desinstalar** usaba el nombre localizado `{cm:UninstallProgram,...}`,
  que cambia según el idioma elegido en el instalador — reinstalar en un
  idioma distinto dejaba un segundo acceso directo huérfano
  (`Desinstalar PunkBackup.lnk` junto a `Uninstall PunkBackup.lnk`).
  Arreglado con un nombre fijo en inglés (`Uninstall PunkBackup`),
  siempre igual sin importar el idioma del instalador.

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
- [x] Automatización personal por WiFi: configurable a la red de casa del
      usuario (ver `shortcuts/*.md`, paso de la automatización).
- [x] Historial de volúmenes por perfil (etiqueta, serie, espacio libre).
- [x] Nombre final del proyecto: **PunkBackup**.
- [x] Tema oscuro/punk aplicado.
- [x] Publicado en GitHub (`hesner/punkbackup`, público, MIT) + GitHub Pages
      con dominio propio **`punkbackup.com`** (comprado en Cloudflare,
      DNS apuntando a GitHub Pages, certificado HTTPS aprobado).
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
- [x] Bug de los videos (0 bytes) **resuelto y confirmado en producción**:
      causa raíz encontrada (`Encode Media`, `Size: Passthrough`, sin
      pérdida real de calidad — comparado con `ffprobe`), reintento
      condicional construido en el Atajo real, y verificado con 7/7 videos
      previamente fallidos subiendo completos. Ver sección 5.1.
- [x] Bug histórico de `/run/finish` (notificación final vacía,
      `finished_at` nunca se completaba desde el inicio del proyecto)
      resuelto — el campo `run_id` faltaba en el cuerpo de esa petición.
      Ver sección 5.3.
- [x] GUI: el log marca cuándo inicia/termina cada corrida de backup (con
      el resumen final), la tarjeta de cada perfil muestra por separado el
      total de archivos en su carpeta destino y cuántos se guardaron
      específicamente en la última corrida. Ver sección 6 (esquema `runs`)
      y `gui/main_window.py`/`gui/i18n.py`.
- [x] Automatización WiFi en el iPhone del usuario — configurada y
      **confirmada corriendo sola** (disparó el Atajo sin tocar el
      teléfono). Hallazgo aparte, documentado y aceptado sin arreglar:
      puede re-dispararse tras un corte breve de WiFi. Ver sección 5.6.
- [x] Archivo `.shortcut` exportado (`shortcuts/PunkBackup.shortcut`) es
      ahora el método **principal** de instalación (manual de configuración
      del iPhone reescrito para llevar a esto primero); el armado manual
      paso a paso se movió a un manual **alternativo** aparte
      (`shortcuts/MANUAL_BUILD_INSTRUCTIONS.md` /
      `shortcuts/INSTRUCCIONES_ATAJO_MANUAL.md`, con su propio PDF).
      Auditoría de usabilidad (2026-09-21) encontró que el archivo no tenía
      forma real de descargarse (no estaba en el release de GitHub, ni
      había link directo en ningún manual) y que el paso de iOS "Permitir
      atajos no confiables" no estaba documentado en ningún lado — ambos
      corregidos: el archivo ahora se sube como asset en cada release de
      GitHub (⚠️ **recordatorio para releases futuros**: `gh release upload
      vX.Y.Z shortcuts/PunkBackup.shortcut` — si se omite, el link
      evergreen `releases/latest/download/PunkBackup.shortcut` que usan
      ambos manuales principales da 404), y el manual principal ahora
      explica el paso de Ajustes → Atajos → Avanzado → "Permitir atajos no
      confiables" explícitamente. También se corrigió una referencia
      rota: el manual principal decía "salta a la sección 'Is it
      working?'" pero esa sección nunca existió en este archivo (estaba en
      el manual de instalación de la PC, sobre un tema distinto) — ahora
      tiene su propia sección real "Step 3 — Test it" / "Paso 3 —
      Pruébalo".
- [ ] Segundo perfil ("iphone de Lau") con su propio dispositivo real
      respaldando de punta a punta — el perfil existe pero todavía no
      tiene carpeta destino configurada (al final).
- [ ] Pendiente anotado 2026-09-22: crear un perfil NUEVO (carpeta destino
      distinta, nunca usada antes) y verificar de punta a punta con un
      dispositivo real adicional — el usuario mencionó un iPad como
      candidato. Objetivo: confirmar que el flujo de alta de un perfil
      "desde cero" (sin ningún archivo previo, sin historial) funciona
      igual de bien que los perfiles ya establecidos probados hoy.
- [x] Detección de backup "en curso" sin actividad — aviso configurable
      (1–30 min, 10 min por defecto), **confirmado disparando
      correctamente** a los 10 minutos exactos en una corrida real. Bug
      real encontrado y corregido en el camino (el chequeo compartía
      ciclo con otras funciones de refresco y podía quedar huérfano en
      silencio). Ver secciones 5.7 y 5.9.
- [x] Arranque del servidor verificado de verdad (no solo asumido) antes
      de reportar "Escuchando" — con reintento automático (hasta 4
      intentos) para conflictos de puerto transitorios (ej. Avast
      cerrando/reabriendo el `.exe`), y mensaje de error real cuando
      falla de verdad. Ver sección 5.10.
- [x] Extensión de archivo y fecha real recuperadas por contenido cuando
      Shortcuts no las reporta (firma binaria + EXIF) — causa raíz
      atacada del lado del servidor, 38 archivos existentes corregidos
      retroactivamente. Ver sección 5.4.
- [x] Log de actividad persistido en disco con limpieza automática (~6
      meses), además del panel en vivo de la GUI. Ver sección 5.8.
- [x] Fecha real (`creation_time`) corregida dentro del propio contenedor
      de video, no solo en la carpeta/base de datos — parche binario
      quirúrgico en Python puro, validado con diff de bytes contra un
      video real antes de aplicarlo a producción. 376/387 videos
      existentes corregidos retroactivamente. Ver sección 5.11.
- [x] Preferencias configurables en la GUI (mismo estilo visual que los
      perfiles): iniciar con Windows, iniciar backup al abrir el
      programa, minutos de timeout de inactividad — con botón "Guardar"
      explícito. Ventana abre maximizada por defecto.
- [x] Instalador: instalación idempotente (borra antes de re-agregar la
      regla de Firewall, evita duplicados) y nombre fijo del acceso
      directo de desinstalación (evita duplicados por idioma del
      instalador).
- [x] Segunda copia de respaldo (USB secundaria) — diseñada e
      implementada (2026-09-21), 58/58 pruebas pasando, probada en vivo
      contra datos reales de producción, todos los bugs reales
      encontrados en el camino ya corregidos. Ver secciones 13 y 14.
      Pendiente real: completar una sincronización 100% con una USB de
      mayor capacidad, y los escenarios de prueba manual 4/6/7 (rama
      `feature/second-usb-mirror`, todavía sin mezclar a `main`).

## 13. Segunda copia de respaldo (USB secundaria) — diseño (2026-09-21)

**Motivación**: el usuario quiere que las fotos/videos respaldados no
vivan solo en una USB — poder mantener una segunda copia física,
sincronizada de forma incremental, sin depender de la nube.

### 13.1 Decisiones de diseño (resueltas en conversación con el usuario)

- **Una segunda copia por perfil**, no una combinada para todos los
  perfiles (cada perfil elige su propia carpeta/USB secundaria, igual que
  ya elige su carpeta principal).
- **La USB secundaria se conecta de vez en cuando**, no permanece
  conectada siempre — este es el estado NORMAL, nunca un error. Por lo
  tanto, la sincronización es **manual** (un botón "Sincronizar ahora"),
  no automática ni programada.
- **Se verifica por hash después de copiar cada archivo** (más lento que
  confiar solo en el tamaño, pero detecta corrupción real de la USB o de
  la copia — justo lo que esta funcionalidad existe para prevenir).
- **Ninguna USB se formatea. No se seleccionan "unidades", se seleccionan
  carpetas** — exactamente la misma premisa que ya rige la carpeta
  destino principal hoy (`Path(profile.destination_dir)` funciona igual
  para una raíz de unidad como `F:\` que para una subcarpeta como
  `F:\Respaldos\Fotos` — confirmado en `server/app.py::_engine_for`, sin
  ningún caso especial).

### 13.2 Modelo de datos: la segunda copia tiene su PROPIA base de datos real

Decisión clave (propuesta por el usuario, mejor que la idea original de
"carpeta muda sin memoria propia" que se descartó): la USB secundaria B
recibe su propia base de datos `.iphone_backup_index/index.sqlite`, con
el MISMO esquema `backed_up_files` que ya usa cualquier destino principal
— "el índice vive dentro de la carpeta destino, viaja con la unidad"
(mismo principio ya documentado en `manifest_db.py`, aplicado ahora
también a la segunda copia).

Cada vez que un archivo se copia de A a B y pasa la verificación por
hash, se inserta su fila correspondiente en la base de datos de B (mismo
`sha256`, `taken_at`, `size_bytes`; `dest_path` ajustado a la ruta dentro
de B). Esto evita guardar cualquier "bandera de ya sincronizado" en un
lugar separado que se pueda desincronizar — la verdad de "qué tiene B" es
literalmente su propia base de datos, construida solo a partir de copias
ya verificadas.

**Por qué esto resuelve gratis el escenario de "USB A se pierde, promover
B a principal"**: no hace falta ninguna función de "promoción" ni
reconciliación — confirmado leyendo `server/app.py::_engine_for` y
`forget_profile()` (ya existente, comentario textual: *"call this
whenever a profile's destination_dir changes"*): cambiar la carpeta
destino de un perfil a la de B, con el botón "Elegir carpeta..." que YA
EXISTE, hace que el sistema abra la base de datos que B ya tiene y
responda correctamente al iPhone sobre qué falta — sin ningún paso nuevo.
La antigua A, si se reconecta después, queda intacta y sin ser
modificada nunca (la sincronización siempre va en una sola dirección,
de la principal actual hacia la secundaria actual, nunca al revés).

### 13.3 Algoritmo de sincronización

1. Verificar espacio libre real en B (`shutil.disk_usage`, no un valor
   cacheado) contra el tamaño total de lo que falta copiar. Si no
   alcanza, mostrar una alerta chica no bloqueante y continuar de todas
   formas (ver 13.4).
2. Recorrer las filas de `backed_up_files` de A que NO tengan ya una fila
   equivalente (mismo `sha256`) en la base de datos de B, **ordenadas por
   `COALESCE(taken_at, received_at) DESC`** (más reciente primero —
   confirmado con datos reales de producción que así es como el propio
   Atajo entrega las fotos a A, ver sección 5.1; aquí es una decisión
   deliberada de prioridad, no una necesidad técnica como en el Atajo).
   Prioriza lo más reciente/valioso si la sincronización se corta o si no
   alcanza el espacio.
3. Para cada archivo: copiar los bytes a la ruta equivalente dentro de B,
   releer el archivo copiado y calcular su hash, compararlo contra el
   `sha256` de A. Si coincide, insertar la fila en la base de datos de B.
   Si no coincide, no registrar nada y reintentar en la siguiente
   sincronización.
4. Si un archivo específico falla por espacio agotado a mitad de copiar,
   descartar el archivo parcial (nunca lo deja a medias ni lo registra).

**Resiliencia sin guardar estado adicional**: como cada fila de B solo se
escribe DESPUÉS de copiar y verificar con éxito, cualquier interrupción
(desconexión física, cierre de la app, apagón, disco lleno) dejando el
proceso a mitad de camino nunca deja a B en un estado falso — la
siguiente sincronización simplemente retoma lo que falte, sin importar en
qué punto exacto se cortó. Única ventana conocida y aceptada: si la app
se cierra justo entre que termina de copiar y de verificar un archivo
específico, ese archivo podría quedar sin verificar (tamaño correcto,
pero sin la confirmación de hash) — mitigado por una acción manual aparte
"Verificar todo" (re-hashea ambas copias completas), no parte del flujo
normal.

### 13.4 Manejo de espacio en disco

- **USB A (principal) sin espacio suficiente para toda la biblioteca**:
  ya es el comportamiento actual, sin cambios — el sistema nunca
  precalcula el total, simplemente intenta archivo por archivo (ver
  sección 5.13 para el bug relacionado, ya corregido: antes fallaba en
  silencio cuando el disco se llenaba de verdad a mitad de un archivo,
  ahora responde con un error claro y reintentable).
- **USB B (segunda copia) con menos espacio que lo necesario**: alerta
  chica no bloqueante al iniciar la sincronización, pero el proceso
  continúa copiando en orden de prioridad (13.3) hasta llenarse. Lo que
  no alcanzó a copiarse queda pendiente para la próxima vez que haya más
  espacio disponible (nueva USB más grande, o se libera espacio).

### 13.5 Interfaz — dentro de la tarjeta de cada perfil, en "⚙ Configuración"

Sin cambios en la pantalla Principal (el monitoreo en vivo del respaldo
del iPhone). Dentro de `ProfileManageRow` (`gui/main_window.py`), debajo
de los botones ya existentes (Elegir carpeta / Historial USB / Copiar
token / Renombrar / Renovar token / Eliminar), una sub-sección opcional:

- **Sin configurar**: link discreto "+ Configurar segunda copia
  (opcional)" — no le agrega ruido a quien no usa la función.
- **Configurada, USB conectada**: "🔄 Segunda copia: [ruta] — [N]/[total]
  archivos · última sync: [fecha]" + botón "🔄 Sincronizar ahora" + botón
  "⚙ Cambiar".
- **Configurada, USB desconectada**: mismo texto, botón de sincronizar
  inactivo con la leyenda "no conectada" — nunca se muestra como un
  error, es el estado normal de esta función.
- **Sincronizando**: barra de progreso en vivo "Sincronizando... X / Y
  archivos", mismo patrón visual que "Iniciando backup..." ya usado para
  el arranque del servidor.

**Sin ningún botón nuevo de "promover a principal"** — ese cambio de rol
usa el botón "Elegir carpeta..." que ya existe (ver 13.2).

### 13.6 Validaciones nuevas necesarias

- Bloquear seleccionar la MISMA carpeta como destino principal y como
  segunda copia del mismo perfil (evitaría "sincronizar una carpeta
  consigo misma").

### 13.7 Plan de pruebas

Ver la lista completa acordada con el usuario (categorías: camino feliz,
desconexión/reconexión, verificación e integridad, espacio en disco,
cierre abrupto de la app, cambio de rol A↔B, validaciones de
configuración, concurrencia) — 24 escenarios en total, todos simulables
sin un dispositivo iPhone real (solo con `tmp_path`/`monkeypatch`, mismo
patrón que sección 5.13).

### 13.8 Trabajo relacionado ya completado antes de empezar

- **Sección 5.13**: el bug de disco lleno en la USB A fallando en
  silencio — corregido y probado ANTES de empezar esta funcionalidad,
  porque el mismo patrón de error aplica igual de fuerte a la segunda
  copia.

### 13.9 Implementado (2026-09-21) — estado real

Construido en la rama `feature/second-usb-mirror`: `server/mirror.py`
(motor de sincronización), campos/métodos nuevos en `server/profiles.py`
y `server/manifest_db.py`, la sub-sección nueva en `ProfileManageRow`
(`gui/main_window.py`), ~35 claves nuevas en `gui/i18n.py`. 56/56 pruebas
pasando (`tests/test_mirror.py`, `tests/test_profiles.py`).

**Bug real encontrado durante la prueba en vivo con datos de producción**
(pregunta directa del usuario: "¿el programa libera la USB o Windows no
me dejará sacarla?"): mientras la sincronización corre, el programa
mantiene abierta una conexión a la base de datos dentro de la USB
secundaria — Windows correctamente bloquea la expulsión seguro mientras
tanto. Pero si se saca la USB a la fuerza (sin expulsar) a mitad de
copiar un archivo, la excepción podía escaparse del hilo en segundo plano
sin ningún manejo, dejando el botón trabado en "Sincronizando..." para
siempre, sin mensaje de error — mismo patrón de falla silenciosa ya
corregido varias veces esta semana (ver AGENTS.md lección 11).
**Corregido**: `sync_mirror()` ahora nunca lanza una excepción sin
controlar — cualquier falla (disco lleno, unidad desconectada, cualquier
otra cosa inesperada) vuelve como un campo del resultado
(`stopped_with_error`, `fatal_error`), con limpieza segura en cada paso
(incluyendo que el propio intento de borrar un archivo parcial pueda
fallar si la unidad ya no está). Nueva prueba:
`test_drive_disconnected_mid_copy_reports_error_not_a_crash`.

**Segundo bug real encontrado, esta vez en vivo (captura de pantalla del
usuario, 2026-09-21)**: la primera sincronización real se hizo contra una
USB de prueba de solo 4 GB (mucho más chica que los ~16 GB reales de la
biblioteca) — validó sin querer el escenario de "espacio insuficiente"
del punto 13.4: copió 128 archivos (2.25 GB) priorizando lo más
reciente, la verificación por hash atrapó 7 copias corruptas cerca del
límite de espacio (justo lo que existe para prevenir), y se detuvo
limpio. Pero mostrar el aviso de "poco espacio" Y el de "se detuvo con
error" **uno después del otro** (ambas condiciones dieron verdadero a la
vez) apiló dos diálogos modales seguidos, y eso disparó un bug real y
preexistente en `gui/dialogs.py` (`_PunkDialog`, usado por TODOS los
diálogos de la app, no solo los nuevos): el lambda del bind de `<Escape>`
exigía el objeto de evento como argumento obligatorio
(`lambda _e: self._cancel()`), y algo en la secuencia de apilar dos
diálogos lo invocó sin argumento — `TypeError: ...<lambda>() missing 1
required positional argument: '_e'`. **Corregido en dos frentes**: (1)
el lambda ahora tiene `_e=None` por defecto (mismo patrón defensivo que
ya usaban `_confirm`/`_cancel` en `ask_input`, aplicado aquí también,
beneficia a TODA la app, no solo a la segunda copia); (2)
`_on_mirror_sync_done` ahora usa `elif` en vez de dos `if` separados, así
nunca apila dos diálogos para el mismo evento de sincronización — mejor
UX de todas formas, no solo evita el bug. 56/56 pruebas pasando después
del arreglo.

**Hueco de observabilidad encontrado en la misma sesión de pruebas**: el
mensaje de error real de `stopped_with_error` solo se mostraba en el
diálogo emergente (transitorio, fácil de perder) — no quedaba guardado
en el log de actividad. Esto llevó a una conclusión apresurada
("se llenó la USB") sin verificar el texto real del error contra el
espacio libre real (que resultó ser 900 MB, no cero) — un recordatorio de
seguir la práctica ya establecida del proyecto de verificar con evidencia
real antes de explicarle algo al usuario. **Corregido**: el mensaje real
del error ahora también se escribe en el log de actividad
(`_on_mirror_sync_done`), no solo en el diálogo.

**Botón "Detener sincronización" (pedido explícito del usuario,
2026-09-21)** — para poder sacar la USB secundaria sin esperar a que
termine una sincronización larga. Mismo patrón que el botón principal
"Iniciar/Detener backup": un solo botón que cambia de función según el
estado (`_toggle_server`/`_sync_profile_mirror`), no un botón aparte.

- `server/mirror.py`: `sync_mirror()` gana un parámetro
  `cancel_event: Optional[threading.Event]`, revisado solo **entre**
  archivos (nunca a mitad de copiar o verificar uno) — así lo que ya se
  copió y verificó queda válido, y la USB queda segura para expulsar
  apenas termina de detenerse. Nuevo campo `MirrorSyncResult.cancelled`
  (no es un error, es un resultado normal pedido por el usuario). Nueva
  prueba: `test_cancelling_mid_sync_stops_cleanly_and_resumes_later`
  (cancela a mitad, confirma que solo lo copiado hasta ahí quedó
  registrado, y que una sincronización posterior retoma el resto).
- `gui/main_window.py`: `_sync_profile_mirror` ahora es un toggle — si ya
  hay una sincronización corriendo para ese perfil (rastreado en
  `self._mirror_cancel_events`, un `threading.Event` por perfil), el
  mismo botón la cancela en vez de iniciar una nueva.
  `ProfileManageRow.set_syncing()` cambia el texto/color del botón
  ("🔄 Sincronizar ahora" ↔ "⏹ Detener") en vez de desactivarlo — tiene
  que seguir siendo clickeable para poder cancelar. El botón "Quitar" sí
  se desactiva mientras sincroniza (quitar la configuración a mitad de
  una sincronización activa no tiene sentido).
- Verificado con una prueba de humo real de los widgets (no solo que
  compila): el botón muestra "⏹ Detener", sigue clickeable, y un cambio
  de idioma a mitad de sincronización no lo revierte a "Sincronizar".
  57/57 pruebas pasando.

**Espacio usado/disponible de la segunda copia (pedido del usuario,
2026-09-21) — HECHO**: `get_mirror_status()` ahora también devuelve
`free_bytes`/`total_bytes` (vía `shutil.disk_usage()`, mismo dato que ya
usaba `sync_mirror()` para la alerta de espacio insuficiente, ahora
también expuesto para mostrar). El estado normal de la tarjeta del perfil
ahora muestra "{N} archivos copiados · {libres} libres de {total}",
mismo formato que ya usa la carpeta principal (`free_of_total`). Prueba
actualizada. **Pendiente, más menor**: mostrar ese mismo dato TAMBIÉN
dentro del texto "Sincronizando... X/Y archivos" mientras corre (hoy solo
se ve en el estado de reposo/conectado, no durante la sincronización
activa) — agregar `free`/`total_space` a `mirror_syncing_progress`.

**Contraste de botones (pedido del usuario, 2026-09-21, con captura de
pantalla) — HECHO**: varios botones con fondo rosa (`ACCENT`) o rojo
(`RED`) — "Elegir carpeta...", "Eliminar", "+ Agregar perfil",
"Sincronizar ahora"/"⏹ Detener" — nunca definían `text_color` en su
construcción, cayendo en el color de texto por defecto de CustomTkinter,
con mal contraste sobre esos fondos brillantes. La app YA tenía la
solución correcta en otros botones del mismo archivo (`ACCENT_INK =
"#1a0308"` para fondo rosa, `TEXT_MAIN` para fondo rojo — el botón
principal "Iniciar/Detener backup" ya lo hacía bien) — simplemente nunca
se aplicó a estos otros botones. Corregidos los 6 casos encontrados
(`btn_choose_dest`, `btn_delete`, `btn_sync_mirror` en sus dos estados,
`add_profile_btn`). Verificado que `.configure()` sin `text_color` no
resetea el que ya estaba puesto (comprobado con un script directo contra
CustomTkinter) — así que los botones que sí lo tenían desde su
construcción (`save_btn`, navegación) no necesitaban tocarse.

**Contador de progreso reiniciaba en "1" en cada corrida nueva (pedido del
usuario, 2026-09-21) — HECHO**: con 128 archivos ya copiados y
verificados, la siguiente corrida mostraba "1/6885" — técnicamente
correcto (1 de los que faltan), pero se veía exactamente como si hubiera
perdido los 128 anteriores. `progress_callback` ahora reporta un conteo
**acumulado** contra el total real de la segunda copia
(`baseline + i` de `baseline + len(pending)`, donde `baseline` es cuántos
ya tenía el espejo antes de esta corrida) — con 128 ya copiados y 1
pendiente, ahora muestra "129/129", nunca "1/1". Nueva prueba:
`test_progress_is_cumulative_not_reset_to_one_on_a_resumed_sync`. 58/58
pruebas pasando.

**Espacio libre/total también durante la sincronización activa (último
pendiente, cerrado 2026-09-21)**: el estado de reposo ya mostraba
"{free} libres de {total}" desde el arreglo anterior, pero el texto
"Sincronizando... X/Y archivos" en vivo todavía no lo mostraba. Cerrado:
`_on_mirror_progress` en `gui/main_window.py` ahora calcula
`shutil.disk_usage(profile.mirror_dir)` en cada actualización de
progreso (barato, sin efectos secundarios) y se lo pasa a
`set_sync_progress`, que arma el texto completo
"Sincronizando... X/Y archivos · {free} libres de {total}". Con esto
queda completo el pedido original del usuario sobre visibilidad de
espacio en la segunda copia — tanto en reposo como mientras corre.

## 14. Estado final de la implementación de la segunda copia (2026-09-21)

Diseño (sección 13) implementado por completo, probado (pytest +
pruebas de humo de widgets + prueba en vivo contra ~7,200 archivos
reales de producción) y con todos los bugs reales encontrados durante
las pruebas ya corregidos:

- Motor de sincronización (`server/mirror.py`): copia newest-first,
  verifica por hash, propia base de datos por segunda copia, nunca
  lanza una excepción sin controlar, botón de cancelar (`cancel_event`),
  progreso acumulado (no se reinicia en "1" al retomar).
- GUI (`gui/main_window.py`, `gui/i18n.py`): sub-sección en la tarjeta
  de cada perfil con los 4 estados de diseño, botón que alterna
  Sincronizar/Detener, espacio libre/total visible tanto en reposo como
  durante la sincronización, contraste de texto corregido en todos los
  botones con fondo de color (rosa/rojo) que lo tenían mal desde antes
  de esta funcionalidad.
- Bug preexistente en `gui/dialogs.py` (`_PunkDialog`) corregido —
  beneficia a toda la app, no solo a esta funcionalidad.
- 58/58 pruebas automatizadas pasando. Validado en producción real con
  el perfil "iphone de Hes" (D: → E:, USB de prueba de 4 GB que reveló
  el escenario de espacio insuficiente sin que se hiciera a propósito).

**Pendiente real, no técnico**: probar con una segunda USB de mayor
capacidad para completar una sincronización 100% completa de los ~16 GB
reales (la USB de 4 GB usada en las pruebas nunca alcanzó a terminar), y
el escenario manual de desconexión física real (sacar la USB a mitad de
una sincronización) que sigue pendiente de ejecutar en vivo.

### 14.6 Prueba en vivo del cambio de rol A↔B, con USB sana (2026-09-22)

Completada de punta a punta, con datos reales, USB por USB, guiada por
el usuario:

1. USB E: (sana, 7.5 GB, vacía) configurada primero como segunda copia
   de D: — sincronización manual copió 121 archivos antes de detenerse
   manualmente; confirma que "Detener" deja el progreso consistente
   (retomable, sin corrupción).
2. **Cambio de rol**: segunda copia quitada, E: promovida a destino
   principal, D: reconfigurada como nueva segunda copia — sin ningún
   botón ni código de "promoción" (por diseño, ver §13.2). Backup real
   desde el iPhone subió ~10 archivos nuevos directo a E: sin errores.
   Sincronización E:→D: salió **0 nuevos, 0 fallidos** — confirma que
   D: (al haber sido la principal original) ya reconocía correctamente
   todo el contenido presente en E:, sin re-copiar ni duplicar nada.
3. **Vuelta atrás**: D: restaurada como principal, E: reconfigurada como
   segunda copia de nuevo — mismo patrón sin errores. Sincronización
   D:→E: y backup real desde el iPhone corriendo en simultáneo
   (validación adicional, no buscada a propósito, de que la
   sincronización de la segunda copia no interfiere con una corrida
   real en curso — el mismo invariante del bug de §14.2).

Con esto, los escenarios manuales de validación "misma carpeta" (ya
cubierto también por `set_mirror_destination`'s guard) y cambio de rol
A↔B quedan confirmados con datos reales, no solo con tests sintéticos.

### 14.1 Velocidad de copia de la segunda copia, medida en el ambiente real (2026-09-22)

Petición del usuario: documentar la velocidad de copia de la segunda
copia, como parte de la misma evaluación de velocidad que ya existe para
el respaldo principal por WiFi (sección 5.12).

**Metodología** (idéntica a la de la sección 5.12, aplicada esta vez a la
base de datos propia de la segunda copia): consulta solo-lectura
(`file:{path}?mode=ro`) contra
`E:\Backup Fotos y Videos\.iphone_backup_index\index.sqlite` de una
corrida real de producción (instalador v1.7.0 ya instalado, perfil real
"iphone de Hes") — 607 filas totales, mediana del intervalo entre
`received_at` consecutivos por extensión.

**Resultado**: JPEG ~1.35s, HEIC ~2.24s, PNG ~1.70s, MOV ~8.27s por
archivo — más rápido que la subida por WiFi en general (sobre todo
videos, ~8s local contra ~17-19s por WiFi), pero casi sin diferencia en
JPEG chicos (mismo patrón: el costo fijo por archivo domina en archivos
chicos, no la transferencia en sí). Publicado en ambos manuales de
troubleshooting (EN/ES), sección nueva "¿Qué tan rápido es la
sincronización de la segunda copia (espejo)?", justo después de la
sección de velocidad por WiFi ya existente.

**Salvedad honesta incluida en la documentación**: la medición se hizo
sobre la USB de prueba de 4 GB, casi llena (quedaban 0.25 GB libres al
momento de medir) — esta misma corrida terminó realmente sin espacio
(`[WinError 112]`), con una tasa de corrupción detectada por la
verificación mucho más alta que la vez anterior (58 de 289 archivos
fallaron la verificación, contra 7 la primera vez que se probó la misma
unidad con más espacio libre) — evidencia real de que una unidad flash
casi llena se comporta peor, no solo más lento. Comparé la primera mitad
de la corrida contra la segunda mitad y NO hay una degradación gradual
clara (1.74s vs 1.65s de mediana) — el fallo fue un límite duro al
final, no una lenta degradación progresiva. Los números de esta tabla
deben leerse como "lo que se puede esperar de una USB chica y casi
llena", no como el rendimiento típico de una unidad sana con espacio de
sobra.

**Analizado y descartado a propósito**: acelerar el proceso quitando el
paso de re-leer y verificar por hash después de copiar (eliminaría
exactamente la comprobación que atrapó las 7 y 58 copias corruptas reales
de arriba) — el usuario pidió explícitamente "que siga siendo preciso",
así que no se implementó. La conclusión honesta es que el cuello de
botella real es la propia unidad USB (pequeña, casi llena), no el
algoritmo — una USB más grande y con más espacio libre es la mejora real,
no un cambio de código.

### 14.2 Bug real y serio: sincronizar la segunda copia podía "cortar" en
### silencio un respaldo real que seguía en curso (2026-09-22)

Encontrado en producción real, reportado por el usuario ("acabo de
iniciar un nuevo backup desde el iphone pero no veo que avance"),
investigado con evidencia real (log de actividad + consulta solo-lectura
a la base de datos), no supuesto.

**Qué pasó**: una corrida real (`run_id 45a3b003...`) empezó a las
08:42:24 desde el iPhone. Once segundos después, el botón de
sincronizar la segunda copia abrió su propia conexión
`ManifestDB(primary_root)` para leer el índice de `D:` — y esa apertura
disparó el mecanismo de "reap" (ver sección 6/AGENTS.md punto 10),
cerrando `finished_at` de esa corrida como si fuera una corrida
abandonada de una sesión anterior. **La causa raíz de fondo**: el
supuesto original del reap ("si `finished_at` es NULL, es porque el
proceso anterior se cerró a medias — `RunID` nunca sobrevive a un
proceso") solo es cierto para la PRIMERA `ManifestDB` que se abre sobre
un `dest_root` en un proceso — no contempla una SEGUNDA apertura, del
mismo proceso todavía corriendo, mientras una corrida real sigue en
curso de verdad. Justo el escenario que la funcionalidad de segunda
copia introdujo por primera vez (antes de esto, solo existía una
`ManifestDB` cacheada por perfil, nunca una segunda).

**Consecuencia real verificada**: los archivos SÍ siguieron subiendo
correctamente después del reap erróneo (`bump_run`/`record_file` no
revisan `finished_at`, confirmado con una consulta real: llegaron
archivos nuevos hasta las 08:43:43) — pero la GUI dejó de mostrar la
corrida como "en curso", haciendo que pareciera detenida aunque seguía
funcionando por debajo. Sin pérdida de datos ni de archivos, pero sí un
hueco real de confianza en lo que el usuario ve en pantalla.

**Corregido**: `ManifestDB.__init__` gana un parámetro
`reap_dangling_runs: bool = True` — `_sync_profile_mirror` en
`gui/main_window.py` ahora abre su `ManifestDB(primary_root)` con
`reap_dangling_runs=False`, ya que es exactamente el caso de "segunda
apertura sobre un destino que el proceso ya puede estar usando
activamente". Nueva prueba:
`test_reap_dangling_runs_false_never_touches_a_genuinely_live_run` en
`tests/test_backup_engine.py`. 59/59 pruebas pasando. Documentado como
lección nueva en AGENTS.md punto 16, con una regla explícita para
cualquier código futuro que abra una `ManifestDB` sobre un destino que
el servidor ya pueda tener abierto: preguntar primero si una corrida
real podría estar en curso, y si la respuesta es sí, usar
`reap_dangling_runs=False`.

### 14.3 Ruido real en el log para perfiles desactivados/sin configurar, y versión visible en la GUI (2026-09-22)

Dos pedidos del usuario, ambos cerrados:

**1. `_check_idle_backups()` (`gui/main_window.py`) revisaba TODOS los
perfiles sin filtrar**, así que un perfil desactivado (ej. "iphone de
Lau", pausado y sin carpeta destino) siempre lanzaba una excepción real
(`get_status_for_profile` → 403/409) que se registraba como un
traceback completo en el log — una vez por cada reinicio de la app (no
en bucle, gracias al arreglo previo de "una vez por racha de error", pero
igual ruido real para algo que es un estado completamente normal, no un
error). **Corregido**: el loop ahora salta por completo cualquier perfil
desactivado o sin carpeta destino configurada, sin llamar nunca a
`get_status_for_profile` para esos casos — cero excepción, cero log.
Verificado con una prueba de humo real (perfil desactivado + perfil sin
configurar, cero líneas de error registradas).

**2. No había forma de ver qué versión de la app estaba instalada.**
Nuevo `server/version.py` (`APP_VERSION`, única fuente de verdad para el
lado Python — el instalador de Inno Setup sigue con su propio
`MyAppVersion` aparte, con un comentario cruzado en ambos archivos
recordando mantenerlos sincronizados, ya que ISPP no puede leer el
`.py` directamente). Se muestra en el título de la ventana
("PunkBackup — v1.7.2") y en la esquina superior derecha de la tarjeta
de idioma en "⚙ Configuración" ("PunkBackup v1.7.2") — visible sin tener
que buscarlo, útil para comparar contra el manual o reportar un problema.

Ambos verificados con una prueba de humo real (`MainWindow` real,
`ProfileStore` real, sin mock) antes de darlos por buenos. Subida a
**v1.7.2** (incluye también el arreglo del reap de la sección 14.2,
nunca llegó a instalarse como v1.7.1 por separado).

### 14.4 Orden de los mensajes al arrancar: "A darle" debe ser el último (2026-09-22)

El usuario reportó (con una captura real) que el aviso de "!! Run ...
was left running by a previous session..." aparecía DESPUÉS de "Servidor
iniciado. A darle." — confirmado que es un caso legítimo (la corrida
anterior de verdad nunca recibió `/run/finish`, no relacionado con el bug
de la sección 14.2), pero el orden se veía raro: un mensaje que parece
una advertencia apareciendo justo después de que todo ya decía estar
listo. **Causa**: el reap se dispara de forma perezosa, la primera vez
que se abre la `ManifestDB` de un perfil — que en la práctica pasaba en
el primer tick del loop de chequeo de inactividad, DESPUÉS de que
`_start_server()` ya había registrado "Iniciando backup..." y "Servidor
iniciado".

**Corregido**: `_start_server()` ahora toca la `ManifestDB` de cada
perfil (llamando `get_status_for_profile`) de forma síncrona, justo
después de `app_module.configure(...)` y ANTES de registrar cualquier
mensaje de esta sesión — así, si hay algo que reapear de la sesión
anterior, queda como lo último de la sesión vieja, no como lo primero
(ni lo último) de la nueva. Orden final: `[reap si aplica]` →
"Iniciando backup..." → "Servidor iniciado. A darle." — "A darle" queda
garantizado como el último mensaje de un arranque normal. Verificado con
una prueba de humo real (corrida abandonada real en el índice + llamada
real a `_start_server()` + inspección del orden real de la cola de
mensajes). 59/59 pruebas pasando.

### 14.5 Disclaimer nuevo sobre el comportamiento real de Avast (2026-09-22)

Pedido explícito del usuario, con conocimiento directo de cómo se
comporta Avast con PunkBackup en la práctica (no solo "a veces cierra la
app", sino el mecanismo exacto): Avast deja abrir la app normal, la
escanea **mientras ya está corriendo** (por eso los primeros segundos se
ven bien), y recién después la cierra y la vuelve a abrir sola, unos
**10 segundos** después del primer arranque. Esto ya estaba documentado
de forma genérica ("Avast puede cerrar la app"), pero faltaba la
consecuencia concreta y accionable: **si el usuario inicia un backup
desde el iPhone justo en esa ventana de ~10 segundos, esa corrida
específica se corta en el momento exacto en que Avast cierra la app** —
no se pierde nada de lo ya subido, pero esa corrida puntual no termina
sola y hay que volver a iniciarla desde el teléfono.

**Documentado en**: la sección "⚠ Importante: esta app no tiene firma
digital de pago" del Manual de instalación (EN/ES, la explicación
completa con el mecanismo y la consecuencia), y un párrafo corto y
accionable en la sección correspondiente del Manual de solución de
problemas (EN/ES) que remite a la explicación completa. Se aclara que el
reintento automático de arranque del servidor (ya existente, sección 5.10
de este mismo documento) se encarga de que el servidor vuelva a quedar
bien después del cierre — lo nuevo que se documenta es específicamente
qué pasa con una corrida del Atajo que estaba activa en ese momento
preciso, que es un caso distinto.

## 15. Cada línea del log ahora dice a qué perfil pertenece (2026-09-22, v1.7.6)

Pedido del usuario: con más de un perfil/dispositivo respaldando, poder
saber de un vistazo a cuál pertenece cada línea del log sin tener que
adivinar solo por el texto del mensaje. Formato acordado: **fecha (ya
existía) → perfil → mensaje (ya existía, sin tocar el texto)**.

### 15.1 Diseño

Dos caminos de logging distintos alimentan el mismo log en pantalla y el
mismo `activity.log` en disco, y ambos necesitaban ganar el campo
"perfil" sin romper ninguno de los dos:

1. **Mensajes del servidor** (`server/storage.py`, `server/app.py`,
   `server/manifest_db.py`) — pasan por el logger real de Python
   (`logging.getLogger("backup_engine")`), que la GUI conecta a la cola
   en pantalla vía un `QueueHandler`.
2. **Mensajes propios de la GUI** (`gui/main_window.py::_log_local`) —
   "Servidor iniciado", los mensajes de la segunda copia, el aviso de
   inactividad, etc. — nunca pasan por el logger de Python, van directo
   a la misma cola como texto plano.

**Servidor**: `ManifestDB` y `BackupEngine` ganan un `profile_label: str`
(default `"-"`, seguro para cualquier construcción sin perfil conocido,
ej. los tests) y un `self.logger = logging.LoggerAdapter(logger,
{"profile": profile_label})` — cada instancia ya sabe de qué perfil es,
así que sus propios `self.logger.info/warning/error(...)` etiquetan el
`LogRecord` automáticamente, sin tener que cambiar el texto de ningún
mensaje existente. `BackupEngine` reutiliza el `profile_label` de su
propio `self.db` (una sola fuente de verdad, no un segundo parámetro
redundante). `server/app.py`'s `_engine_for()` es el único lugar que
construye ambos — ahí es donde se pasa `profile.name` una sola vez.
`server/mirror.py::sync_mirror()` gana el mismo parámetro opcional, para
la base de datos propia de la segunda copia (aunque en la práctica casi
nunca emite nada por sí misma).

Se aprovechó el cambio para **quitar el nombre del perfil que ya venía
embebido a mano dentro del texto** de "=== Backup run started/finished
==="  en `app.py` (ahora sería redundante con la nueva columna
estructurada) — verificado que ningún manual ni prueba dependía de ese
texto exacto. Los mensajes de la segunda copia (`gui/i18n.py`) SÍ siguen
trayendo el nombre embebido en el texto (ej. `Sincronizando segunda
copia de "iphone de Hes"...`) — esos NO se tocaron a propósito, porque el
Manual de solución de problemas los cita textualmente; queda una
redundancia cosmética menor (el nombre aparece dos veces en esas líneas
específicas), aceptada conscientemente para no arriesgar los manuales.

**GUI**: `_log_local(message, profile=None)` ahora mete a la cola una
tupla `(profile_label, message)` en vez de solo el texto. `_drain_log_queue`
distingue tres formas de lo que puede salir de la cola (`LogRecord` real,
tupla de `_log_local`, o string suelto como último recurso) y construye
`f"{fecha} > {perfil} > {mensaje}"` para pantalla, y pasa
`extra={"profile": perfil}` al logger de archivo (cuyo `Formatter` ganó
`%(profile)s`). Cualquier línea sin perfil conocido (arranque/apagado del
servidor, errores de los loops internos, la excepción no controlada de
Tkinter) muestra `-` — nunca revienta por un atributo faltante, gracias a
`getattr(record, "profile", "-")`.

### 15.2 Pruebas y documentación

3 pruebas nuevas (70/70 pasando): que un `ManifestDB`/`BackupEngine`
etiqueta sus propios `LogRecord`s con el `profile_label` correcto (vía
`caplog`), que uno sin `profile_label` explícito cae a `"-"` sin romper
nada, y una prueba de extremo a extremo contra la API real con DOS
perfiles subiendo a la vez confirmando que sus líneas de log nunca se
mezclan (cada una lleva el nombre de SU propio perfil, no el del otro).

Documentado en el Manual de Uso (EN/ES), sección "▼ Mostrar actividad" /
"▼ Show activity", donde ya se explicaba el formato de fecha/hora —
ahora también explica el nuevo campo de perfil. PDFs reconstruidos.

Versión: **v1.7.6** (bump pendiente de build+instalación, a la espera de
confirmación del usuario antes de aplicar).
