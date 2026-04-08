# Smoke test demo por rol (CoyoLabs)

## STUDENT
1. Iniciar sesión con cuenta verificada.
2. Abrir notificaciones (logo) y confirmar que carga feed.
3. Forzar recarga de página y validar badge actualizado.
4. Entrar a Objetos perdidos y validar que el CTA no redirige a ruta admin.
5. Abrir Impresiones 3D > Nueva solicitud y verificar copy de límites visibles.
6. Enviar solicitud con 1 archivo válido y confirmar feedback de éxito.

## TEACHER
1. Iniciar sesión como profesor verificado con perfil completo.
2. Revisar Mi perfil: cambio de teléfono directo y carga académica visible.
3. Reservaciones: validar selector de materia/grupo y calendario de ocupación.
4. Notificaciones: validar recepción (o fallback con aviso de sincronización).
5. Objetos perdidos: validar CTA no admin.

## ADMIN
1. Iniciar sesión y validar entrada a Panel (operación).
2. Revisar bandeja de notificaciones y acciones marcar/leer/limpiar.
3. Objetos perdidos: validar CTA de registro administrativo habilitado.
4. Impresiones 3D admin: cambiar estado y confirmar notificación READY idempotente.
5. Reportes: abrir vista, revisar columnas demo-friendly por defecto y descargas.
