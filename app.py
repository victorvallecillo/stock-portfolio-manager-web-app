import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from werkzeug.exceptions import default_exceptions


app = Flask(__name__)

app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///finance.db")

API_KEY = os.environ.get("API_KEY")


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]

    rows = db.execute("""
        SELECT symbol, SUM(shares) AS shares
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING shares > 0
    """, user_id)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    total = cash
    portfolio = []

    for row in rows:
        quote = lookup(row["symbol"])
        price = quote["price"]
        total_stock = price * row["shares"]
        portfolio.append({
            "symbol": row["symbol"],
            "shares": row["shares"],
            "price": usd(price),
            "total": usd(total_stock)
        })
        total += total_stock

    return render_template("index.html", portfolio=portfolio, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("missing symbol", 400)
        if not shares or not shares.isdigit():
            return apology("invalid shares", 400)

        shares = int(shares)
        if shares <= 0:
            return apology("invalid shares", 400)

        quote = lookup(symbol)
        if quote is None:
            return apology("invalid symbol", 400)

        price = quote["price"]
        cost = price * shares

        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        if cost > cash:
            return apology("not enough cash", 400)

        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, user_id)

        db.execute("""
            INSERT INTO transactions (user_id, symbol, shares, price)
            VALUES (?, ?, ?, ?)
        """, user_id, symbol.upper(), shares, price)

        flash("Bought!")
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]

    rows = db.execute("""
        SELECT symbol, shares, price, timestamp
        FROM transactions
        WHERE user_id = ?
        ORDER BY timestamp DESC
    """, user_id)

    for row in rows:
        row["price"] = usd(row["price"])

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("must provide username", 403)
        if not password:
            return apology("must provide password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 403)

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("missing symbol", 400)

        quote = lookup(symbol)
        if quote is None:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", quote=quote)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        if not password:
            return apology("must provide password", 400)
        if password != confirmation:
            return apology("passwords do not match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("username taken", 400)

        hash = generate_password_hash(password)

        new_id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        session["user_id"] = new_id

        flash("Registered!")
        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]

    symbols = db.execute("""
        SELECT symbol
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING SUM(shares) > 0
    """, user_id)

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("missing symbol", 400)
        if not shares or not shares.isdigit():
            return apology("invalid shares", 400)

        shares = int(shares)
        if shares <= 0:
            return apology("invalid shares", 400)

        total = db.execute("""
            SELECT SUM(shares) AS total
            FROM transactions
            WHERE user_id = ? AND symbol = ?
        """, user_id, symbol)[0]["total"]

        if shares > total:
            return apology("too many shares", 400)

        quote = lookup(symbol)
        price = quote["price"]
        cash_add = price * shares

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", cash_add, user_id)

        db.execute("""
            INSERT INTO transactions (user_id, symbol, shares, price)
            VALUES (?, ?, ?, ?)
        """, user_id, symbol, -shares, price)

        flash("Sold!")
        return redirect("/")

    return render_template("sell.html", symbols=symbols)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    if request.method == "POST":
        amount = request.form.get("amount")

        try:
            amount = float(amount)
            if amount <= 0:
                return apology("invalid amount", 400)
        except:
            return apology("invalid amount", 400)

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, session["user_id"])

        flash("Cash added!")
        return redirect("/")

    return render_template("add_cash.html")


def errorhandler(e):
    """Handle error"""
    if isinstance(e, HTTPException):
        return apology(e.name, e.code)
    else:
        return apology("Error interno", 500)


# Listen for errors
for code in default_exceptions:
    app.register_error_handler(code, errorhandler)
