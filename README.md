# readme-seeder

Inserta datos de prueba en PostgreSQL, MySQL y MongoDB.

## Uso

```bash
docker compose run --rm seeder
```

Al terminar, los logs muestran un resumen y 5 emails de prueba:

```
Usuarios de prueba (password: pass123):
  cristina.gil@example.com
  roberto.fernandez@hotmail.com
  ...
```

Cualquiera de esos emails + `pass123` sirve para loguearse.
