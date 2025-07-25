@staticmethod
def generate_html_for_list_of_dicts(item_list: list[dict[str, Any]]) -> str:
    if not item_list:
        return "<p>No items.</p>"

    html_parts = []
    for item_dict in item_list:
        if not isinstance(item_dict, dict):
            html_parts.append(f"<div style='padding: 5px; border: 1px solid #eee; margin-bottom: 5px;'>{html_escape_string_recursive(item_dict)}</div>")
            continue

        item_details_html = []
        for key, value in item_dict.items():
            escaped_key = html_escape_string_recursive(str(key))
            escaped_value = html_escape_string_recursive(value)  # Use recursive for nested structures within item dict
            item_details_html.append(f"<div><strong>{escaped_key}:</strong> {escaped_value}</div>")

        html_parts.append(f"<div style='padding: 8px; border: 1px solid #ccf; background-color: #f9f9f9; border-radius: 4px;'>{''.join(item_details_html)}</div>")

    return "".join(html_parts)

# (In another section of the code)
table_rows = ""
for key, value in details.items():
    # Basic HTML escaping for value to prevent XSS if details come from untrusted sources, for more robust escaping, use html.escape
    # escaped_value = str(value).replace('<','&lt;').replace('>','&gt;')
    escaped_key = html_escape_string_recursive(key)
    rendered_value_html = ""
    if key in ("Checks", "Actions") and isinstance(value, list):
        rendered_value_html = self.generate_html_for_list_of_dicts(value)  # Use the method to generate HTML for lists of dicts
    else:
        # For other types, use the recursive escape
        rendered_value_html = html_escape_string_recursive(value)

    table_rows += f"""
<tr>
    <td style="padding: 8px; border: 1px solid #ddd; text-align: left; font-weight: bold; vertical-align: top;">{escaped_key}</td>
    <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{rendered_value_html}</td>
</tr>
"""

html_content = ...