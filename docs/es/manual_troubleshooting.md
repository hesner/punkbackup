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

- Revisa que **"Find Photos"** no tenga ningún filtro raro (debe decir
  "Find Photos" sin condiciones adicionales, salvo Sort/Order/Limit) — un
  filtro que se cuele por accidente hace que dé 0 resultados en silencio,
  sin ningún error visible.
- Si tienes un **Limit** bajo en "Find Photos" y ya llevas varias corridas,
  puede que siempre esté revisando las mismas fotos más viejas — sube el
  Limit para avanzar.
- Confirma en Configuración → Privacidad y seguridad → Fotos que la app
  Atajos tenga acceso ("Todas las fotos" / "Always Allow").

## Mi biblioteca es enorme (miles de fotos) y el respaldo completo falla o se congela

- "Find Photos" **sin límite** revisa toda tu biblioteca de una sola vez —
  con bibliotecas muy grandes (miles de fotos) esto puede tardar mucho o
  hacer que iOS interrumpa el Atajo con un error genérico ("There was a
  problem running the shortcut"). Esto es una **limitación conocida**,
  todavía sin una solución definitiva.
- Mientras tanto: usa un **Limit moderado** (ej. 300-500) y corre el Atajo
  varias veces manualmente — cada corrida avanza mientras haya fotos
  nuevas sin respaldar más recientes que las ya cubiertas, aunque con un
  límite fijo puede que no llegue nunca a las fotos más antiguas de una
  biblioteca muy grande. Para el respaldo inicial completo de una biblioteca
  grande, ten paciencia, mantén el teléfono con auto-bloqueo desactivado y
  conectado a corriente, y si falla, vuelve a correrlo — el sistema es
  incremental, así que no se pierde el progreso ya logrado.

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
