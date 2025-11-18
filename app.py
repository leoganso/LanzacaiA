from flask import Flask, render_template, request, redirect, session
from supabase import create_client
from datetime import datetime, timedelta
import os
import random
from resend import Emails

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# ------------------------
#   SUPABASE
# ------------------------
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(supabase_url, supabase_key)

# ------------------------
# Função: enviar código
# ------------------------
def enviar_codigo(email, codigo):
    Emails.send({
        "from": os.getenv("EMAIL_SENDER"),
        "to": email,
        "subject": "Seu código de confirmação - Lanzaca IA",
        "html": f"<h1>Seu código é <b>{codigo}</b></h1>"
    })


# =========================================================
#   ROTAS DO SISTEMA
# =========================================================

@app.route("/")
def index():
    return render_template("loader.html")


# ------------------------
#   Login
# ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        res = supabase.table("usuarios").select("*") \
            .eq("email", email).eq("senha", senha).execute()

        if not res.data:
            return render_template("login.html", erro="Email ou senha incorretos.")

        user = res.data[0]

        if not user["confirmado"]:
            return render_template("login.html", erro="Confirme seu email para continuar.")

        # Trial expirado?
        inicio = datetime.fromisoformat(user["trial_started_at"])
        if datetime.utcnow() > inicio + timedelta(days=30):
            return redirect("/planos")

        session["usuario_id"] = user["id"]
        session["nome"] = user["nome"]
        session["plano"] = user["plano"]

        return redirect("/painel")

    return render_template("login.html")


# ------------------------
#   Cadastro
# ------------------------
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":

        nome = request.form["nome"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        senha = request.form["senha"]

        ip = request.remote_addr

        # Impede vários trials
        existe = supabase.table("usuarios").select("*") \
            .or_(f"email.eq.{email},telefone.eq.{telefone},ip.eq.{ip}") \
            .execute()

        if existe.data:
            return render_template("cadastro.html",
                                   erro="Você já usou seu teste grátis.")

        codigo = random.randint(100000, 999999)

        supabase.table("usuarios").insert({
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "senha": senha,
            "codigo": codigo,
            "confirmado": False,
            "plano": "trial",
            "status_pagamento": "pendente",
            "trial_started_at": datetime.utcnow().isoformat(),
            "ip": ip
        }).execute()

        enviar_codigo(email, codigo)

        return redirect(f"/confirmar?email={email}")

    return render_template("cadastro.html")


# ------------------------
#   Confirmar código
# ------------------------
@app.route("/confirmar", methods=["GET", "POST"])
def confirmar():
    email = request.args.get("email")

    if request.method == "POST":
        codigo_digitado = request.form["codigo"]

        res = supabase.table("usuarios").select("*") \
            .eq("email", email).execute()

        if not res.data:
            return "Usuário não encontrado."

        user = res.data[0]

        if str(user["codigo"]) != codigo_digitado:
            return render_template("confirmar.html", email=email,
                                   erro="Código incorreto.")

        supabase.table("usuarios").update({"confirmado": True}) \
            .eq("email", email).execute()

        return redirect("/login")

    return render_template("confirmar.html", email=email)


# ------------------------
# Painel interno
# ------------------------
@app.route("/painel")
def painel():
    if "usuario_id" not in session:
        return redirect("/login")

    return render_template("painel.html", nome=session["nome"])


# ------------------------
#   Tela de Planos
# ------------------------
@app.route("/planos")
def planos():
    return render_template("planos.html")


# ------------------------
#   Página Top 3 (Bloqueada para trial)
# ------------------------
@app.route("/top3")
def top3():

    if "usuario_id" not in session:
        return redirect("/login")

    if session["plano"] == "trial":
        return render_template("bloqueado.html")

    # Aqui você vai buscar o Top 3 da IA
    palpites = [
        {"jogo": "Palmeiras x Flamengo", "prob": 82, "odd": 1.95},
        {"jogo": "Corinthians x São Paulo", "prob": 78, "odd": 1.68},
        {"jogo": "Grêmio x Botafogo", "prob": 71, "odd": 2.10}
    ]

    return render_template("top3.html", palpites=palpites)


# ------------------------
# Logout
# ------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =======================================================
# RUN
# =======================================================
if __name__ == "__main__":
    app.run(debug=True)
