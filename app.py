from flask import Flask, render_template, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

db = psycopg2.connect(
    host=os.getenv("SUPABASE_HOST"),
    database=os.getenv("SUPABASE_DATABASE"),
    user=os.getenv("SUPABASE_USER"),
    password=os.getenv("SUPABASE_PASSWORD")
)

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

def execute_query(query, params=None):
    cursor = db.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(query, params)

        if cursor.description:
            result = cursor.fetchall()
        else:
            result = None

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()

def IsAuthorized(email):
    result = execute_query("SELECT IsAuthorized(%s) AS authorized", (email,))

    if not result:
        return False
    
    return result[0]["authorized"]

def authorized_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))

        email = session["user"]["email"]

        if not IsAuthorized(email):
            return render_template("unauthorized.html")

        return f(*args, **kwargs)

    return decorated

def GetRecords():
    return execute_query("SELECT * FROM GetAllPasses()")

def GetMyRecords():
    teacherID = session["user"]["sub"]

    return execute_query("SELECT * FROM GetTeacherPasses(%s)", (teacherID,))

def InsertPass(teacherName, studentName, destination, googleID):
    execute_query(
        "SELECT AddPass(%s, %s, %s, %s)",
        (teacherName, studentName, destination, googleID)
    )

def DeletePass(passID, deletedBy):
    execute_query(
        "SELECT ArchivePass(%s, %s)",
        (passID,
         deletedBy)
    )

@app.route("/")
@authorized_required
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html", 
        title="Welcome", 
        username=session["user"]["name"],
        dataSet=GetMyRecords(),
        fullSet=GetRecords(),
        now=datetime.now(),
        next_page="home"
    )

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user = token["userinfo"]

    session["user"] = user

    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

@app.route("/get_my_passes")
def get_my_passes():
    dataSet = GetMyRecords()

    next_page = request.args.get("next", "home")

    return render_template(
        "pass_table.html",
        passes=dataSet,
        show_delete=True,
        show_teacher=False,
        next_page=next_page
    )

@app.route("/get_all_passes/<show_delete>")
def get_all_passes(show_delete):
    fullSet = GetRecords()

    next_page = request.args.get("next", "home")

    return render_template(
        "pass_table.html",
        passes=fullSet,
        show_delete=(show_delete == "true"),
        show_teacher=True,
        next_page=next_page
    )

@app.route("/add_pass", methods=["POST"])
def add_pass():

    teacherName = session["user"]["name"]
    studentName = request.form.get("studentName")
    destination = request.form.get("destination")
    otherDestination = request.form.get("otherDestination")
    googleID = session["user"]["sub"]

    if destination == "Other":
        destination = otherDestination

    InsertPass(teacherName, studentName, destination, googleID)

    return redirect(url_for("home"))
  
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    deletedBy = session["user"]["email"]
    DeletePass(id, deletedBy)

    next_page = request.args.get("next", "home")
    return redirect(url_for(next_page))

@app.route("/monitor")
@authorized_required
def monitor():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "monitor.html", 
        title="Welcome", username=session["user"]["name"],
        fullSet=GetRecords(),
        now=datetime.now(),
        next_page="monitor"
    )

if __name__ == "__main__":
    app.run(debug=True)