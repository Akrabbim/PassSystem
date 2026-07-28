from flask import Flask, render_template, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
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

def DeletePass(passID):
    execute_query(
        "SELECT ArchivePass(%s)",
        (passID,)
    )

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html", 
        title="Welcome", 
        username=session["user"]["name"],
        dataSet=GetMyRecords(),
        now=datetime.now()
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
    DeletePass(id)      # your database function

    next_page = request.args.get("next", "home")
    return redirect(url_for(next_page))

@app.route("/monitor")
def monitor():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "monitor.html", 
        title="Welcome", username=session["user"]["name"],
        dataSet=GetRecords(),
        now=datetime.now()
    )

if __name__ == "__main__":
    app.run(debug=True)