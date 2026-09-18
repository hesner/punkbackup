# PunkBackup — Manual de solución de problemas

## La app se cierra sola poco después de abrirla

**Esto es Avast** (u otro antivirus parecido), no un error de PunkBackup —
ver la sección "⚠ Importante: esta app no tiene firma digital de pago" del
Manual de instalación para el por qué, y el arreglo (agregar una excepción
para la carpeta de instalación de PunkBackup en Avast, restaurarla desde
Cuarentena/Virus Chest si quedó ahí).

## "Iniciar backup" no hace nada / no cambia de estado

- Cierra la app por completo (no solo minimizarla) y ábrela de nuevo con el
  ícono del Escritorio.
- Si vuelve a pasar, ahora debería aparecerte una ventana con el error
  exacto (en vez de fallar en silencio) — mándanos ese texto.
- Verifica que no haya quedado otra copia de la app abierta desde antes
  (revisa la barra de tareas).

## El iPhone no puede conectarse al servidor

1. Confirma que el iPhone y la PC estén en la **misma red WiFi** (revisa el
   nombre exacto en Configuración → WiFi de ambos dispositivos — a veces un
   router tiene redes separadas para 2.4GHz/5GHz con nombres parecidos).
2. Prueba abrir, desde el navegador del iPhone (Safari), la dirección que
   te muestra la app (ej. `http://NOMBRE-PC.local:8787/health`). Si no
   carga, prueba con la "IP alternativa" que también te muestra la app.
3. Confirma que el servidor esté encendido en la PC ("Escuchando en el
   puerto...").
   Si alguna vez falla al iniciar (por ejemplo, si otro programa ya está
   usando el puerto), la app ahora muestra un mensaje de error real
   explicando por qué, en vez de decir "Escuchando" sin serlo de verdad —
   si ves ese error, cierra lo que esté usando el puerto 8787 (u otra
   copia de PunkBackup abierta) e inténtalo de nuevo.
4. Revisa que la regla de Firewall exista: PowerShell (como administrador) →
   `Get-NetFirewallRule -DisplayName "PunkBackup"`. Si no aparece (por
   ejemplo, si no marcaste esa casilla durante la instalación), agrégala
   con `New-NetFirewallRule -DisplayName "PunkBackup" -Direction Inbound
   -Protocol TCP -LocalPort 8787 -Profile Private -Action Allow`.

## Error 401 "Missing or invalid X-Backup-Token header"

- El token en el Atajo no coincide con el de tu perfil en la PC.
- En el Atajo, revisa **cada** acción que tenga un encabezado
  `X-Backup-Token` — el valor debe ser el **chip** de la variable `Token`
  (fondo de color), nunca la palabra "Token" escrita como texto plano.
- Copia el token de nuevo desde la app (botón "Copiar token" en el perfil) y
  pégalo en la acción **Text** correspondiente del Atajo.

## Error 403 "This profile is paused"

- El perfil está **Pausado**. Ve a la app → pantalla Principal o
  ⚙ Configuración → activa el interruptor a **Activo**.

## Error 409 "no destination folder configured"

- Ese perfil no tiene carpeta destino. Ve a ⚙ Configuración → "Elegir
  carpeta..." para ese perfil.

## El Atajo corre pero no sube ninguna foto nueva

- Revisa que **"Find Photos"** no tenga ningún filtro raro además del
  `Date Taken is before Limite` descrito en el Manual de configuración del
  iPhone — otro filtro distinto que se cuele hace que dé 0 resultados en
  silencio, sin ningún error visible.
- Revisa que **`Limit`** esté activado y en **50** en "Find Photos" — esto
  es obligatorio, no opcional: sin él, "Find Photos" falla directamente en
  una biblioteca grande, incluso solo contando resultados.
- Confirma en Configuración → Privacidad y seguridad → Fotos que la app
  Atajos tenga acceso ("Todas las fotos" / "Always Allow") — con acceso
  limitado, una foto que acabas de tomar o guardar simplemente puede no
  ser visible para el Atajo todavía, sin ningún error visible.

## Todas las fotos nuevas están cayendo en la misma carpeta (el mes actual)

Esto pasa cuando el servidor recibe una fecha vacía para cada foto, y
`_year_month_dir()` usa "ahora mismo" como respaldo — así que todo termina
en la carpeta del mes en curso sin importar cuándo se tomó la foto
realmente.

- **Causa casi siempre confirmada**: el chip dentro de la acción
  **Formatear fecha** (la que construye la variable `TomadaEn`, en la
  sección 4 del Manual de configuración del iPhone) se desconfiguró en
  silencio y quedó apuntando a otro atributo (por ejemplo "Nombre") en vez
  de **Fecha de captura**. Esto suele pasar sin ningún error visible,
  justo después de agregar o mover otra acción dentro del mismo bloque
  "Repetir" — Shortcuts a veces reconfigura chips vecinos sin avisar.
- **Cómo confirmarlo**: dentro del Atajo, abre la acción "Formatear fecha"
  de la sección 4 y toca su chip — debe decir **Fecha de captura**. Si
  dice cualquier otra cosa, ese es el problema.
- **Arreglo**: vuelve a seleccionar "Fecha de captura" en ese chip. Las
  fotos que subas DESPUÉS de este arreglo van a quedar en su carpeta
  correcta automáticamente — no hace falta hacer nada más para las
  nuevas.
- **Las fotos que ya se subieron mal archivadas** (antes del arreglo) no
  se reorganizan solas — quedan donde cayeron. Si esto te pasó con muchos
  archivos, es un caso de mantenimiento puntual (leer la fecha real
  directamente del archivo o forzar un re-envío desde el teléfono); no es
  algo que el Atajo o el servidor corrijan automáticamente.

## Mi biblioteca es enorme (miles de fotos) — ¿llegará a terminar el respaldo completo?

El Atajo barre tu biblioteca hacia atrás en bloques acotados de 50 fotos,
empezando por las más recientes, avanzando automáticamente bloque por
bloque dentro de una sola corrida — ver el paso "Armar el barrido en
bloques hacia atrás" del Manual de configuración del iPhone. Esto es lo
que permite que una biblioteca grande de verdad llegue a terminar, en vez
de fallar por tiempo (sin `Limit`) o quedarse revisando siempre el mismo
conjunto fijo sin avanzar (`Limit` fijo sin forma de avanzar).

- La cantidad de bloques por corrida se controla con la variable
  `Repeticiones` (una acción `Text` cerca del inicio, por defecto `50`).
  Comprobado funcionando con `Repeticiones` hasta 50 (≈2500 fotos
  revisadas en una sola corrida). Para tu primer respaldo completo de una
  biblioteca grande, está bien correr el Atajo varias veces seguidas en
  vez de subir `Repeticiones` muy alto desde el primer intento — revisa el
  log de actividad de la app en la PC (usa "⤢ Expandir" para verlo más
  grande) para confirmar que va avanzando bien antes de subir el número.
- **Los videos actualmente pueden llegar vacíos (0 bytes) — a veces de
  forma sistemática, no solo ocasional.** El servidor siempre detecta y
  rechaza esto automáticamente, así que nunca queda registrado como
  respaldado de verdad y ese mismo video simplemente se reintenta en una
  corrida posterior — pero la causa real (por qué el iPhone a veces manda
  el cuerpo vacío específicamente para un video) todavía no está resuelta:
  no es optimización de almacenamiento de iCloud, no es un límite de
  tamaño fijo, y ni siquiera se arregla de forma confiable manteniendo
  Atajos en primer plano — es un problema abierto, no resuelto. Las fotos
  no se ven afectadas (confirmado confiable al 100%). Mantener la pantalla
  encendida y Atajos en primer plano durante una corrida manual grande
  puede ayudar igual, y no hace daño, pero no cuentes con que arregle
  todos los casos.
- Si una corrida se interrumpe (sales de casa, o le das Stop), no se pierde
  nada — todo lo ya subido queda respaldado para siempre. La siguiente
  corrida simplemente vuelve a empezar desde tus fotos más recientes, no
  exactamente donde quedó — los bloques ya completos se revisan rápido
  (sin transferir archivos) antes de llegar a terreno nuevo.
- Si el Atajo mismo parece congelarse sin ningún error ni causa visible
  (raro, pero una falla conocida de la app Atajos sin relación con este
  sistema), fuérzalo a cerrar desde el selector de apps y vuelve a
  correrlo — nada se corrompe por una corrida interrumpida, ver el punto
  anterior.

## El teléfono se traba mientras corre el Atajo

- Ve a Configuración → Pantalla y brillo → Auto-bloqueo → **Nunca**
  (temporalmente, mientras corres un respaldo grande).
- Corridas con miles de fotos pueden tardar varios minutos — es normal, no
  es que se haya "colgado".
- Si de verdad no responde: reinicio forzado del iPhone es seguro, no se
  pierde nada (la corrida en el servidor queda "a medias" sin daño).

## La notificación final del Atajo sale con los números vacíos (Nuevos/Ya existían/Conflictos)

**No afecta el respaldo real** en ningún caso — las fotos se siguen
subiendo y guardando correctamente aunque la notificación salga vacía.
Si te pasa, revisa la acción **"Obtener contenido de URL"** hacia
`/run/finish` (sección 5 del Manual de configuración del iPhone):

- El header `X-Backup-Token` debe estar en **Headers**, no dentro de
  **Request Body → Form**.
- **Request Body → Form** debe tener un campo `run_id` con valor la
  variable `RunID` — sin ese campo, el servidor rechaza la petición y el
  resto de esa sección (leer los contadores, armar el mensaje) se salta
  en silencio, dejando el resumen vacío.

Para confirmar que sí se guardó algo mientras lo revisas, mira la carpeta
destino directamente (ver siguiente sección).

## Cómo revisar si de verdad se están guardando archivos

Sin necesidad de nada técnico: abre la carpeta destino que elegiste en el
Explorador de Windows — deberías ver subcarpetas por Año y Mes con tus
fotos y videos dentro.

## Sigue sin funcionar

Contacta a quien te ayudó a instalar el sistema, o revisa el repositorio del
proyecto en GitHub para reportar el problema.
