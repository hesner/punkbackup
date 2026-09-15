# PunkBackup — Manual de solución de problemas

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

Es un problema cosmético conocido — el paso final que cierra la corrida
(`/run/finish`) a veces no completa, así que el resumen no siempre trae los
números. **No afecta el respaldo real**: las fotos se siguen subiendo y
guardando correctamente. Para confirmar que sí se guardó algo, revisa la
carpeta destino directamente (ver siguiente sección).

## Cómo revisar si de verdad se están guardando archivos

Sin necesidad de nada técnico: abre la carpeta destino que elegiste en el
Explorador de Windows — deberías ver subcarpetas por Año y Mes con tus
fotos y videos dentro.

## Sigue sin funcionar

Contacta a quien te ayudó a instalar el sistema, o revisa el repositorio del
proyecto en GitHub para reportar el problema.
