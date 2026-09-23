# PunkBackup — Manual de uso de la aplicación de escritorio

Esta guía explica qué hace cada pantalla y cada botón de la app. Para
instalarla por primera vez, usa el **Manual de instalación**; para
problemas, el **Manual de solución de problemas**.

## La ventana tiene 2 pantallas

- **Principal**: encender/apagar el backup, ver a qué dirección deben
  conectarse tus dispositivos, y el estado de cada perfil.
- **⚙ Configuración**: cambiar el idioma de la app, y crear/administrar
  cada persona o dispositivo (perfiles).

Se cambia entre ellas con los dos botones de arriba, justo debajo del
nombre de la app.

La ventana se abre **maximizada** por defecto cada vez — puedes
restaurarla/achicarla como cualquier ventana de Windows si prefieres
tenerla más pequeña; eso es un control normal de Windows, PunkBackup no
recuerda ese tamaño entre aperturas.

---

## Pantalla "⚙ Configuración" → Idioma

Arriba de todo en Configuración hay dos botones: **Español** / **English**.
Tócalo y **toda la app cambia de idioma al instante** — botones, títulos,
mensajes, todo — sin cerrar ni reiniciar nada. Tu elección se recuerda la
próxima vez que abras la app.

En la esquina superior derecha de esa misma tarjeta, y también en la
barra de título de la ventana, vas a ver qué versión tienes instalada
(ej. "PunkBackup v1.7.3") — útil para comparar contra este manual o para
reportar un problema.

---

## Pantalla "⚙ Configuración" → Preferencias

Justo debajo de Idioma, tres tarjetas — mismo estilo de interruptor
on/off que el switch Activo/Pausado de cada perfil en la pantalla
Principal. Cada cambio aquí se aplica de inmediato, sin reiniciar.

- **Iniciar PunkBackup con Windows**: agrega (o quita) a PunkBackup de los
  programas de inicio de Windows, para que se abra solo al iniciar
  sesión — sin tener que buscar el ícono del Escritorio cada vez.
  **Desactivado por defecto.**
- **Iniciar backup al abrir el programa**: apenas termina de abrirse la
  app, hace automáticamente lo mismo que si tú mismo hicieras clic en
  **"🤘 Iniciar backup"** — incluyendo los mismos avisos si todavía no
  hay ningún perfil configurado, o ninguno tiene carpeta destino. Combina
  esto con el interruptor de arriba para que la PC quede escuchando a tu
  iPhone completamente sola después de reiniciar. **Desactivado por
  defecto.**
- **Minutos sin actividad para avisar que el backup se detuvo**: un
  campo numérico (1 a 30 minutos) que controla el aviso de inactividad
  descrito arriba en "▼ Mostrar actividad". Escribe un valor nuevo y haz
  clic en **"Guardar"** (o presiona Enter) — el botón solo se activa
  mientras hay un cambio válido sin guardar, y muestra brevemente "✓
  Guardado" una vez aplicado, así siempre queda claro si tu cambio
  realmente se aplicó. **5 minutos por defecto.**

---

## Pantalla "Principal"

### Botón "🤘 Iniciar backup" / "Detener backup"

Es el interruptor general del servidor — controla si la PC está
**escuchando** en la red o no.

- **Apagado** (texto "Iniciar backup", verde): tu PC no acepta conexiones
  de ningún iPhone/iPad. Es el estado por defecto — la app nunca se
  enciende sola, ni siquiera si la dejas abierta.
- **Encendido** (texto "Detener backup", rojo): tu PC ya puede recibir
  fotos y videos de cualquier perfil que tengas **Activo**.

Justo al lado, el texto **"Estado: ..."** confirma en qué modo está:
`Detenido`, `Iniciando backup...` (brevemente, justo después de hacer
clic — normalmente un par de segundos, a veces un poco más si el puerto
tarda en liberarse, por ejemplo justo después de que un antivirus cierre
y reabra la app), o `Escuchando en el puerto 8787`. Si de verdad falla al
iniciar (el puerto sigue sin liberarse), te sale una ventana de error
explicando por qué, en vez de un falso "Escuchando".

> No necesitas "seleccionar" qué perfil va a respaldar — mientras el
> servidor esté encendido, **cualquier perfil Activo puede subir en
> cualquier momento**, incluso varios al mismo tiempo.

### "Dirección del servidor"

Dos datos que vas a necesitar **una sola vez**, al configurar el Atajo de
cada iPhone/iPad (no cambian entre perfiles):

- **Dirección**: `http://NOMBRE-DE-TU-PC.local:8787` — úsala primero.
- **IP alternativa**: una dirección numérica de respaldo, por si la
  anterior no responde desde algún iPhone en particular.

### "Perfiles conectados a este backup"

Una tarjeta por cada perfil que hayas creado, con:

- **Nombre** del perfil.
- **Total en destino**: cuántos archivos hay en total en la carpeta de ese
  perfil (todo lo respaldado hasta ahora, de todas las corridas), y la
  fecha de la última copia.
- **Última corrida**: cuántos archivos se guardaron específicamente en la
  corrida más reciente del Atajo (nuevos vs. los que ya existían) — si el
  Atajo sigue corriendo en ese momento, se marca "(en curso...)".
- **Carpeta**: a dónde está guardando sus archivos.
- **USB**: si su carpeta está en una unidad extraíble, la etiqueta y el
  espacio libre de ese disco.
- Un interruptor **Activo / Pausado** — ver más abajo.

#### El interruptor Activo / Pausado

Es distinto del botón grande de arriba. El de arriba enciende/apaga **toda
la PC**; este interruptor bloquea o permite **un perfil específico**, sin
tocar a los demás.

- **Activo**: ese dispositivo puede subir fotos normalmente.
- **Pausado**: ese dispositivo específico no puede subir nada (el servidor
  le responde "perfil pausado"), aunque el resto siga funcionando. Útil
  para, por ejemplo, cortarle el acceso a un dispositivo de visita sin
  borrar su historial.

Pausar/reactivar **no borra nada** — es totalmente reversible.

### "Última copia (todos los perfiles) / Total archivos"

Un resumen general sumando todos los perfiles — para ver de un vistazo si
algo se respaldó recientemente, sin entrar a revisar perfil por perfil.

### "▼ Mostrar actividad"

Está **visible por defecto** — colápsalo con el mismo botón si quieres
una pantalla más limpia. Muestra un registro en vivo (estilo terminal,
texto verde) de cada archivo que va llegando: nuevo, ya existía, o
conflicto. Sirve para confirmar que algo está pasando en tiempo real
mientras corres un Atajo desde el iPhone. También marca claramente cuándo
**inicia** y cuándo **termina** cada corrida (con el resumen final:
nuevos/ya existían/conflictos/errores), así que puedes ver de un vistazo
dónde empieza y termina cada backup en el historial del log.

Cada línea lleva la **fecha y hora local** en que ocurrió
(`DD-MM-AAAA HH:MM:SS`), seguida de **a qué perfil/dispositivo
corresponde** (ej. `iPhone de Hesner`, `Ipad`, o `-` para una línea que no
es de ningún perfil en particular, como cuando arranca o se detiene el
servidor) — así, con más de un dispositivo respaldando, puedes saber de
un vistazo a cuál pertenece cada línea, sin tener que adivinar solo por
el mensaje. De cualquier forma, un log que abarca varios días (si dejas
la app abierta) se sigue leyendo con claridad — puedes saber exactamente
cuándo corrió cada backup, no solo el orden en que aparecen.

Si una corrida se queda "en curso" sin recibir ningún archivo nuevo
durante un rato (por ejemplo, si el WiFi se cortó o cerraste el Atajo en
el teléfono a medio backup), el log muestra un aviso tipo `⏸ "[perfil]":
sin actividad hace 5+ minutos — el backup parece haberse detenido` — una
sola vez por cada corte, no se repite mientras siga inactivo. Cuántos
minutos de inactividad cuentan como "detenido" es configurable — ver
"⚙ Configuración" → Preferencias más arriba.

Junto a ese botón hay uno más pequeño, **"⤢ Expandir"**, que abre el mismo
registro en una ventana aparte, más grande y redimensionable — útil cuando
una corrida larga genera mucho texto y el panel chico se queda corto.

Cada línea también se guarda en un archivo en disco
(`%APPDATA%\PunkBackup\logs\activity.log`), así que puedes revisar la
actividad pasada incluso después de cerrar la app — no solo lo que está
visible en pantalla en ese momento. Rota diariamente y borra
automáticamente lo más viejo de unos 6 meses, para que nunca crezca sin
límite.

---

## Pantalla "⚙ Configuración" → Perfiles

Debajo del selector de idioma es donde se gestionan las identidades — una
por cada persona o dispositivo.

### "+ Agregar perfil"

1. Escribe un nombre que identifique el dispositivo (ej. `iPhone de
   María`, `iPad de Diego`) — no tiene que ser técnico, es solo para que
   tú lo reconozcas.
2. La app genera un **token** único para ese perfil y te lo copia al
   portapapeles automáticamente — lo vas a pegar en el Atajo de ese
   dispositivo (ver el Manual de configuración del iPhone).
3. Enseguida te pide elegir la **carpeta destino** de ese perfil — puede
   ser cualquier carpeta, en tu disco interno o en un USB externo.

### Botones de cada perfil

| Botón | Qué hace |
|---|---|
| **Elegir carpeta...** | Cambia dónde guarda sus archivos ese perfil (por ejemplo, si cambiaste de USB). Los archivos ya respaldados en la carpeta anterior NO se mueven ni se borran. |
| **Historial USB** | Muestra los discos/carpetas que ese perfil ha usado antes — etiqueta, número de serie, espacio — para que reconozcas cuál USB es cuál aunque Windows le cambie la letra de unidad. |
| **Copiar token** | Vuelve a copiar el token al portapapeles (por si necesitas reconfigurar el Atajo). |
| **Renombrar** | Cambia solo el nombre que ves en la app — no afecta el token ni la carpeta. |
| **Renovar token** | Genera un token nuevo para ese perfil. El Atajo de ese dispositivo deja de funcionar hasta que pegues el token nuevo ahí — úsalo solo si sospechas que el token se filtró. |
| **Eliminar** | Revoca el acceso de ese perfil (su token deja de servir). **No borra ningún archivo ya respaldado.** |

### Segunda copia (opcional)

Debajo de los botones, cada perfil puede tener una **segunda copia** —
una copia de todo lo que hay en su destino principal, guardada en otra
carpeta/USB. No es obligatoria y viene desactivada por defecto; es para
quien quiera tener sus fotos en más de una unidad física.

- **"+ Configurar segunda copia (opcional)"** — aparece cuando todavía no
  configuraste ninguna. Tócalo, elige una carpeta (no puede ser la misma
  que tu destino principal), y con eso ya quedó configurada.
- Una vez configurada, vas a ver cuántos archivos tiene y cuánto espacio
  libre le queda, además de un botón **"🔄 Sincronizar ahora"**.
- Tocar **"🔄 Sincronizar ahora"** copia lo que falte desde tu destino
  principal hacia la segunda copia — empezando por las fotos más
  recientes — y verifica cada archivo después de copiarlo, así una mala
  escritura de la USB se detecta y se reintenta sola en vez de dejar una
  copia dañada sin que nadie se entere. Esto nunca corre solo; tú decides
  cuándo sincronizar.
- Mientras sincroniza, ese mismo botón se convierte en **"⏹ Detener"** —
  úsalo si necesitas desconectar la segunda unidad antes de que termine.
  No se pierde nada en ningún caso: lo que ya se copió y verificó queda
  ahí, y la siguiente sincronización retoma justo donde quedó.
- **"Quitar"** deja de sincronizar hacia esa carpeta — **no** borra
  ningún archivo que ya se haya copiado ahí.
- Si algún día pierdes o se daña tu unidad principal, esta segunda copia
  es un respaldo real e independiente: basta con apuntar el destino
  principal de ese perfil a esa carpeta (con "Elegir carpeta..." de
  arriba) y la app reconoce exactamente lo que ya tiene ahí — no hace
  falta volver a subir nada desde el teléfono.

---

## Flujo típico de uso diario

1. Abres la app con el ícono del Escritorio.
2. Presionas **"🤘 Iniciar backup"**.
3. Corres el Atajo en tu iPhone (manual, o automático si configuraste la
   automatización de WiFi).
4. Ves en la pantalla Principal cómo va subiendo (despliega "Mostrar
   actividad" si quieres el detalle en vivo).
5. Cuando termines, puedes cerrar la app o dejarla — no hace nada por su
   cuenta mientras no le des "Iniciar backup".

## Buenas prácticas

- Crea un perfil por cada persona o dispositivo, nunca compartas un token
  entre dos iPhones.
- Si vas a usar un USB distinto para alguien, simplemente usa "Elegir
  carpeta..." en su perfil — no hace falta crear un perfil nuevo.
- Revisa "Historial USB" antes de conectar un disco que no usas seguido,
  para confirmar que es el correcto.
