import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get values such as stocks the user owns, the numbers of shares owned,
    # the current price of each stock, and the total value of each holding (i.e., shares times price).
    # Also display the user’s current cash balance along with a grand total (i.e., stocks’ total value plus cash).

    stocks = db.execute("SELECT name, symbol, shares FROM portfolio WHERE user_id = ?;", session["user_id"])
    holding = 0
    for basic in stocks:
        basic["price"] = lookup(basic["symbol"]).get("price")
        basic["value"] = basic["price"] * basic["shares"]
        holding += basic["value"]
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0].get("cash")

    return render_template("index.html", stocks=stocks, holding=holding, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        user_stock = request.form
        stock = lookup(user_stock["symbol"])
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        try:
          quantity = int(user_stock["shares"])
        except ValueError:
            return apology("Invalid quantity!")



        if stock == None:
            return apology("Couldn't find stock!")
        elif not quantity > 0 or not quantity % 1 == 0:
            return apology("Invalid quantity!")
        elif stock["price"]*quantity > user_cash[0]["cash"]:
            return apology("Pfft, You BROKE! Me too T_T")

        cost = stock["price"]*quantity

        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db.execute("INSERT INTO transactions (user_id, date_time, price, symbol, shares, type) VALUES (?,?,?,?,?,'BUY')",
                   session["user_id"], date_time, stock["price"], stock["symbol"], quantity)
        initial_stocks = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
        for symbols in initial_stocks:
            if symbols["symbol"] == stock["symbol"]:
                db.execute("UPDATE portfolio SET shares = shares + ? WHERE (symbol = ? AND user_id = ?);",
                           quantity, stock["symbol"], session["user_id"])
                break
        else:
            db.execute("INSERT INTO portfolio (user_id, name, symbol, shares) VALUES (?,?,?,?);",
                       session["user_id"], stock["name"], stock["symbol"], quantity)
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?;",
                   cost, session["user_id"])

        flash("Successfully Bought " + str(quantity) + " share(s) of " + stock["symbol"])
        return redirect("/")

    value = request.args.get("symbol", "")
    return render_template("buy.html", value=value)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    trans = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", trans=trans)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if lookup(request.form.get("quote")) == None:
            flash("Incorrect Symbol!")
        return render_template("quote.html", stock=lookup(request.form.get("quote")))
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # List: username with name username. Try and exception, Unique OR raise apology.
    # Ask for password, confirmation. With post, hash password
    if request.method == "POST":
        user = request.form

        if user["password"] != user["confirmation"]:
            return apology("Passwords don't Match!")
        hash = generate_password_hash(user["password"])
        try:
            db.execute("INSERT INTO users(username, hash) VALUES (?, ?);", user["username"], hash)
        except ValueError:
            return apology("Username already in use!")

        flash("Succesfully Registered!")
        return redirect("/login")


    return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        sell_req = request.form
        user_symbol = db.execute("SELECT symbol, shares FROM portfolio WHERE user_id = ?", session["user_id"])

        # Try convert
        try:
            user_quantity = int(sell_req["shares"])
        except ValueError:
            return apology("Invalid Quantity!")

        for symbols in user_symbol:
            if symbols["symbol"] == sell_req["symbol"]:
                symbol = symbols["symbol"]
                quantity = symbols["shares"]
                break
        else:
            return apology("No such holding")
        if user_quantity > quantity or user_quantity <= 0 or user_quantity % 1 != 0:
            return apology("Invalid Quantity!")

        # For price and dates
        stock = lookup(symbol)
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update Portfolio
        db.execute("UPDATE portfolio SET shares = shares - ? WHERE (user_id = ? AND symbol = ?);", user_quantity, session["user_id"], stock["symbol"])
        # Clean Portfolio
        db.execute("DELETE FROM portfolio WHERE shares = 0;")
        # Update transactions
        db.execute("INSERT INTO transactions (user_id, date_time, symbol, shares, price, type) VALUES (?, ?, ?, - ?, ?,'SELL');",
                   session["user_id"], date_time, symbol, user_quantity, stock["price"])
        # Update cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", stock["price"] * user_quantity, session["user_id"])
        flash("Successfully Sold " + str(user_quantity) + " share(s) of " + symbol)
        return redirect("/")

    symbols = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", session["user_id"])
    value = request.args.get("symbol", "")
    return render_template("sell.html", value=value, symbols=symbols)

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """return value of cash"""
    return str(db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])[0].get("cash"))
