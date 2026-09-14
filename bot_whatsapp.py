from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client, Client
import unicodedata
from google import genai

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN DE TUS LLAVES Y CONEXIONES
# ==========================================

# Conexión a Supabase
SUPABASE_URL = "https://uctwcciuvgonajsvfhkc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVjdHdjY2l1dmdvbmFqc3ZmaGtjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDc3ODA0NywiZXhwIjoyMDk2MzU0MDQ3fQ.RLXQTYlwBj3Cj-u76jxVxiOJFfJ5aCp3B3-iBLIeTpk" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Conexión al Cerebro de Inteligencia Artificial (Gemini)
GOOGLE_API_KEY = "AQ.Ab8RN6KuujeAgbB6-ZvER6xzUlz0ErdmSK0N7MbaHssDHW_Ygw"
cliente_ia = genai.Client(api_key=GOOGLE_API_KEY)

# ==========================================
# 2. FUNCIONES DE AYUDA
# ==========================================

def limpiar_texto(texto):
    texto_sin_acentos = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    for simbolo in ['?', '!', '.', ',', '"', "'"]:
        texto_sin_acentos = texto_sin_acentos.replace(simbolo, '')
    return texto_sin_acentos.strip().lower()

# ==========================================
# 3. LÓGICA PRINCIPAL DEL BOT (WEBHOOK)
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        mensaje_crudo = request.values.get('Body', '')
        numero_remitente = request.values.get('From', '')
        num_media = int(request.values.get('NumMedia', 0))
        tipo_mensaje = request.values.get('MessageType', 'text')
        
        respuesta = MessagingResponse()
        mensaje = respuesta.message()

        # Bloqueo de notas de voz y stickers
        if tipo_mensaje != 'text' and num_media == 0:
            mensaje.body("🤖 Por ahora solo entiendo mensajes de texto o fotos de comprobantes. ¿Me escribes tu consulta?")
            print(f"--- XML ENVIADO A TWILIO ---\n{str(respuesta)}\n----------------------------")
            return Response(str(respuesta), mimetype='application/xml')

        mensaje_entrante = limpiar_texto(mensaje_crudo)
        
        # --- BOTONES DE EMERGENCIA ---
        if "asesor" in mensaje_entrante:
            mensaje.body("🤖 Te transferiré con un asesor. Dame un momento.")
            print(f"--- XML ENVIADO A TWILIO ---\n{str(respuesta)}\n----------------------------")
            return Response(str(respuesta), mimetype='application/xml')
            
        if mensaje_entrante in ["cancelar", "vaciar", "reiniciar", "empezar de nuevo"]:
            supabase.table("carritos_activos").delete().eq("telefono", numero_remitente).execute()
            mensaje.body("🗑️ He vaciado tu pedido por completo. ¿Empezamos de cero? Dime qué buscas.")
            print(f"--- XML ENVIADO A TWILIO ---\n{str(respuesta)}\n----------------------------")
            return Response(str(respuesta), mimetype='application/xml')

        # --- VALIDACIÓN VIP ---
        es_vip = False
        resultado_vip = supabase.table("clientes_vip").select("*").eq("telefono", numero_remitente).execute()
        if resultado_vip.data:
            es_vip = True

        # --- GESTIÓN DE LA MEMORIA (CARRITO) ---
        resultado_carrito = supabase.table("carritos_activos").select("*").eq("telefono", numero_remitente).execute()
        datos_carrito = resultado_carrito.data

        saludos = ["hola", "buenas", "buenos dias", "buenas tardes", "que tal"]

        if not datos_carrito:
            supabase.table("carritos_activos").insert({"telefono": numero_remitente, "estado": "cotizando", "articulos": [], "total": 0}).execute()
            if mensaje_entrante in saludos:
                mensaje.body("¡Hola! Soy el copiloto de Tapitel. 🤖\n¿Qué material o herramienta buscas hoy?")
                print(f"--- XML ENVIADO A TWILIO ---\n{str(respuesta)}\n----------------------------")
                return Response(str(respuesta), mimetype='application/xml')
            datos_carrito = [{"telefono": numero_remitente, "estado": "cotizando", "articulos": [], "total": 0}]

        carrito = datos_carrito[0]
        estado_actual = carrito['estado']
        
        # ==========================================
        # ESTADO 1: COTIZANDO Y BUSCANDO
        # ==========================================
        if estado_actual == 'cotizando':
            if mensaje_entrante in saludos:
                if carrito['total'] > 0:
                    mensaje.body(f"¡Hola de nuevo! 🤖 Tienes un pedido pendiente por ${carrito['total']}.\n¿Qué más te agrego? O escribe 'listo' para pagar.")
                else:
                    mensaje.body("¡Hola de nuevo! 🤖 Dime, ¿qué material buscas hoy?")
                
            elif "registrado" in mensaje_entrante or "mayoreo" in mensaje_entrante:
                msg = "🤖 ¡Claro! Ya te tengo en mi lista VIP. Tus precios tienen descuento automático." if es_vip else "🤖 Aún no tengo este número registrado. Escribe *asesor* para darte de alta."
                mensaje.body(msg)
                
            elif mensaje_entrante in ["comprar", "pagar", "listo", "cerrar", "terminar"]:
                if carrito['total'] == 0:
                    mensaje.body("🤖 Tu pedido está vacío. Escribe 'agregar [material]' para empezar.")
                else:
                    supabase.table("carritos_activos").update({"estado": "pagando"}).eq("telefono", numero_remitente).execute()
                    texto_pago = (
                        f"📝 *Resumen de tu pedido*\nTotal: ${carrito['total']}\n\n"
                        "Para asegurar tu material, requerimos el pago por transferencia.\n"
                        "🏦 BBVA | Cuenta: 1234567890 | Tapitel\n\n"
                        "📸 *Envíame la foto del comprobante por aquí.*\n"
                        "*(Si pagarás en efectivo en el mostrador, escribe 'efectivo')*"
                    )
                    mensaje.body(texto_pago)
                    
            elif mensaje_entrante.startswith("agregar"):
                producto = mensaje_entrante.replace("agregar", "").strip()
                resultado = supabase.table("inventario_tapitel").select("*").ilike("producto", f"%{producto}%").limit(1).execute()
                
                if resultado.data:
                    item = resultado.data[0]
                    existencia = item.get("existencia", 0)
                    precio = item.get("p_mayoreo", item.get("p_venta", 0)) if es_vip else item.get("p_venta", 0)
                    
                    if existencia <= 0:
                        mensaje.body(f"❌ Lo siento, {item['producto']} se encuentra agotado.")
                    else:
                        nuevo_total = carrito['total'] + precio
                        nuevos_articulos = carrito['articulos'] + [item['producto']]
                        supabase.table("carritos_activos").update({"articulos": nuevos_articulos, "total": nuevo_total}).eq("telefono", numero_remitente).execute()
                        mensaje.body(f"✅ *Agregado:* {item['producto']} (${precio})\n💰 *Total actual:* ${nuevo_total}\n\nPara cerrar tu pedido escribe *listo*, o busca otro material.")
                else:
                    mensaje.body("🤖 No encontré ese producto. Escríbelo exactamente como te lo indiqué en las sugerencias.")
                    
            else:
                # --- AQUÍ ENTRA LA INTELIGENCIA ARTIFICIAL (GEMINI) ---
                datos_inv = supabase.table("inventario_tapitel").select("producto, p_venta, p_mayoreo, existencia").execute().data
                
                catalogo_texto = ""
                for item in datos_inv:
                    if item['existencia'] > 0:
                        precio = item['p_mayoreo'] if es_vip else item['p_venta']
                        catalogo_texto += f"- {item['producto']} (Precio: ${precio})\n"
                
                prompt = f"""Eres el copiloto experto de ventas de Tapitel, una tienda de materiales de tapicería.
                
                Este es tu inventario exacto y actualizado de hoy:
                {catalogo_texto}
                
                El cliente te acaba de decir esto: "{mensaje_entrante}"
                
                Tus reglas estrictas:
                1. Analiza lo que pide. Si busca "esponja de 2 pulgadas", revisa el inventario y menciónale las diferentes densidades que tenemos en esa medida.
                2. Si pide algo que no tenemos exacto, ofrécele la alternativa más lógica que sí tengamos en el inventario.
                3. NUNCA inventes productos ni precios que no estén en la lista del inventario de hoy.
                4. Háblale de forma natural, amable y concisa (máximo 3 párrafos cortos). Usa viñetas para listar opciones.
                5. Al final de tu respuesta, indícale siempre que para confirmar el pedido debe escribir la palabra "agregar" seguida del nombre exacto del producto como aparece en el inventario.
                """
                
                respuesta_gemini = cliente_ia.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=prompt,
                )
                mensaje.body(respuesta_gemini.text)

        # ==========================================
        # ESTADO 2: PAGANDO
        # ==========================================
        elif estado_actual == 'pagando':
            if num_media > 0 or "efectivo" in mensaje_entrante:
                supabase.table("carritos_activos").update({"estado": "entrega"}).eq("telefono", numero_remitente).execute()
                if "efectivo" in mensaje_entrante:
                    mensaje.body("✅ Anotado: Pago en efectivo al recoger.\n\n¿Deseas envío *a domicilio* o prefieres *recoger* en mostrador?")
                else:
                    mensaje.body("✅ Comprobante recibido.\n\n¿Deseas envío *a domicilio* o prefieres *recoger* en mostrador?")
            else:
                mensaje.body("🤖 Aún espero tu comprobante (o escribe 'efectivo' si pagarás en mostrador).")

        # ==========================================
        # ESTADO 3: ENTREGA Y CIERRE
        # ==========================================
        elif estado_actual == 'entrega':
            tipo_entrega = ""
            if "domicilio" in mensaje_entrante:
                tipo_entrega = "Domicilio"
                mensaje.body("🚚 Perfecto. Compártenos tu ubicación o dirección completa por aquí para coordinar la ruta.\n\n¡Gracias por tu compra en Tapitel! 🛠️")
            elif "recoger" in mensaje_entrante or "mostrador" in mensaje_entrante:
                tipo_entrega = "Mostrador"
                mensaje.body("🏪 ¡Perfecto! Tu material quedará separado. Te esperamos a partir de las 12:30 pm.\n\n¡Gracias por tu compra en Tapitel! 🛠️")
            
            if tipo_entrega:
                try:
                    supabase.table("pedidos_completados").insert({
                        "telefono": numero_remitente,
                        "articulos": carrito['articulos'],
                        "total": carrito['total'],
                        "entrega": tipo_entrega
                    }).execute()
                except Exception as e:
                    print("Error guardando historial de pedido:", e)
                    
                supabase.table("carritos_activos").delete().eq("telefono", numero_remitente).execute()
            else:
                mensaje.body("🤖 Por favor, responde únicamente si prefieres envío *a domicilio* o *recoger* en tienda para terminar.")

        # --- IMPRESIÓN DE DEPURACIÓN FINAL ---
        print(f"--- XML ENVIADO A TWILIO ---\n{str(respuesta)}\n----------------------------")
        return Response(str(respuesta), mimetype='application/xml')

    except Exception as e:
        print(f"Error crítico capturado: {e}")
        respuesta_emergencia = MessagingResponse()
        respuesta_emergencia.message("🤖 Tuve un pequeño inconveniente procesando los datos. Escribe *cancelar* para reiniciar el pedido, o *asesor* para ayuda manual.")
        print(f"--- XML DE EMERGENCIA ENVIADO A TWILIO ---\n{str(respuesta_emergencia)}\n----------------------------")
        return Response(str(respuesta_emergencia), mimetype='application/xml')

if __name__ == '__main__':
    print("🚀 Copiloto Tapitel con IA activado. Esperando mensajes...")
    app.run(port=5000, debug=True)

    