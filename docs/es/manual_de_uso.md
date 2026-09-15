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

---

## Pantalla "⚙ Configuración" → Idioma

Arriba de todo en Configuración hay dos botones: **Español** / **English**.
Tócalo y **toda la app cambia de idioma al instante** — botones, títulos,
mensajes, todo — sin cerrar ni reiniciar nada. Tu elección se recuerda la
próxima vez que abras la app.

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
`Detenido`, o `Escuchando en el puerto 8787`.

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

Está **oculto por defecto** para no saturar la pantalla. Al desplegarlo,
muestra un registro en vivo (estilo terminal, texto verde) de cada archivo
que va llegando: nuevo, ya existía, o conflicto. Sirve para confirmar que
algo está pasando en tiempo real mientras corres un Atajo desde el iPhone.
También marca claramente cuándo **inicia** y cuándo **termina** cada
corrida (con el resumen final: nuevos/ya existían/conflictos/errores), así
que puedes ver de un vistazo dónde empieza y termina cada backup en el
historial del log.

Junto a ese botón hay uno más pequeño, **"⤢ Expandir"**, que abre el mismo
registro en una ventana aparte, más grande y redimensionable — útil cuando
una corrida larga genera mucho texto y el panel chico se queda corto.

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
