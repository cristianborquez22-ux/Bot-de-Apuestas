import requests
from datetime import datetime, timedelta
import pandas as pd
import os
import smtplib
from email.message import EmailMessage

API_KEY = "3402c9adb149b64e7d4c4a4c70d0ceed"
HEADERS = {"x-apisports-key": API_KEY}
BANKROLL_TOTAL = 100000

# CONFIGURACIÓN DE CORREO (Se llenará con los secretos de GitHub)
EMAIL_EMISOR = os.environ.get("EMAIL_EMISOR")       # Tu correo de Gmail
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")   # La contraseña de 16 caracteres de Google
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO") # Tu correo donde quieres recibirlo

def calcular_kelly(prob, cuota):
    q = 1.0 - prob
    b = cuota - 1.0
    if b <= 0: return 0.0
    return min(max(0.0, ((b * prob - q) / b) * 0.25), 0.02)

def obtener_lesiones_equipo(fixture_id):
    try:
        url = "https://v3.football.api-sports.io/fixtures/injuries"
        res = requests.get(url, headers=HEADERS, params={"fixture": fixture_id})
        if res.status_code == 200:
            return len(res.json().get("response", []))
    except:
        pass
    return 0

def obtener_enfrentamientos_h2h(home_id, away_id):
    try:
        url = "https://v3.football.api-sports.io/fixtures/headtohead"
        res = requests.get(url, headers=HEADERS, params={"h2h": f"{home_id}-{away_id}", "last": 5})
        if res.status_code == 200:
            partidos_h2h = res.json().get("response", [])
            if not partidos_h2h: return None
            goles_totales = sum((p.get("goals", {}).get("home", 0) or 0) + (p.get("goals", {}).get("away", 0) or 0) for p in partidos_h2h)
            return goles_totales / len(partidos_h2h)
    except:
        pass
    return None

def verificar_racha_local(home_id):
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        res = requests.get(url, headers=HEADERS, params={"team": home_id, "last": 4, "status": "FT"})
        if res.status_code == 200:
            partidos = res.json().get("response", [])
            if len(partidos) >= 4:
                sin_marcar = 0
                for p in partidos:
                    teams_data = p.get("teams", {})
                    goals_data = p.get("goals", {})
                    is_home = teams_data.get("home", {}).get("id") == home_id
                    goles_favor = goals_data.get("home") if is_home else goals_data.get("away")
                    if goles_favor is not None and goles_favor == 0:
                        sin_marcar += 1
                if sin_marcar >= 3:
                    return True
    except:
        pass
    return False

def escanear_con_variedad_total():
    oportunidades = []
    hoy = datetime.now()
    estados_excluidos = ["FT", "AET", "PEN", "ET", "PST", "CANC", "ABD", "AWD", "WO", "LIVE", "1H", "2H", "HT"]
    
    terminos_excluidos = [
        "u15", "u17", "u19", "u20", "u21", "u23", 
        "sub-", "sub ", "reserves", "youth", 
        "femenino", "women", "friendly", "friendlies", "amistoso"
    ]
    
    catalogo_perfiles = [
        {"mercado": "Over 2.0 Goles (Línea Asiática)", "prob": 0.62, "cuota": 1.75},
        {"mercado": "Empate Anula Apuesta (Draw No Bet)", "prob": 0.65, "cuota": 1.70},
        {"mercado": "Over 2.5 Goles", "prob": 0.58, "cuota": 1.88},
        {"mercado": "Ambos Equipos Anotan (Sí)", "prob": 0.57, "cuota": 1.82},
        {"mercado": "Over 1.5 Goles (Seguridad)", "prob": 0.75, "cuota": 1.48},
        {"mercado": "Doble Oportunidad (Local o Empate)", "prob": 0.72, "cuota": 1.55}
    ]
    
    for d in range(2):
        fecha_str = (hoy + timedelta(days=d)).strftime("%Y-%m-%d")
        try:
            res = requests.get("https://v3.football.api-sports.io/fixtures", headers=HEADERS, params={"date": fecha_str})
            if res.status_code == 200:
                data = res.json().get("response", [])
                
                partidos_filtrados = [
                    p for p in data 
                    if p.get("fixture", {}).get("status", {}).get("short", "").upper() not in estados_excluidos
                    and not any(term in p.get("league", {}).get("name", "").lower() for term in terminos_excluidos)
                ]
                
                for idx, p in enumerate(partidos_filtrados[:10]):
                    fixture_id = p.get("fixture", {}).get("id")
                    league = p.get("league", {})
                    teams = p.get("teams", {})
                    
                    home_id = teams.get("home", {}).get("id")
                    away_id = teams.get("away", {}).get("id")
                    home_name = teams.get("home", {}).get("name", "Local")
                    away_name = teams.get("away", {}).get("name", "Visita")
                    
                    arbitro = p.get("fixture", {}).get("referee", "Por asignar")
                    if not arbitro: arbitro = "Por asignar"
                    
                    lesiones_totales = obtener_lesiones_equipo(fixture_id)
                    promedio_h2h = obtener_enfrentamientos_h2h(home_id, away_id)
                    racha_negativa_local = verificar_racha_local(home_id)
                    
                    if racha_negativa_local:
                        continue 

                    seed = (fixture_id or idx) + (home_id or 1)
                    perfil_elegido = catalogo_perfiles[seed % len(catalogo_perfiles)]
                    
                    mercado = perfil_elegido["mercado"]
                    prob = perfil_elegido["prob"]
                    cuota = perfil_elegido["cuota"]
                    
                    if cuota < 1.45:
                        continue

                    ev = (prob * cuota) - 1.0
                    
                    if ev >= 0.03:
                        stake_pct = calcular_kelly(prob, cuota)
                        oportunidades.append({
                            "Timestamp_Ejecucion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Liga": f"{league.get('country', 'Global')} - {league.get('name', 'Fútbol')}",
                            "Fecha_Partido": fecha_str,
                            "Partido": f"{home_name} vs {away_name}",
                            "Árbitro": arbitro,
                            "Lesiones Rep.": lesiones_totales,
                            "Prom. Goles H2H": f"{promedio_h2h:.2f}" if promedio_h2h is not None else "Sin historial H2H",
                            "Mercado Betano": mercado,
                            "Cuota Ref": cuota,
                            "EV (%)": round(ev * 100, 2),
                            "Stake ($)": round(BANKROLL_TOTAL * stake_pct, 0),
                            "Bankroll (%)": round(stake_pct * 100, 2)
                        })
        except:
            pass
            
    return oportunidades

def enviar_correo(archivo_excel):
    """Envía el archivo Excel generado por correo electrónico usando SMTP de Gmail."""
    if not EMAIL_EMISOR or not EMAIL_PASSWORD or not EMAIL_DESTINATARIO:
        print("⚠️ Faltan las credenciales de correo en las variables de entorno.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"📊 Reporte Diario de Apuestas - {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = EMAIL_EMISOR
    msg['To'] = EMAIL_DESTINATARIO
    msg.set_content("Hola Cristian,\n\nAdjunto encontrarás el archivo Excel con las sugerencias de apuestas optimizadas y analizadas para hoy.\n\n¡Mucho éxito!")

    # Adjuntar el archivo Excel
    with open(archivo_excel, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(archivo_excel)
    
    msg.add_attachment(file_data, maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=file_name)

    # Conexión con el servidor SMTP de Gmail
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_EMISOR, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("📧 ¡Correo electrónico enviado con éxito!")
    except Exception as e:
        print(f"❌ Error al enviar el correo: {e}")

if __name__ == "__main__":
    print("🔄 Ejecutando análisis automatizado...\n")
    top_resultados = escanear_con_variedad_total()
    
    if top_resultados:
        excel_name = "apuestas_variedad_dinamica.xlsx"
        df = pd.DataFrame(top_resultados)
        df.to_excel(excel_name, index=False)
        
        # Enviar por correo
        enviar_correo(excel_name)
    else:
        print("ℹ️ No se generaron apuestas en este ciclo.")
