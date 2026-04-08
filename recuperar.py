import xmlrpc.client

# Tus datos de conexión
URL = "https://proyectos-gerenciando-canales.odoo.com"
DB = "proyectos-gerenciando-canales"
USERNAME = "odooproyectosgerenciando@gmail.com"
API_KEY = "T5128740142e5be95fb506af7deb1a574cefad87f" # Reemplazá por la clave larga real

print("Conectando a Odoo por la puerta trasera...")
common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, USERNAME, API_KEY, {})
models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

if uid:
    print(f"¡Conexión exitosa! Tu ID de usuario es: {uid}")
    
    # LA MAGIA: Forzamos el cambio de contraseña
    NUEVA_CONTRASEÑA = "FacundoRescate2026!" # Podés poner la que quieras acá
    
    try:
        models.execute_kw(DB, uid, API_KEY, 'res.users', 'write', [[uid], {'password': NUEVA_CONTRASEÑA}])
        print(f"✅ ¡ÉXITO! La contraseña se cambió correctamente a: {NUEVA_CONTRASEÑA}")
        print("Ahora andá a la web de Odoo, poné tu mail y esta nueva contraseña. Luego te pedirá el código de Google.")
    except Exception as e:
        print(f"❌ Error al intentar cambiar la clave: {e}")
else:
    print("❌ No se pudo conectar. Revisá que la API Key esté bien pegada.")
