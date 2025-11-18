from flask import Flask, request, render_template, redirect, session
from supabase import create_client
from datetime import datetime, timedelta
import os
import random

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)


# ==========================================
# FUNÇÃO PARA ENVIAR CÓDIGO POR E-MAIL
# ==========================================

def enviar_codigo(email, codigo):
    try:
        from resend import Emails
        Emails.send({
            "from": os.getenv("EMAIL_SENDER"),
            "to": email,
            "subject": "Seu código de confirmação - Lanzaca IA",
            "html": f"<h2>Seu código é <b>{codigo}</b></h2>"
        })
    except Exception as e:
        print("Erro ao enviar código:", e)


# ==========================================
# ROTA LOADER (TELA DE CARREGAMENTO)
# ==========================================

@app.route("/loader")
def loader():
    return render_template("loader.html")


# ==========================================
# CADASTRO DE NOVO USUÁRIO
# ==========================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":

        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        senha = request.form["senha"]
        ip = request.remote_addr

        # Verifica se alguém já usou o trial neste IP / email / telefone
        check = supabase.table("usuarios") \
            .select("*") \
            .or_(f"email.eq.{email},telefone.eq.{telefone},ip.eq.{ip}") \
            .execute()

        if check.data:
            return render_template("cadastro.html",
                                   erro="Você já usou o teste grátis anteriormente.")

        codigo = random.randint(100000, 999999)

        supabase.table("usuarios").insert({
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "senha": senha,
            "codigo": codigo,
            "confirmado": False,
            "trial_started_at": datetime.utcnow().isoformat(),
            "plano": "trial",
            "status_pagamento": "pendente",
            "ip": ip
        }).execute()

        enviar_codigo(email, codigo)

        return redirect(f"/confirmar?email={email}")

    return render_template("cadastro.html")


# ==========================================
# CONFIRMAR CÓDIGO
# ==========================================

@app.route("/confirmar", methods=["GET", "POST"])
def confirmar():
    email = request.args.get("email")

    if request.method == "POST":
        codigo_digitado = request.form["codigo"]

        dados = supabase.table("usuarios") \
            .select("*") \
            .eq("email", email).execute()

        if not dados.data:
            return "Erro inesperado"

        user = dados.data[0]

        if str(user["codigo"]) != codigo_digitado:
            return render_template("confirmar.html",
                                   email=email,
                                   erro="Código incorreto")

        # Atualiza usuário como confirmado
        supabase.table("usuarios") \
            .update({"confirmado": True}) \
            .eq("email", email).execute()

        return redirect("/login")

    return render_template("confirmar.html", email=email)


# ==========================================
# LOGIN
# ==========================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        # Busca usuário
        dados = supabase.table("usuarios") \
            .select("*") \
            .eq("email", email) \
            .eq("senha", senha) \
            .execute()

        if not dados.data:
            return render_template("login.html",
                                   erro="E-mail ou senha incorretos.")

        user = dados.data[0]

        if not user["confirmado"]:
            return render_template("login.html",
                                   erro="Confirme seu e-mail antes de entrar.")

        # Verifica se trial venceu
        inicio = datetime.fromisoformat(user["trial_started_at"])
        if datetime.utcnow() > inicio + timedelta(days=30) and user["plano"] == "trial":
            return redirect("/planos")

        # Login OK
        session["usuario_id"] = user["id"]
        session["nome"] = user["nome"]
        session["plano"] = user["plano"]

        return redirect("/painel")

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ==========================================
# PÁGINA PRINCIPAL
# ==========================================

@app.route("/painel")
def painel():
    if "usuario_id" not in session:
        return redirect("/login")

    return render_template("painel.html",
                           nome=session["nome"],
                           plano=session["plano"])


# ==========================================
# TOP 3 (BLOQUEADO PARA TRIAL)
# ==========================================

@app.route("/top3")
def top3():
    if "usuario_id" not in session:
        return redirect("/login")

    if session["plano"] == "trial":
        return render_template("bloqueado.html")

    return render_template("top3.html")


# ==========================================
# PALPITES GERAIS (TODOS VEEM)
# ==========================================

@app.route("/palpites")
def palpites():
    if "usuario_id" not in session:
        return redirect("/login")

    return render_template("top_palpites.html")


# ==========================================
# PÁGINA DOS PLANOS
# ==========================================

@app.route("/planos")
def planos():
    if "usuario_id" not in session:
        return redirect("/login")

    return render_template("planos.html")


# ==========================================
# CONFIRMAÇÃO DE PAGAMENTO
# ==========================================

@app.route("/pagamento_confirmado")
def pagamento_confirmado():
    return render_template("pagamento_confirmado.html")


# ==========================================
# EXECUTAR
# ==========================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
