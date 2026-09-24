# PunkBackup — Manual de solución de problemas

## La app se cierra sola poco después de abrirla

**Esto es Avast** (u otro antivirus parecido), no un error de PunkBackup —
ver la sección "⚠ Importante: esta app no tiene firma digital de pago" del
Manual de instalación para el por qué, y el arreglo (agregar una excepción
para la carpeta de instalación de PunkBackup en Avast, restaurarla desde
Cuarentena/Virus Chest si quedó ahí).

Si un backup que iniciaste desde tu iPhone justo después de abrir
PunkBackup parece haberse detenido sin razón, casi seguro que es por
esto: Avast escanea la app durante sus primeros ~10 segundos, y después
la cierra y la vuelve a abrir en silencio — cualquier corrida de backup
activa justo en ese momento se corta junto con ella (ver el Manual de
instalación para la explicación completa). No se pierde nada de lo que
ya se subió — solo vuelve a iniciar el backup desde tu iPhone una vez que
la app esté abierta de nuevo. Agregar la excepción de Avast hace que esto
deje de pasar.

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
   Reintenta automáticamente unas cuantas veces (mostrando brevemente
   "Iniciando backup...") si el puerto no se libera de inmediato — común
   justo después de que un antivirus cierre y reabra la app. Si sigue
   fallando después de esos reintentos (por ejemplo, si otro programa de
   verdad está usando el puerto), la app muestra un mensaje de error real
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
  `Date Taken is before Limite` (ver el paso 3 de la guía alternativa de
  Construcción Manual para ver cómo debería quedar) — otro filtro
  distinto que se cuele hace que dé 0 resultados en silencio, sin ningún
  error visible.
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
  **Formatear fecha** (la que construye la variable `TomadaEn` — ver el
  paso 4 de la guía alternativa de Construcción Manual) se desconfiguró en
  silencio y quedó apuntando a otro atributo (por ejemplo "Nombre") en vez
  de **Fecha de captura**. Esto suele pasar sin ningún error visible,
  justo después de agregar o mover otra acción dentro del mismo bloque
  "Repetir" — Shortcuts a veces reconfigura chips vecinos sin avisar.
- **Cómo confirmarlo**: dentro del Atajo, abre la acción "Formatear fecha"
  y toca su chip — debe decir **Fecha de captura**. Si
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

## Un video sale con la fecha de hoy en otra app (PhotoPrism, Finder...), aunque esté en la carpeta Año/Mes correcta

Esto es esperado y ya está corregido automáticamente — no necesitas hacer
nada. Algunos videos (principalmente los importados de otras apps, no los
grabados directo con la cámara) necesitan un reintento automático para
subir correctamente; ese proceso de reintento dejaba la fecha interna
propia del video con el día del reintento, no la fecha real de grabación
— aunque la carpeta donde cayó siempre fue la correcta. El servidor ahora
corrige esa fecha interna automáticamente en cada video que recibe, y ya
corrigió retroactivamente todos los videos respaldados antes de que
existiera esta corrección. Si de todas formas sigues viendo una fecha
incorrecta en otra app después de esto, es posible que esa app esté
leyendo un campo distinto al que se corrige — no es algo que valga la
pena perseguir más del lado de PunkBackup.

## Mi biblioteca es enorme (miles de fotos) — ¿llegará a terminar el respaldo completo?

El Atajo barre tu biblioteca hacia atrás en bloques acotados de 50 fotos,
empezando por las más recientes, avanzando automáticamente bloque por
bloque dentro de una sola corrida — esto ya viene armado dentro del
archivo de Atajo ya hecho del Manual de configuración del iPhone, no hace
falta configurar nada de tu parte. (Si construiste el Atajo a mano, o
solo quieres entender exactamente cómo funciona, ver el paso "Armar el
barrido en bloques hacia atrás" de la guía alternativa de Construcción
Manual.) Esto es lo que permite que una biblioteca grande de verdad llegue a terminar, en vez
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
  exactamente donde quedó. Revisar de nuevo esos bloques ya completos
  nunca vuelve a transferir ningún archivo, pero — ver la sección "¿Qué tan
  rápido es un respaldo, en la práctica?" justo abajo — tampoco es
  necesariamente rápido; calcula tiempo real para eso, no cero.
- Si el Atajo mismo parece congelarse sin ningún error ni causa visible
  (raro, pero una falla conocida de la app Atajos sin relación con este
  sistema), fuérzalo a cerrar desde el selector de apps y vuelve a
  correrlo — nada se corrompe por una corrida interrumpida, ver el punto
  anterior.

## ¿Qué tan rápido es un respaldo, en la práctica? (medido en este ambiente)

Estos números vienen de subidas reales de producción en el ambiente propio
de este proyecto — un **iPhone 15**, una **red WiFi de casa**, y una **PC
Windows (Dell)** — calculados directamente de las marcas de tiempo propias
del servidor, usando solo los **últimos días** de subidas reales (cerca de
1.340 archivos) para que los números reflejen las condiciones actuales, no
un promedio mezclado con las primeras corridas de prueba del proyecto.

| Tipo de archivo | % típico de una biblioteca | Tamaño promedio | Tiempo típico por archivo |
|---|---|---|---|
| JPEG | ~57% | 0.24 MB | ~1.7 s |
| HEIC | ~30% | 2.0 MB | ~6.5 s |
| PNG | ~5.5% | 2.9 MB | ~6.6 s |
| MP4 | ~3% | 8.3 MB | ~9.7 s |
| MOV | ~4% | 23.6 MB | ~16.7 s |

La mayor parte del tiempo de una foto chica **no** es transferencia por
red — es el costo fijo de las dos peticiones por archivo que hace el Atajo
(`/check`, luego `/upload`). Ese costo fijo casi no cambia según el tamaño,
así que domina en fotos chicas y pesa cada vez menos en videos grandes,
donde la velocidad real de transferencia pasa a ser el factor principal.

**Proyección por `Repeticiones`** (la variable que controla cuántos
bloques de 50 elementos barre una sola corrida — ver la nota "Ajustando
`Repeticiones`" del Manual de configuración del iPhone), desglosada por
tipo de archivo con esta misma mezcla real, para un **primer respaldo de
archivos totalmente nuevos**:

| Repeticiones | Total elementos | JPEG | HEIC | PNG | MP4 | MOV | Tiempo (solo elementos nuevos) |
|---|---|---|---|---|---|---|---|
| 10 | 500 | 287 | 152 | 27 | 16 | 18 | ~35 min |
| 20 | 1.000 | 574 | 303 | 55 | 31 | 37 | ~1 h 10 min |
| 30 | 1.500 | 861 | 455 | 82 | 47 | 55 | ~1 h 45 min |
| 40 | 2.000 | 1.148 | 607 | 109 | 63 | 73 | ~2 h 20 min |
| 50 | 2.500 | 1.435 | 759 | 136 | 78 | 92 | ~2 h 56 min |
| 75 | 3.750 | 2.152 | 1.138 | 205 | 118 | 137 | ~4 h 24 min |
| 100 | 5.000 | 2.870 | 1.517 | 273 | 157 | 183 | ~5 h 52 min |
| 150 | 7.500 | 4.305 | 2.276 | 409 | 235 | 275 | ~8 h 48 min |
| 180 | 9.000 | 5.166 | 2.731 | 491 | 283 | 330 | ~10 h 34 min |
| 200 | 10.000 | 5.740 | 3.034 | 546 | 314 | 366 | ~11 h 44 min |
| 250 | 12.500 | 7.175 | 3.793 | 682 | 392 | 458 | ~14 h 40 min |

`Repeticiones` hasta **50** (≈2.500 elementos) está confirmado funcionando
en un dispositivo real desde las pruebas originales de este proyecto.
**`Repeticiones = 180` (≈9.000 elementos) también fue confirmado
funcionando en un dispositivo real** — el Atajo en sí no falla ni se
cuelga a ese tamaño. Los valores por encima de 50 que no se han confirmado
por separado se muestran igual como referencia, pero trátalos como no
verificados hasta probarlos.

> ⚠️ **Importante, encontrado investigando un respaldo real que no había
> terminado después de varias sesiones**: la tabla de arriba solo modela
> el tiempo de archivos **nuevos**. Asume que cada elemento del barrido
> necesita una subida real — pero una vez que parte de tu biblioteca ya
> está respaldada (de una corrida anterior interrumpida), la mayoría de
> los 50 elementos de cada bloque nuevo van a ser "ya respaldado, se
> salta" en vez de subidas reales. Medido directamente del log de
> actividad: un salto (el `/check` responde "ya está respaldado", sin
> transferir ningún archivo) tardó una **mediana de unos 20 segundos** en
> corridas reales recientes — no el ida-y-vuelta casi instantáneo que
> esperarías de un chequeo HTTP simple sin nada que transferir (la muestra
> todavía es chica y tiene ruido — desde unos segundos hasta varios
> minutos). **Esto significa que una corrida que está mayormente
> re-revisando contenido ya respaldado puede tardar notablemente más que
> lo que sugiere la tabla de arriba**, no menos — probablemente explica
> por qué un respaldo grande que se detiene y se retoma varias veces puede
> tardar mucho más en tiempo real que lo que estima la proyección de "solo
> elementos nuevos". La causa exacta todavía no está confirmada
> (candidatos: costo fijo propio de cada acción dentro de la app Atajos, o
> que `Find Photos` vuelve a escanear una biblioteca grande en cada
> bloque) — trata el caso de mayoría-saltos como **más lento, no más
> rápido**, que un primer respaldo del mismo número de elementos, hasta
> que esto se investigue más a fondo.

Otras salvedades:
- Tu propia mezcla de fotos/videos cambia estos números — una biblioteca
  con más videos tarda notablemente más por elemento que una con más fotos.
- La fuerza de tu propia señal WiFi y otros dispositivos compitiendo por
  el ancho de banda al mismo tiempo pueden mover estos números en
  cualquier dirección.

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
`/run/finish` (ver el paso 5 de la guía alternativa de Construcción
Manual):

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

## Segunda copia (espejo) — mensajes y qué significan

Ver la sección "Segunda copia (opcional)" del Manual de uso para cómo
funciona normalmente esta funcionalidad. Estos son los mensajes que
podrías llegar a ver:

- **"No se puede usar esa carpeta"** — intentaste poner la segunda copia
  exactamente en la misma carpeta que tu destino principal. Elige otra.
- **"🔄 Segunda copia: [ruta] (no conectada)"**, botón de sincronizar en
  gris — estado normal y esperado cuando esa unidad no está conectada en
  este momento. No es un error; conéctala de nuevo y vuelve a estar lista
  para sincronizar.
- **"La segunda copia no tiene espacio suficiente para todo lo
  pendiente"** — un aviso que aparece antes de sincronizar, no algo que
  detiene el proceso: igual copia lo que alcance, empezando por tus fotos
  más recientes, y retoma el resto cuando liberes espacio o pongas una
  USB más grande.
- **"La sincronización se detuvo antes de terminar ([error])"** — algo
  interrumpió un archivo a mitad de copiarlo, casi siempre porque la
  unidad se llenó de verdad o se desconectó en vez de expulsarse de forma
  segura. No se pierde nada — lo que ya se copió con éxito antes de eso
  queda válido — solo revisa la unidad y toca "🔄 Sincronizar ahora" de
  nuevo; retoma exactamente donde se detuvo.
- **"No se pudo completar la sincronización de la segunda copia:
  [error]"** — una falla real, puntual (poco común). El log de actividad
  (▼ Mostrar actividad) tiene el texto exacto del error justo después de
  esta línea en el log.
- Reconectar una USB de segunda copia que ya tiene algunos archivos nunca
  vuelve a copiar lo que ya está ahí, y nunca reinicia el contador visible
  desde cero — el conteo que ves ya refleja todo lo que hay en esa
  unidad, lo viejo y lo nuevo combinados.
- **"⚠ N fallidos"**, junto al contador durante la sincronización —
  aparece cuando algunos archivos no logran pasar la verificación (casi
  siempre porque otra cosa está usando la misma unidad USB al mismo
  tiempo, por ejemplo un respaldo real desde el iPhone corriendo en
  paralelo). El contador principal (**X / Y archivos**) solo cuenta
  copias que sí se confirmaron correctas — nunca cuenta intentos fallidos
  como si fueran progreso, así que si lo ves avanzar muy lento junto con
  un número de fallidos que crece, es una señal real de que algo más
  está compitiendo por esa unidad — no un error del programa. Detén el
  proceso que esté usando esa misma unidad y vuelve a sincronizar.

## ¿Qué tan rápido es la sincronización de la segunda copia (espejo)?

Mismo método de medición real que la velocidad de subida por WiFi de
arriba, pero para la copia local USB-a-USB — medido de una corrida real
en el ambiente propio de este proyecto (607 archivos reales, 3.11 GB,
copiados y verificados).

| Tipo de archivo | Cantidad | Tamaño prom. | Tiempo típico | Velocidad aprox. |
|---|---|---|---|---|
| JPEG | 349 | 0.21 MB | ~1.35 s | ~0.15 MB/s |
| HEIC | 117 | 2.23 MB | ~2.24 s | ~0.99 MB/s |
| PNG | 57 | 1.75 MB | ~1.70 s | ~1.03 MB/s |
| MOV | 82 | 32.62 MB | ~8.27 s | ~3.94 MB/s |

La copia local es en general más rápida que subir el mismo archivo por
WiFi — sobre todo en videos (~8 s local vs. ~17-19 s por WiFi) — pero en
fotos JPEG chicas casi no hay diferencia (~1.35 s local vs. ~1.7-2 s por
WiFi). Misma razón de fondo que los números de WiFi: la mayor parte del
tiempo de un archivo chico es costo fijo por archivo (abrirlo, copiarlo,
releerlo para verificar, registrarlo), no transferencia de datos en sí —
la velocidad de transferencia real solo empieza a pesar cuando el archivo
ya es grande (videos).

**Salvedad importante**: esto se midió en una USB chica (4 GB) y casi
llena — no en una unidad nueva con espacio de sobra. Una unidad flash con
poco espacio libre puede comportarse peor que estos números en
condiciones reales (esta misma corrida terminó porque se quedó sin
espacio de verdad, con una tasa notablemente más alta de copias que
fallaron la verificación justo al final — 58 de 289, contra 7 la primera
vez que se probó la misma USB con más espacio disponible). Espera que una
USB sana con espacio real rinda al menos así de bien, probablemente
mejor — pero no esperes que una USB casi llena aguante el ritmo.

## Sigue sin funcionar

Contacta a quien te ayudó a instalar el sistema, o revisa el repositorio del
proyecto en GitHub para reportar el problema.
