import os
import requests
from flask import redirect, session
from functools import wraps


def apology(message, code=400):
    def escape(s):
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''")
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def lookup(symbol):
    url = f"https://api.iex.cloud/v1/data/core/quote/{symbol}?token={os.environ.get('API_KEY')}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    if len(data) == 0:
        return None
    data = data[0]
    return {
        "name": data["companyName"],
        "price": data["latestPrice"],
        "symbol": data["symbol"]
    }


def usd(value):
    return f"${value:,.2f}"
