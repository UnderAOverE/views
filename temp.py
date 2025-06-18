import html
from typing import Any, Dict, List, Union
from datetime import datetime, timezone

def html_escape_string_recursive(value: Any) -> str:
    """
    Recursively escapes HTML special characters in strings,
    handles lists and dicts by converting them to string representations
    and then escaping.
    """
    if isinstance(value, str):
        return html.escape(value)
    elif isinstance(value, list):
        return html.escape(str([html_escape_string_recursive(item) for item in value]))
    elif isinstance(value, dict):
        return html.escape(str({k: html_escape_string_recursive(v) for k, v in value.items()}))
    elif value is None:
        return "N/A" # Or however you want to represent None
    return html.escape(str(value))


def generate_html_for_list_of_dicts(item_list: List[Dict[str, Any]]) -> str:
    """
    Generates HTML for a list of dictionaries.
    Each dictionary is rendered as a block of key-value pairs.
    """
    if not item_list:
        return "<p>No items.</p>"

    html_parts = []
    for item_dict in item_list:
        if not isinstance(item_dict, dict):
            html_parts.append(f"<div style='padding: 5px; border: 1px solid #eee; margin-bottom: 5px;'>{html_escape_string_recursive(item_dict)}</div>")
            continue

        item_details_html = []
        for key, value in item_dict.items():
            escaped_key = html.escape(str(key))
            escaped_value = html_escape_string_recursive(value) # Use recursive for nested structures within item_dict values
            item_details_html.append(f"<div><strong>{escaped_key}:</strong> {escaped_value}</div>")
        
        html_parts.append(f"<div style='padding: 8px; border: 1px solid #ccc; background-color: #f9f9f9; margin-bottom: 8px; border-radius: 4px;'>{''.join(item_details_html)}</div>")
    
    return "".join(html_parts)


def generate_html_table(title: str, details: Dict[str, Any]) -> str: # Changed type hint
    if not details:
        return f'<h2>{title}</h2><p>No details provided.</p>'

    log_datetime = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z') # Standardized format
    table_rows = ''
    
    # Define APPLICATION_NAME_STR or pass it as an argument
    application_name = details.get("application_name", "My Application") # Example default

    for key, value in details.items():
        # Skip internal keys if you added them like application_name
        if key == "application_name":
            continue

        escaped_key = html.escape(str(key).replace("_", " ").title()) # Prettify key
        
        rendered_value_html = ''
        if key in ("checks", "actions") and isinstance(value, list):
            rendered_value_html = generate_html_for_list_of_dicts(value)
        else:
            # For other types, use the recursive escaper
            rendered_value_html = html_escape_string_recursive(value)

        table_rows += f'''
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: left; font-weight: bold; vertical-align: top;">{escaped_key}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{rendered_value_html}</td>
        </tr>'''

    html_content = f'''
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        body {{font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333;}}
        h2 {{color: #333; border-bottom: 2px solid #2BBCE3; padding-bottom: 5px;}}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.15);
            background-color: #fff;
        }}
        th, td {{
            padding: 10px 12px; /* Adjusted padding */
            border: 1px solid #ddd;
            text-align: left;
        }}
        th {{
            background-color: #2BBCE3; /* Main theme color for headers */
            color: #fff; /* White text for better contrast */
            font-weight: bold;
        }}
        /* Keep specific styling for first column cells if needed for alignment */
        td[style*="font-weight: bold"] {{ 
            background-color: #e9ecef; /* Lighter shade for key cells */
        }}
        tr:nth-child(even) td:not([style*="font-weight: bold"]) {{ /* Style even rows' value cells */
            /* background-color: #f8f9fa; */ /* Subtle striping if desired, removed for simplicity */
        }}
        tr:hover td:not([style*="font-weight: bold"]) {{ /* Hover effect for value cells */
            background-color: #e2f4fb;
        }}
        /* Styling for the nested blocks within checks/actions */
        div[style*="background-color: #f9f9f9"] div {{ /* Target divs inside the blocks */
            padding: 2px 0; /* Minimal padding for sub-items */
        }}
        p.footer {{font-size: 0.9em; color: #777; margin-top: 20px; text-align: center;}}
    </style>
    </head>
    <body>
        <h2>{html.escape(title)}</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 25%;">Property</th> {/* Changed from Stage to Property */}
                    <th>Details</th>      {/* Changed from Result to Details */}
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p class="footer">
            This is an automated email from {html.escape(application_name)} generated on {log_datetime}.
        </p>
    </body>
    </html>
    '''
    return html_content

# --- Example Usage ---
if __name__ == '__main__':
    sample_details = {
        "Process ID": "12345",
        "Status": "Completed",
        "Environment": "Production",
        "application_name": "Data Pipeline Monitor", # Example of passing app name
        "checks": [
            {"name": "Database Connection", "result": "Success", "timestamp": "2023-10-27 10:00:00"},
            {"name": "API Availability", "result": "Failure", "error_code": 503, "message": "Service unavailable"},
            {"name": "Disk Space", "result": "Warning", "usage_percent": "85%"}
        ],
        "actions": [
            {"type": "Notification Sent", "recipient": "admin@example.com", "status": "Success"},
            {"type": "Restart Attempted", "service": "PaymentGateway", "status": "Pending"}
        ],
        "Summary": "Process finished with some warnings."
    }

    html_output = generate_html_table("System Health Check Report", sample_details)

    with open("email_report.html", "w", encoding="utf-8") as f:
        f.write(html_output)
    print("Generated email_report.html")

    # Example with an empty list
    sample_details_empty_list = {
        "Process ID": "67890",
        "Status": "Initiated",
        "checks": [],
        "actions": [
             {"type": "Initial Log", "message": "Process started"}
        ]
    }
    html_output_empty = generate_html_table("Empty List Test", sample_details_empty_list)
    with open("email_report_empty.html", "w", encoding="utf-8") as f:
        f.write(html_output_empty)
    print("Generated email_report_empty.html")

    # Example with non-dict in list
    sample_details_mixed_list = {
        "Process ID": "ABCDE",
        "Status": "Mixed Content",
        "checks": [
             {"name": "Valid Item", "result": "OK"},
             "This is just a string in the list", # Non-dict item
             None,
             12345
        ]
    }
    html_output_mixed = generate_html_table("Mixed List Test", sample_details_mixed_list)
    with open("email_report_mixed.html", "w", encoding="utf-8") as f:
        f.write(html_output_mixed)
    print("Generated email_report_mixed.html")
