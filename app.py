"""
NEXUS.CLINIC — Backend com 10 Agentes Autônomos de IA
======================================================
Deploy: Render, Railway, ou qualquer servidor Python
Banco: Supabase (PostgreSQL)
"""

import os
import json
import random
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO
# ============================================================
app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://seu-projeto.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sua-chave-anon")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# DEFINIÇÃO DOS 10 AGENTES
# ============================================================
AGENTS = [
    {
        "id": "cerebro",
        "name": "Cérebro Neural",
        "emoji": "🧠",
        "color": "#ff00aa",
        "role": "orquestrador",
        "description": "Roteia mensagens para o agente correto usando análise de intenção.",
        "triggers": ["*"]
    },
    {
        "id": "recepcionista",
        "name": "Recepcionista",
        "emoji": "👩‍⚕️",
        "color": "#00f0ff",
        "role": "recepcionista",
        "description": "Cadastra pacientes, coleta dados e dá boas-vindas.",
        "triggers": ["cadastrar", "novo paciente", "meu nome", "quero ser paciente", "primeira vez", "dados", "cadastro"]
    },
    {
        "id": "agendador",
        "name": "Agendador",
        "emoji": "📅",
        "color": "#2196F3",
        "role": "agendador",
        "description": "Marca, remarca e cancela consultas. Verifica disponibilidade.",
        "triggers": ["agendar", "marcar", "consulta", "horário", "disponível", "remarcar", "cancelar", "quando", "data"]
    },
    {
        "id": "financeiro",
        "name": "Financeiro",
        "emoji": "💰",
        "color": "#FF9800",
        "role": "financeiro",
        "description": "Gera boletos, consulta débitos, planos e orçamentos.",
        "triggers": ["preço", "valor", "custo", "orçamento", "boleto", "pagamento", "dinheiro", "cartão", "pix", "débito", "crédito", "plano"]
    },
    {
        "id": "marketing",
        "name": "Marketing",
        "emoji": "📢",
        "color": "#9C27B0",
        "role": "marketing",
        "description": "Capta leads, campanhas, promoções e fidelização.",
        "triggers": ["promoção", "desconto", "campanha", "indicação", "instagram", "google", "facebook", "lead", "cupom"]
    },
    {
        "id": "estoque",
        "name": "Estoque",
        "emoji": "📦",
        "color": "#795548",
        "role": "estoque",
        "description": "Controla materiais, alerta reposição e fornecedores.",
        "triggers": ["estoque", "material", "luva", "anestésico", "reposição", "falta", "comprar", "fornecedor"]
    },
    {
        "id": "lembretes",
        "name": "Lembretes",
        "emoji": "⏰",
        "color": "#ffcc00",
        "role": "lembretes",
        "description": "Envia confirmações, lembretes de consulta e pós-operatório.",
        "triggers": ["lembrar", "confirmar", "avisar", "notificação", "lembrete", "próxima consulta", "retorno"]
    },
    {
        "id": "triagem",
        "name": "Triagem",
        "emoji": "🩺",
        "color": "#00ff88",
        "role": "triagem",
        "description": "Pré-avalia clínica, sintomas e encaminha ao dentista certo.",
        "triggers": ["dor", "sangrando", "inchaço", "carie", "canal", "extração", "limpeza", "clareamento", "aparelho", "sensível", "dente", "gengiva"]
    },
    {
        "id": "diretor",
        "name": "Diretor",
        "emoji": "📊",
        "color": "#aa66ff",
        "role": "diretor",
        "description": "Dashboard, KPIs, relatórios e tomada de decisão.",
        "triggers": ["relatório", "dashboard", "kpi", "faturamento", "meta", "lucro", "receita", "despesa", "relatório"]
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp",
        "emoji": "💬",
        "color": "#25D366",
        "role": "whatsapp",
        "description": "Interface de comunicação via WhatsApp Business API.",
        "triggers": ["whatsapp", "mensagem", "falar", "atendente", "humano", "reclamação"]
    }
]

# ============================================================
# UTILITÁRIOS
# ============================================================
def log_action(agent_id, action, details=""):
    """Registra ação no log de operações."""
    try:
        supabase.table("agent_logs").insert({
            "agent_id": agent_id,
            "action": action,
            "details": details,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[LOG ERROR] {e}")

def save_memory(agent_role, type_, content, phone=None):
    """Salva memória no cérebro neural."""
    try:
        supabase.table("brain_memory").insert({
            "agent_role": agent_role,
            "type": type_,
            "content": content,
            "phone": phone,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[MEMORY ERROR] {e}")

def create_synapse(from_agent, to_agent, trigger_event):
    """Cria sinapse (notificação entre agentes)."""
    try:
        supabase.table("brain_synapses").insert({
            "from_agent": from_agent,
            "to_agent": to_agent,
            "trigger_event": trigger_event,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[SYNAPSE ERROR] {e}")

def get_patient_by_phone(phone):
    """Busca paciente pelo telefone."""
    try:
        res = supabase.table("patients").select("*").eq("phone", phone).execute()
        return res.data[0] if res.data else None
    except:
        return None

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ============================================================
# CÉREBRO NEURAL — ROTEADOR DE INTENÇÃO
# ============================================================
def cerebro_route(text):
    """
    Analisa o texto e retorna o agente mais adequado.
    Fallback para Recepcionista se não identificar.
    """
    text_lower = text.lower()
    scores = {}

    for agent in AGENTS:
        if agent["id"] == "cerebro":
            continue
        score = 0
        for trigger in agent["triggers"]:
            if trigger in text_lower:
                score += 1
        if score > 0:
            scores[agent["id"]] = score

    if scores:
        best = max(scores, key=scores.get)
        return best
    return "recepcionista"  # fallback

# ============================================================
# LÓGICA DE CADA AGENTE
# ============================================================

def agent_recepcionista(phone, text):
    patient = get_patient_by_phone(phone)

    if not patient:
        # Novo paciente — coletar dados
        reply = (
            "👩‍⚕️ *Recepcionista NEXUS*

"
            "Olá! Seja bem-vindo à NEXUS.CLINIC.
"
            "Vou cadastrar você agora. Por favor, me envie:

"
            "1️⃣ Nome completo
"
            "2️⃣ Data de nascimento (DD/MM/AAAA)
"
            "3️⃣ Convênio (Particular, Unimed, etc.)

"
            "Ou acesse o painel: https://seusite.com"
        )
        save_memory("recepcionista", "lead_capture", f"Novo contato: {phone}", phone)
        return reply

    reply = (
        f"👩‍⚕️ *Recepcionista NEXUS*

"
        f"Olá, {patient.get('name', 'paciente')}!
"
        f"Como posso ajudar hoje?

"
        f"Digite:
"
        f"• *agendar* — marcar consulta
"
        f"• *preço* — valores e orçamentos
"
        f"• *meus dados* — ver cadastro"
    )
    save_memory("recepcionista", "greeting", f"Saudação para {patient.get('name')}", phone)
    return reply

def agent_agendador(phone, text):
    patient = get_patient_by_phone(phone)
    if not patient:
        return "📅 *Agendador*

Preciso cadastrar você primeiro. Digite *cadastrar*."

    # Simular verificação de horários
    tomorrow = datetime.now() + timedelta(days=1)
    horarios = ["09:00", "10:30", "14:00", "15:30", "17:00"]

    reply = (
        f"📅 *Agendador NEXUS*

"
        f"Olá, {patient.get('name')}!
"
        f"Horários disponíveis para *{tomorrow.strftime('%d/%m')}*:

"
        + "
".join([f"• {h}" for h in horarios]) +
        f"

Qual horário prefere?
"
        f"Também me diga o procedimento (Limpeza, Canal, Extração, etc.)"
    )
    save_memory("agendador", "availability_check", f"Consultado horários para {phone}", phone)
    return reply

def agent_financeiro(phone, text):
    patient = get_patient_by_phone(phone)

    # Buscar débitos
    try:
        debits = supabase.table("financial").select("*").eq("patient_phone", phone).eq("type", "expense").execute()
        total_debit = sum([d["amount"] for d in debits.data]) if debits.data else 0
    except:
        total_debit = 0

    reply = (
        f"💰 *Financeiro NEXUS*

"
        f"Tabela de preços:
"
        f"• Consulta inicial: R$ 150,00
"
        f"• Limpeza: R$ 200,00
"
        f"• Canal: R$ 800,00
"
        f"• Extração: R$ 300,00
"
        f"• Clareamento: R$ 1.200,00
"
        f"• Aparelho: R$ 3.500,00

"
    )

    if total_debit > 0:
        reply += f"⚠️ Você tem um débito de *{format_currency(total_debit)}*
"

    reply += "
Formas de pagamento: Pix, Cartão (até 12x), Dinheiro (5% desc.)"
    save_memory("financeiro", "pricing_query", f"Consultado preços por {phone}", phone)
    return reply

def agent_marketing(phone, text):
    reply = (
        f"📢 *Marketing NEXUS*

"
        f"🎉 *PROMOÇÃO DO MÊS*
"
        f"Clareamento a laser + Limpeza = *R$ 999,00*
"
        f"(de R$ 1.400,00)

"
        f"💎 Programa de Indicação:
"
        f"Indique um amigo e ganhe *R$ 50* de desconto!

"
        f"📲 Siga no Instagram: @nexus.clinic
"
        f"Cupom: *NEXUS10* (10% off na 1ª consulta)"
    )
    save_memory("marketing", "promotion", f"Enviado promoções para {phone}", phone)
    return reply

def agent_estoque(phone, text):
    try:
        stock = supabase.table("stock").select("*").execute()
        low_items = [s for s in stock.data if s.get("status") != "ok"] if stock.data else []
    except:
        low_items = []

    if low_items:
        reply = (
            f"📦 *Estoque NEXUS*

"
            f"⚠️ *Itens com estoque baixo:*
"
            + "
".join([f"• {item['item']}: {item['quantity']} un (mín: {item['min_level']})" for item in low_items[:5]])
            + "

Solicitando reposição aos fornecedores..."
        )
    else:
        reply = (
            f"📦 *Estoque NEXUS*

"
            f"✅ Todos os materiais em nível adequado.
"
            f"Última verificação: {datetime.now().strftime('%d/%m %H:%M')}"
        )
    save_memory("estoque", "stock_check", f"Verificado estoque por {phone}", phone)
    return reply

def agent_lembretes(phone, text):
    patient = get_patient_by_phone(phone)
    if not patient:
        return "⏰ *Lembretes*

Cadastre-se primeiro para receber lembretes."

    try:
        appts = supabase.table("appointments").select("*").eq("patient_phone", phone).gte("date", datetime.now().strftime("%Y-%m-%d")).execute()
        next_appt = appts.data[0] if appts.data else None
    except:
        next_appt = None

    if next_appt:
        reply = (
            f"⏰ *Lembretes NEXUS*

"
            f"✅ Próxima consulta confirmada!
"
            f"📅 {next_appt['date']} às {next_appt['time']}
"
            f"🦷 {next_appt['procedure']}
"
            f"👨‍⚕️ {next_appt['dentist']}

"
            f"Lembre-se de chegar 15 min antes.
"
            f"Cancelamentos com menos de 24h: taxa de 50%."
        )
    else:
        reply = (
            f"⏰ *Lembretes NEXUS*

"
            f"Você não tem consultas agendadas.
"
            f"Digite *agendar* para marcar uma!"
        )
    save_memory("lembretes", "reminder_sent", f"Lembrete enviado para {phone}", phone)
    return reply

def agent_triagem(phone, text):
    text_lower = text.lower()

    # Análise simples de sintomas
    urgency = "normal"
    if any(w in text_lower for w in ["muito dor", "sangrando muito", "inchaço", "infeccao", "abscesso"]):
        urgency = "alta"

    if urgency == "alta":
        reply = (
            f"🩺 *Triagem NEXUS*

"
            f"⚠️ *CASO PRIORITÁRIO*

"
            f"Identifiquei sintomas que precisam de atenção imediata.

"
            f"🏥 *Você tem duas opções:*
"
            f"1. Venha HOJE — temos vaga de emergência
"
            f"2. Ligue: (11) 99999-9999

"
            f"Não ignore dor intensa ou inchaço facial."
        )
    else:
        reply = (
            f"🩺 *Triagem NEXUS*

"
            f"Entendi seu relato. Baseado nos sintomas:

"
            f"• Se for dor leve/sensibilidade → *Consulta de avaliação*
"
            f"• Se for dor intensa/inchaço → *Emergência odontológica*
"
            f"• Se for estética → *Avaliação de sorriso*

"
            f"Quer que eu agende uma consulta de avaliação?"
        )
    save_memory("triagem", "symptom_analysis", f"Triagem: {text[:50]}...", phone)
    return reply

def agent_diretor(phone, text):
    try:
        # KPIs do dia
        today = datetime.now().strftime("%Y-%m-%d")
        appts = supabase.table("appointments").select("*").eq("date", today).execute()
        patients = supabase.table("patients").select("*").execute()
        fin = supabase.table("financial").select("*").execute()

        total_revenue = sum([f["amount"] for f in fin.data if f["type"] == "revenue"]) if fin.data else 0
        total_expense = sum([f["amount"] for f in fin.data if f["type"] == "expense"]) if fin.data else 0

        reply = (
            f"📊 *Diretor NEXUS*

"
            f"*Resumo do dia:*
"
            f"• Consultas hoje: {len(appts.data) if appts.data else 0}
"
            f"• Pacientes cadastrados: {len(patients.data) if patients.data else 0}
"
            f"• Receita: {format_currency(total_revenue)}
"
            f"• Despesas: {format_currency(total_expense)}
"
            f"• Lucro: {format_currency(total_revenue - total_expense)}

"
            f"Meta do mês: R$ 50.000,00
"
            f"Progresso: {((total_revenue/50000)*100):.1f}%"
        )
    except Exception as e:
        reply = f"📊 *Diretor NEXUS*

Dados em processamento. Tente pelo painel web."

    save_memory("diretor", "dashboard_query", f"Dashboard consultado por {phone}", phone)
    return reply

def agent_whatsapp(phone, text):
    reply = (
        f"💬 *Atendimento NEXUS*

"
        f"Vou transferir você para um atendente humano.
"
        f"⏳ *Tempo estimado: 5 minutos*

"
        f"Enquanto isso, posso ajudar com:
"
        f"• Agendamento automático
"
        f"• Tabela de preços
"
        f"• Localização da clínica

"
        f"Digite *voltar* para falar com os agentes de IA."
    )
    save_memory("whatsapp", "human_handoff", f"Solicitado atendente humano: {phone}", phone)
    return reply

# ============================================================
# ROTEAMENTO CENTRAL
# ============================================================
AGENT_HANDLERS = {
    "recepcionista": agent_recepcionista,
    "agendador": agent_agendador,
    "financeiro": agent_financeiro,
    "marketing": agent_marketing,
    "estoque": agent_estoque,
    "lembretes": agent_lembretes,
    "triagem": agent_triagem,
    "diretor": agent_diretor,
    "whatsapp": agent_whatsapp,
}

def process_message(phone, text):
    """Processa mensagem pelo Cérebro Neural."""
    agent_id = cerebro_route(text)
    handler = AGENT_HANDLERS.get(agent_id, agent_recepcionista)

    reply = handler(phone, text)

    # Log e memória
    log_action(agent_id, "message_processed", f"Phone: {phone}, Text: {text[:50]}")
    save_memory("cerebro", "routing", f"Roteou '{text[:30]}...' -> {agent_id}", phone)

    # Sinapses: notificar outros agentes
    if agent_id == "recepcionista":
        create_synapse("recepcionista", "marketing", "Novo paciente cadastrado")
    elif agent_id == "agendador":
        create_synapse("agendador", "lembretes", "Nova consulta agendada")
        create_synapse("agendador", "estoque", "Verificar materiais para procedimento")
    elif agent_id == "financeiro":
        create_synapse("financeiro", "diretor", "Nova movimentação financeira")

    return {"agent": AGENTS_DICT[agent_id]["name"], "role": agent_id, "reply": reply}

AGENTS_DICT = {a["id"]: a for a in AGENTS}

# ============================================================
# ENDPOINTS DA API
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agents": len(AGENTS), "version": "1.0.0"})

@app.route("/api/agents", methods=["GET"])
def get_agents():
    return jsonify(AGENTS)

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    try:
        patients = supabase.table("patients").select("*", count="exact").execute()
        appts = supabase.table("appointments").select("*", count="exact").execute()
        fin = supabase.table("financial").select("*").execute()
        leads = supabase.table("leads").select("*", count="exact").execute()
        stock = supabase.table("stock").select("*").execute()
        msgs = supabase.table("brain_memory").select("*", count="exact").execute()

        today = datetime.now().strftime("%Y-%m-%d")
        today_appts = [a for a in (appts.data or []) if a.get("date") == today]
        low_stock = [s for s in (stock.data or []) if s.get("status") != "ok"]

        revenue = sum([f["amount"] for f in (fin.data or []) if f["type"] == "revenue"])
        expenses = sum([f["amount"] for f in (fin.data or []) if f["type"] == "expense"])

        return jsonify({
            "total_patients": patients.count if hasattr(patients, 'count') else len(patients.data or []),
            "total_appointments": appts.count if hasattr(appts, 'count') else len(appts.data or []),
            "today_appointments": len(today_appts),
            "total_messages": msgs.count if hasattr(msgs, 'count') else len(msgs.data or []),
            "total_leads": leads.count if hasattr(leads, 'count') else len(leads.data or []),
            "revenue": revenue,
            "expenses": expenses,
            "stock_alerts": len(low_stock)
        })
    except Exception as e:
        return jsonify({
            "total_patients": 0, "total_appointments": 0, "today_appointments": 0,
            "total_messages": 0, "total_leads": 0, "revenue": 0, "expenses": 0, "stock_alerts": 0,
            "error": str(e)
        })

@app.route("/api/bot/message", methods=["POST"])
def bot_message():
    data = request.get_json() or {}
    phone = data.get("phone", "")
    text = data.get("text", "")
    if not phone or not text:
        return jsonify({"error": "phone and text required"}), 400
    result = process_message(phone, text)
    return jsonify(result)

@app.route("/api/agent/<role>", methods=["POST"])
def agent_direct(role):
    data = request.get_json() or {}
    phone = data.get("phone", "5511999999999")
    text = data.get("text", "teste")
    handler = AGENT_HANDLERS.get(role, agent_recepcionista)
    reply = handler(phone, text)
    return jsonify({"agent": AGENTS_DICT.get(role, {}).get("name", role), "role": role, "reply": reply})

# --- CRUD PACIENTES ---
@app.route("/api/patients", methods=["GET", "POST"])
def patients():
    if request.method == "POST":
        data = request.get_json() or {}
        data["created_at"] = datetime.utcnow().isoformat()
        try:
            res = supabase.table("patients").insert(data).execute()
            log_action("recepcionista", "patient_created", data.get("name", ""))
            create_synapse("recepcionista", "marketing", f"Novo paciente: {data.get('name')}")
            return jsonify(res.data[0] if res.data else {"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            res = supabase.table("patients").select("*").order("created_at", desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            return jsonify([])

# --- CRUD CONSULTAS ---
@app.route("/api/appointments", methods=["GET", "POST"])
def appointments():
    if request.method == "POST":
        data = request.get_json() or {}
        data["created_at"] = datetime.utcnow().isoformat()
        data["status"] = data.get("status", "scheduled")
        try:
            res = supabase.table("appointments").insert(data).execute()
            log_action("agendador", "appointment_created", data.get("procedure", ""))
            create_synapse("agendador", "lembretes", f"Consulta agendada: {data.get('procedure')}")
            return jsonify(res.data[0] if res.data else {"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            res = supabase.table("appointments").select("*, patients(name)").order("date", desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            return jsonify([])

# --- CRUD FINANCEIRO ---
@app.route("/api/financial", methods=["GET", "POST"])
def financial():
    if request.method == "POST":
        data = request.get_json() or {}
        data["created_at"] = datetime.utcnow().isoformat()
        try:
            res = supabase.table("financial").insert(data).execute()
            log_action("financeiro", "transaction_created", f"{data.get('type')} {data.get('amount')}")
            create_synapse("financeiro", "diretor", f"Nova {data.get('type')}: R$ {data.get('amount')}")
            return jsonify(res.data[0] if res.data else {"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            res = supabase.table("financial").select("*").order("created_at", desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            return jsonify([])

# --- CRUD LEADS ---
@app.route("/api/leads", methods=["GET", "POST"])
def leads():
    if request.method == "POST":
        data = request.get_json() or {}
        data["created_at"] = datetime.utcnow().isoformat()
        data["status"] = data.get("status", "new")
        try:
            res = supabase.table("leads").insert(data).execute()
            log_action("marketing", "lead_created", data.get("name", ""))
            return jsonify(res.data[0] if res.data else {"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            res = supabase.table("leads").select("*").order("created_at", desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            return jsonify([])

# --- CRUD ESTOQUE ---
@app.route("/api/stock", methods=["GET", "POST"])
def stock():
    if request.method == "POST":
        data = request.get_json() or {}
        data["created_at"] = datetime.utcnow().isoformat()
        qty = data.get("quantity", 0)
        min_lvl = data.get("min_level", 0)
        data["status"] = "ok" if qty >= min_lvl else "low"
        try:
            res = supabase.table("stock").insert(data).execute()
            log_action("estoque", "stock_added", data.get("item", ""))
            if data["status"] == "low":
                create_synapse("estoque", "diretor", f"Estoque baixo: {data.get('item')}")
            return jsonify(res.data[0] if res.data else {"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            res = supabase.table("stock").select("*").order("created_at", desc=True).execute()
            return jsonify(res.data or [])
        except Exception as e:
            return jsonify([])

# --- CÉREBRO: MEMÓRIA E SINAPSES ---
@app.route("/api/brain/memory", methods=["GET"])
def brain_memory():
    try:
        res = supabase.table("brain_memory").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(res.data or [])
    except:
        return jsonify([])

@app.route("/api/brain/synapses", methods=["GET"])
def brain_synapses():
    try:
        res = supabase.table("brain_synapses").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(res.data or [])
    except:
        return jsonify([])

# ============================================================
# INICIALIZAÇÃO
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
