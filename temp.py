def generate_html_table(title: str, details: dict[str, str]) -> str:
    if not details:
        return f'<h2>{title}</h2><p>No details provided.</p>'

    log_datetime = datetime.now(timezone.utc).strftime('%m-%d-%y %H:%M:%S %Z')
    table_rows = ''
    for key, value in details.items():
        escaped_value = html_escape_string_recursive(value)
        table_rows += f'<tr><td style="padding: 8px; border: 1px solid #ddd; text-align: left; font-weight: bold;">{key}</td><td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{escaped_value}</td></tr>'

    html_content = f'''
    <html>
    <head>
    <style>
        body {{font-family: Arial, sans-serif; margin: 20px;}}
        h2 {{color: #333;}}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            box-shadow: 0 2px 3px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            border: 1px solid #ddd;
            text-align: left;
        }}
        th {{
            background-color: #2BBCE3;
            color: #333;
        }}
        tr:nth-child(even) {{background-color: #2BBCE3;}}
        tr:hover {{background-color: #f1f1f1;}}
    </style>
    </head>
    <body>
        <h2>{title}</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 30%;">Stage</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p style="font-size: 0.9em; color: #777; margin-top: 20px;">
            This is an automated email from (APPLICATION_NAME_STR) generated on {log_datetime}.
        </p>
    </body>
    </html>
    '''
    return html_content