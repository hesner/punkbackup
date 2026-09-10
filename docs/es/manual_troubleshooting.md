# Manual de solución de problemas

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
   `Get-NetFirewallRule -DisplayName "iPhone WiFi Backup"`.

## Error 401 "Missing or invalid X-Backup-Token header"

- El token en el Atajo no coincide con el de tu perfil en la PC.
- En el Atajo, revisa **cada** acción que tenga un encabezado
  `X-Backup-Token` — el valor debe ser el **chip** de la variable `Token`
  (fondo de color), nunca la palabra "Token" escrita como texto plano.
- Copia el token de nuevo desde la app (botón "Copiar token" en el perfil) y
  pégalo en la acción **Text** correspondiente del Atajo.

## Error 403 "This profile is paused"

- El perfil está **Pausado**. Ve a la app → pestaña Principal o Perfiles →
  activa el interruptor a **Activo**.

## Error 409 "no destination folder configured"

- Ese perfil no tiene carpeta destino. Ve a Perfiles → "Elegir carpeta..."
  para ese perfil.

## El Atajo corre pero no sube ninguna foto nueva

- Revisa que **"Find Photos"** no tenga ningún filtro raro (debe decir
  "Find Photos" sin condiciones adicionales, salvo Sort/Order/Limit).
- Si tienes un **Limit** bajo en "Find Photos" y ya llevas varias corridas,
  puede que siempre esté revisando las mismas fotos más viejas — sube el
  Limit o desactívalo para un respaldo completo de tu biblioteca.
- Confirma en Configuración → Privacidad y seguridad → Fotos que la app
  Atajos tenga acceso ("Todas las fotos" / "Always Allow").

## El teléfono se traba mientras corre el Atajo

- Ve a Configuración → Pantalla y brillo → Auto-bloqueo → **Nunca**
  (temporalmente, mientras corres un respaldo grande).
- Corridas con miles de fotos pueden tardar varios minutos — es normal, no
  es que se haya "colgado".
- Si de verdad no responde: reinicio forzado del iPhone es seguro, no se
  pierde nada (la corrida en el servidor queda "a medias" sin daño).

## Cómo revisar si de verdad se están guardando archivos

Sin necesidad de nada técnico: abre la carpeta destino que elegiste en el
Explorador de Windows — deberías ver subcarpetas por Año y Mes con tus
fotos y videos dentro.

## Sigue sin funcionar

Contacta a quien te ayudó a instalar el sistema, o revisa el repositorio del
proyecto en GitHub para reportar el problema.
