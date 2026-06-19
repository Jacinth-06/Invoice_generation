import os
from flask import Flask, render_template, request, send_file
from generate_invoice import create_invoice
import tempfile

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    
    # Process data to match sample_data structure
    invoice_data = {
        "company": {
            "name": data.get("company_name", ""),
            "address_lines": [line.strip() for line in data.get("company_address", "").split('\n') if line.strip()],
            "phone": data.get("company_phone", ""),
            "email": data.get("company_email", ""),
            "gstin": data.get("company_gstin", ""),
            "logo_path": None,  # Hardcoded for now
        },
        "invoice_no": data.get("invoice_no", ""),
        "invoice_date": data.get("invoice_date", ""),
        "bill_to": {
            "name": data.get("bill_to_name", ""),
            "address_lines": [line.strip() for line in data.get("bill_to_address", "").split('\n') if line.strip()],
            "gstin": data.get("bill_to_gstin", ""),
        },
        "ship_to": {
            "name": data.get("ship_to_name", ""),
            "address_lines": [line.strip() for line in data.get("ship_to_address", "").split('\n') if line.strip()],
            "gstin": data.get("ship_to_gstin", ""),
        },
        "items": [],
        "notes": [line.strip() for line in data.get("notes", "").split('\n') if line.strip()],
        "bank": {
            "acc_name": data.get("bank_acc_name", ""),
            "acc_no": data.get("bank_acc_no", ""),
            "acc_type": data.get("bank_acc_type", ""),
            "bank_name": data.get("bank_name", ""),
            "branch": data.get("bank_branch", ""),
            "ifsc": data.get("bank_ifsc", ""),
        }
    }

    # Items
    for item in data.get("items", []):
        try:
            invoice_data["items"].append({
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "hsn": item.get("hsn", ""),
                "qty": float(item.get("qty", 0)),
                "rate": float(item.get("rate", 0)),
                "cgst_pct": float(item.get("cgst_pct", 0)),
                "sgst_pct": float(item.get("sgst_pct", 0)),
            })
        except ValueError:
            pass # Ignore item if invalid number

    # Provide fallback if no items to prevent division by zero or errors
    if not invoice_data["items"]:
        invoice_data["items"].append({
            "name": "Sample Item",
            "description": "Please add an item",
            "hsn": "",
            "qty": 1,
            "rate": 0.0,
            "cgst_pct": 0.0,
            "sgst_pct": 0.0,
        })

    # Generate PDF in temp directory
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    
    create_invoice(invoice_data, path)

    # Return the file to be previewed
    return send_file(path, as_attachment=False, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
