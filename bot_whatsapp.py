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
        # 2. CONEXIÓN DIRECTA A GEMINI (Bypass de la librería)
        # ==========================================
        # AQUÍ ESTÁ EL CAMBIO: Le inyectamos tu llave directamente a la URL con ?key=
        url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        # Dejamos los encabezados limpios
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

        
