from flask import Flask, render_template, request, redirect
from database import get_db_connection

app = Flask(__name__)


# Home Page
@app.route("/")
def home():
    return render_template("index.html")


# Get Token Page
@app.route("/get-token")
def get_token():
    return render_template("get_token.html")


@app.route("/track-token", methods=["GET", "POST"])
def track_token():

    if request.method == "POST":

        token_number = request.form["token_number"]

        return redirect(f"/queue-status/{token_number}")

    return render_template("track_token.html")


# Generate Token
@app.route("/generate-token", methods=["POST"])
def generate_token():

    name = request.form["name"]
    service = request.form["service"]

    if service == "Billing":
        prefix = "B"
    elif service == "Enquiry":
        prefix = "E"
    elif service == "Registration":
        prefix = "R"
    elif service == "General Consultation":
        prefix = "G"
    else:
        prefix = "A"

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM tokens WHERE service = %s",
        (service,)
    )

    count = cursor.fetchone()[0]

    token_number = f"{prefix}{count + 1:03d}"

    cursor.execute(
        """
        INSERT INTO tokens (token_number, name, service)
        VALUES (%s, %s, %s)
        """,
        (token_number, name, service)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(f"/queue-status/{token_number}")


# Queue Status
@app.route("/queue-status/<token_number>")
def queue_status(token_number):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get user's token
    cursor.execute(
        "SELECT * FROM tokens WHERE token_number = %s",
        (token_number,)
    )

    token = cursor.fetchone()

    if token is None:
        cursor.close()
        connection.close()
        return "Token not found"

    # Find current waiting token for same service
    cursor.execute(
        """
        SELECT token_number
        FROM tokens
        WHERE service = %s
        AND status = 'Waiting'
        ORDER BY id ASC
        LIMIT 1
        """,
        (token["service"],)
    )

    current = cursor.fetchone()

    if current:
        current_token = current["token_number"]
    else:
        current_token = "No Waiting Tokens"

    # Count people before this token
    cursor.execute(
        """
        SELECT COUNT(*) AS people_before
        FROM tokens
        WHERE service = %s
        AND status = 'Waiting'
        AND id < %s
        """,
        (token["service"], token["id"])
    )

    result = cursor.fetchone()

    people_before = result["people_before"]

    # Get average service time for this service
    cursor.execute(
        """
        SELECT AVG(
            TIMESTAMPDIFF(MINUTE, created_at, completed_at)
        ) AS avg_time
        FROM tokens
        WHERE service = %s
        AND status = 'Completed'
        """,
        (token["service"],)
    )

    avg_result = cursor.fetchone()

    if avg_result["avg_time"] is not None:
        average_service_time = round(avg_result["avg_time"])
    else:
        average_service_time = 5

    # Calculate estimated waiting time
    waiting_time = people_before * average_service_time

    cursor.close()
    connection.close()

    return render_template(
        "queue_status.html",
        token_number=token["token_number"],
        name=token["name"],
        service=token["service"],
        current_token=current_token,
        people_before=people_before,
        waiting_time=waiting_time,
        status=token["status"]
    )


# Admin Dashboard
@app.route("/admin")
def admin():

    selected_service = request.args.get(
        "service",
        "Billing"
    )

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM tokens
        WHERE status = 'Waiting'
        AND service = %s
        ORDER BY id ASC
        """,
        (selected_service,)
    )

    tokens = cursor.fetchall()

    if tokens:
        current_token = tokens[0]["token_number"]
    else:
        current_token = "No Waiting Tokens"

    waiting_count = len(tokens)

    cursor.close()
    connection.close()

    return render_template(
        "admin.html",
        tokens=tokens,
        current_token=current_token,
        waiting_count=waiting_count,
        selected_service=selected_service
    )


# Call Next Token
@app.route("/call-next", methods=["POST"])
def call_next():

    service = request.form["service"]

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM tokens
        WHERE status = 'Waiting'
        AND service = %s
        ORDER BY id ASC
        LIMIT 1
        """,
        (service,)
    )

    token = cursor.fetchone()

    if token:

        cursor.execute(
            """
            UPDATE tokens
            SET status = 'Completed',
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (token[0],)
        )

        connection.commit()

    cursor.close()
    connection.close()

    return redirect(f"/admin?service={service}")


# Run Flask Application
if __name__ == "__main__":
    app.run(debug=True)