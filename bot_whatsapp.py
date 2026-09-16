import os
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN DE CREDENCIALES
# ==========================================
SUPABASE_URL = "https://uctwcciuvgonajsvfhkc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjdHdjY2l1dmdvbmFqc3ZmaGtjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDc3ODA0NywiZXhwIjoyMDk2MzU0MDQ3fQ.RLXQTYlwBj3Cj-u76jxVxiOJFfJ5aCp3B3-iBLIeTpk"
GEMINI_API_KEY = "AQ.Ab8RN6LWvCO5giXroJMHmS7QQIJvVr95AAwIMpwVTr30hSQjoQ"

# Inicializar conexión a la base de datos
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
        # Consultar el inventario de Tapitel
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

        # ==========================================
        # 2. CONEXIÓN DIRECTA A GEMINI (Bypass)
        # ==========================================
        url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        encabezados = {
            "Content-Type": "application/json"
        }
        
        cuerpo_peticion = {
            "contents": [{
                "parts": [{"text": prompt_sistema}]
            }]
        }

        # Enviar el inventario y la pregunta a Google
        respuesta_google = requests.post(url_gemini, headers=encabezados, json=cuerpo_peticion)
        
        if respuesta_google.status_code == 200:
            datos_ia = respuesta_google.json()
            respuesta_final = datos_ia["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"Error de Google: {respuesta_google.text}", flush=True)
            respuesta_final = "Una disculpa, estoy revisando el almacén y tuve un pequeño problema técnico."

    # ESTA ES LA PARTE QUE FALTABA EN TU CÓDIGO
    except Exception as e:
        print(f"Error interno en el servidor: {e}", flush=True)
        respuesta_final = "Una disculpa, estoy revisando el almacén y tuve un pequeño problema técnico."

    return jsonify({"respuesta": respuesta_final})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
