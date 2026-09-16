import os
from flask import Flask, request, jsonify
from supabase import create_client, Client
from google import genai # <--- ¡Librería nueva!

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN DE CREDENCIALES
# ==========================================
SUPABASE_URL = "https://uctwcciuvgonajsvfhkc.supabase.co"  
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjdHdjY2l1dmdvbmFqc3ZmaGtjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDc3ODA0NywiZXhwIjoyMDk2MzU0MDQ3fQ.RLXQTYlwBj3Cj-u76jxVxiOJFfJ5aCp3B3-iBLIeTpk"
GEMINI_API_KEY = "AQ.Ab8RN6LWvCO5giXroJMHmS7QQIJvVr95AAwIMpwVTr30hSQjoQ"

# Inicializar conexión a la base de datos
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inicializar IA con el nuevo cliente oficial
client = genai.Client(api_key=GEMINI_API_KEY)

@app.route('/webhook', methods=['POST'])
def webhook():
    datos = request.get_json()
    
    if not datos:
        return jsonify({"error": "Formato incorrecto, se esperaba JSON"}), 400

    mensaje_entrante = datos.get('mensaje', '').strip()
    numero_cliente = datos.get('numero', 'Desconocido')

    if not mensaje_entrante:
        return jsonify({"respuesta": "No pude leer tu mensaje. ¿En qué te ayudo?"})

    # flush=True hace que el texto aparezca de inmediato en los logs de Render
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

        # Generar respuesta con la nueva sintaxis
        respuesta_ia = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt_sistema
        )
        respuesta_final = respuesta_ia.text.strip()

    except Exception as e:
        print(f"Error interno en el servidor: {e}", flush=True)
        respuesta_final = "Una disculpa, estoy revisando el almacén y tuve un pequeño problema técnico. ¿Me puedes repetir tu pregunta?"

    return jsonify({"respuesta": respuesta_final})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
