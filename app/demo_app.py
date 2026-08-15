from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

app = FastAPI(title="Mock Banking Back Office")


MEMBERS = {
    "12345": {
        "name": "Alex Johnson",
        "checking_balance": 2450.75,
        "savings_balance": 8920.50,
        "status": "Active",
    },
    "67890": {
        "name": "Maria Smith",
        "checking_balance": 1120.20,
        "savings_balance": 15440.10,
        "status": "Active",
    },
}


PAGE_STYLE = """
<style>
    body {
        font-family: Arial, sans-serif;
        background: #f4f6f8;
        margin: 0;
        padding: 40px;
    }

    .container {
        max-width: 700px;
        margin: auto;
        background: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    }

    h1 {
        margin-top: 0;
    }

    input {
        padding: 10px;
        width: 250px;
        margin-right: 10px;
    }

    button {
        padding: 10px 18px;
        cursor: pointer;
    }

    .error {
        color: darkred;
        margin-top: 20px;
        font-weight: bold;
    }

    .details {
        margin-top: 25px;
        line-height: 1.8;
    }

    .label {
        font-weight: bold;
    }

    a {
        display: inline-block;
        margin-top: 25px;
    }
</style>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <html>
        <head>
            <title>Member Lookup</title>
            {PAGE_STYLE}
        </head>

        <body>
            <div class="container">
                <h1>Member Lookup</h1>

                <p>Search for a member using their member ID.</p>

                <form action="/lookup" method="post">
                    <input
                        type="text"
                        name="member_id"
                        placeholder="Enter member ID"
                        required
                    />

                    <button type="submit">
                        Search
                    </button>
                </form>
            </div>
        </body>
    </html>
    """


@app.post("/lookup", response_class=HTMLResponse)
def lookup_member(member_id: str = Form(...)):
    member = MEMBERS.get(member_id)

    if not member:
        return f"""
        <html>
            <head>
                <title>Member Not Found</title>
                {PAGE_STYLE}
            </head>

            <body>
                <div class="container">
                    <h1>Member Lookup</h1>

                    <div class="error">
                        Member not found
                    </div>

                    <a href="/">
                        Back to search
                    </a>
                </div>
            </body>
        </html>
        """

    return f"""
    <html>
        <head>
            <title>Member Details</title>
            {PAGE_STYLE}
        </head>

        <body>
            <div class="container">

                <h1>Member Details</h1>

                <div class="details">
                    <div>
                        <span class="label">Member ID:</span>
                        <span id="member-id">{member_id}</span>
                    </div>

                    <div>
                        <span class="label">Name:</span>
                        <span id="member-name">{member["name"]}</span>
                    </div>

                    <div>
                        <span class="label">Status:</span>
                        <span id="member-status">{member["status"]}</span>
                    </div>

                    <div>
                        <span class="label">Checking Balance:</span>
                        $<span id="checking-balance">
                            {member["checking_balance"]:.2f}
                        </span>
                    </div>

                    <div>
                        <span class="label">Savings Balance:</span>
                        $<span id="savings-balance">
                            {member["savings_balance"]:.2f}
                        </span>
                    </div>
                </div>

                <a href="/">
                    Search another member
                </a>

            </div>
        </body>
    </html>
    """