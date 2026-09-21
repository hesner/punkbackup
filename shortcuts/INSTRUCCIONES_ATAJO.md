# PunkBackup — Configuración del iPhone (Atajo de respaldo por WiFi)

Este manual te guía para instalar, en tu iPhone, el Atajo que envía tus
fotos y videos nuevos a tu PC por WiFi. Usa el archivo de Atajo ya armado —
no hace falta construir ninguna acción a mano.

> **¿Prefieres armarlo tú mismo, o quieres entender qué hace cada acción?**
> Hay una guía aparte para eso: la guía de **Construcción Manual**
> (`shortcuts/INSTRUCCIONES_ATAJO_MANUAL.md`, también publicada como su
> propio PDF). No la necesitas para nada de lo de aquí — este es el camino
> completo para casi todos.

## Antes de empezar, ten a la mano

Este sistema soporta varios dispositivos/personas (perfiles) en la misma PC.
**Cada dispositivo necesita su propio perfil y su propio token** — así que
si vas a configurar más de un iPhone/iPad, repite estos pasos en la app de
PC por cada uno.

En tu PC:
1. Abre la app y presiona **Iniciar backup**.
2. En **"⚙ Configuración"**, click **"+ Agregar perfil"** y ponle un
   nombre que identifique ESTE dispositivo (ej. `iPhone de María`), y elige
   su carpeta destino cuando te la pida.
3. La app te muestra (y copia automáticamente) el **token** de ese perfil —
   solo sirve para ese dispositivo.

Anota estos datos:

| Dato | Dónde lo ves en la app | Ejemplo |
|---|---|---|
| Dirección del servidor (igual para todos los perfiles) | Campo "Dirección" | `http:​/​/​[NOMBRE_DE_TU_PC].​local:​8787` |
| IP alternativa (por si la anterior no responde desde el iPhone) | Campo "IP alternativa" | `http:​/​/​192.​168.​1.​50:​8787` |
| Token de ESTE perfil | Botón "Copiar token" en la fila del perfil que acabas de crear | una cadena larga de letras/números |

> Tu iPhone y tu PC deben estar conectados a la **misma red WiFi**.
> Si luego agregas otro dispositivo, créale su propio perfil — nunca
> reutilices el token de otro dispositivo.

> **Nota de diseño**: este atajo NO usa ningún álbum de "ya respaldado" en
> el iPhone. La decisión de qué subir la toma siempre el servidor,
> preguntando qué existe realmente en la carpeta destino de tu perfil en
> ese momento — así, si cambias de USB/carpeta destino en la PC, el sistema
> se ajusta solo, en vez de "recordar" incorrectamente algo que en
> realidad nunca llegó a esa carpeta.

---

## Paso 1 — Instala el Atajo en tu iPhone

1. En tu **iPhone**, abre Safari y ve a esta dirección (escríbela, o
   mándatela por mensaje/correo para poder tocarla directo):

   **[⬇ Descargar PunkBackup.shortcut](https://github.com/hesner/punkbackup/releases/latest/download/PunkBackup.shortcut)**

   Safari descarga el archivo y ofrece abrirlo en la app **Atajos**. (Si en
   cambio lo descargaste en tu PC, primero mándalo a tu iPhone — AirDrop,
   iCloud Drive, correo, lo que tengas — y ábrelo desde ahí.)

2. **Es probable que iOS lo bloquee al principio con una advertencia de
   seguridad** ("Atajo no confiable" / "No se puede añadir el atajo"). Esto
   es esperado — iOS no confía por defecto en archivos de Atajo que no
   vienen de la galería integrada. Para permitirlo, **solo esta vez**:
   - Ve a **Configuración del iPhone → Atajos → Avanzado**.
   - Activa **"Permitir atajos no confiables"**.
   - Regresa y abre de nuevo el archivo `PunkBackup.shortcut` (desde la app
     Archivos, o descargándolo otra vez) — ahora debería abrir normal en
     Atajos.
   - Es una configuración de una sola vez por iPhone; no vas a tener que
     repetirla para futuras actualizaciones de este mismo Atajo.
3. Toca **"Añadir atajo"**.

## Paso 2 — Pon tu propia dirección y token

El Atajo llega correctamente conectado excepto por dos valores de ejemplo.
Ábrelo para editar (toca y mantén presionado su recuadro → **Editar**) y
cambia:

- La primera acción **Texto** (actualmente `http://your-pc.local:8787`) →
  tu **dirección del servidor** real (de la tabla de arriba).
- La segunda acción **Texto** (actualmente `TOKEN HERE`) → el **token** real
  de este perfil (de la tabla de arriba).

Guarda, y ya quedó construido.

## Paso 3 — Pruébalo

1. Toca el atajo `PunkBackup` una vez, manualmente, desde la app Atajos (o
   desde la pantalla de inicio si lo agregaste ahí).
2. Deberías ver una notificación al final con los números (Nuevos / Ya
   existían / Conflictos). Es normal que los números de esta primera
   corrida muestren varios archivos subidos — es tu primer respaldo
   corriendo.
3. En tu PC, abre en el Explorador de Windows la carpeta destino que
   elegiste para este perfil — deberías ver subcarpetas de Año/Mes con tus
   fotos y videos cayendo adentro.

Si alguno de estos pasos no funciona como se describe, revisa el Manual de
solución de problemas.

> Opcional: también existe un atajo corto "Estado del Backup" que puedes
> construir para ver el estado sin correr un backup completo — ver el
> Paso 2 de la guía de **Construcción Manual** si lo quieres (no viene
> incluido en el archivo ya armado).

---

## Paso 4 — Automatizar: que se dispare solo al llegar a casa

1. Abre **Atajos** → pestaña **Automatización** → **+** → **Crear automatización personal**.
2. Elige **Wi-Fi** → selecciona tu red de casa: `[TU_RED_WIFI]`.
3. Deja marcado **Al conectar**.
4. Toca **Siguiente** → **Añadir acción** → busca y elige tu atajo `PunkBackup`.
5. Toca **Siguiente** → **Listo**.
6. Muy importante: cuando el sistema te pregunte, o en la pantalla de la
   automatización, **desactiva "Preguntar antes de ejecutar"**. La primera
   vez que corra puede pedirte un permiso único de seguridad — acéptalo. A
   partir de ahí correrá sola, en silencio, cada vez que llegues a esa WiFi.

> También puedes correr `PunkBackup` manualmente en cualquier momento
> tocándolo en la app Atajos, o diciendo "Oye Siri, PunkBackup".

> ⚠️ **Un corte breve de WiFi puede re-disparar esta automatización.**
> Como está configurada para "Al conectar", caminar por la casa por una
> zona de señal débil y reconectar cuenta como una nueva conexión — la
> automatización puede volver a dispararse encima de un backup que ya
> estaba corriendo (o que se acaba de cortar). Confirmado en un
> dispositivo real: no se pierde ninguna foto en ningún caso (el diseño
> autosanador lo cubre), pero puedes ver un par de corridas superpuestas
> en el log de actividad de la app de PC después de eso — es esperado,
> no es un error.

---

## Notas
- El sistema **nunca borra ni modifica nada en tu iPhone** — solo lee fotos
  y las sube.
- La verdad de "qué ya está respaldado" vive **solo en la carpeta destino de
  la PC**, nunca en el iPhone. Si en la PC cambias la carpeta/USB de tu
  perfil, el atajo automáticamente vuelve a enviar lo que falte en la
  carpeta nueva — no necesitas hacer nada distinto en el iPhone.
- Si más adelante actualiza el archivo de Atajo de esta guía en un futuro
  release de PunkBackup, descárgalo de nuevo y repite los Pasos 1-2 — tu
  Dirección del servidor y Token se mantienen igual.
