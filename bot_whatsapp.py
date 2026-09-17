import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN SEGURA DE CREDENCIALES
# ==========================================
# El .strip() evita errores si se copian espacios invisibles en Render
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/webhook', methods=['POST'])
def webhook():
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Formato incorrecto, se esperaba JSON"}), 400

    mensaje_entrante = datos.get('mensaje', '').strip()
    numero_cliente = datos.get('numero', 'Desconocido')

    if not mensaje_entrante:
        return jsonify({"respuesta": "No pude leer tu mensaje. ¿En qué te ayudo?"})

    print(f"[{numero_cliente}] Pregunta: {mensaje_entrante}", flush=True)

    try:
        # Consultar inventario
        respuesta_bd = supabase.table('inventario_tapitel').select('*').execute()
        datos_inventario = respuesta_bd.data

        prompt_sistema = f"""
        Eres Tapi, el asistente virtual experto de Tapitel. 
        Tu objetivo es dar una excelente atención al cliente, respondiendo dudas sobre nuestro catálogo de materiales para tapicería.
        
        Reglas:
        1. Sé amable, claro y directo.
        2. Usa el inventario proporcionado abajo para saber qué tenemos disponible.
        3. Si un cliente pide algo que no está en el inventario, dile amablemente que por el momento no contamos con ello.
        4. No inventes precios ni existencias que no estén en la lista.
        
        Inventario actual en bodega:
        {datos_inventario}
        
        Mensaje del cliente: "{mensaje_entrante}"
        
        Redacta tu respuesta a continuación:
        """

    
        # 2. CONEXIÓN DIRECTA (VERSIÓN OFICIAL V1)
        # ==========================================
        url_gemini = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"

        encabezados = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
        
        cuerpo_peticion = {
            "contents": [{"parts": [{"text": prompt_sistema}]}]
        }

        respuesta_google = requests.post(
            url_gemini,
            headers=encabezados,
            json=cuerpo_peticion,
            timeout=30
        )
        
        if respuesta_google.status_code == 200:
            datos_ia = respuesta_google.json()
            respuesta_final = datos_ia["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"Error de Google {respuesta_google.status_code}: {respuesta_google.text}", flush=True)
            respuesta_final = "Una disculpa, estoy revisando el almacén y tuve un pequeño problema técnico."

    except Exception as e:
        print(f"Error interno en el servidor: {e}", flush=True)
        respuesta_final = "Una disculpa, estoy revisando el almacén y tuve un pequeño problema técnico."

    return jsonify({"respuesta": respuesta_final})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
