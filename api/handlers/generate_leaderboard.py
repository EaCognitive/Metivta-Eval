import json
import os
from datetime import UTC, datetime

from metivta_eval.config.config_loader import get_config_section


def generate_leaderboard():
    config = get_config_section("leaderboard")
    api_config = get_config_section("api")

    if not os.path.exists(api_config["data_file"]):
        return

    with open(api_config["data_file"]) as f:
        data = json.load(f)

    sort_key = config["sort_by_metric"]
    sorted_data = sorted(data, key=lambda x: x["scores"].get(sort_key, 0), reverse=True)

    rows_html = ""
    if sorted_data:
        score_keys = sorted_data[0]["scores"].keys()
        for i, entry in enumerate(sorted_data):
            rank = i + 1
            system_name = entry.get("system", "N/A")
            project_url = entry.get("project_url")
            verified_badge = " ✅" if project_url else ""
            system_display = (
                f'<a href="{project_url}" target="_blank">{system_name}</a>{verified_badge}'
                if project_url
                else system_name
            )

            rows_html += "<tr>"
            rows_html += f"<td>{rank}</td>"
            rows_html += f"<td>{system_display}</td>"
            rows_html += f"<td>{entry.get('author', 'N/A')}</td>"

            for key in score_keys:
                value = entry["scores"].get(key, 0.0)
                class_attr = ' class="highlight"' if key == sort_key else ""
                rows_html += f"<td{class_attr}>{value:.3f}</td>"

            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M UTC")
            rows_html += f"<td>{timestamp}</td></tr>\n"

    template_path = os.path.join(
        os.path.dirname(__file__), "templates", "leaderboard_template.html"
    )
    with open(template_path) as f:
        template = f.read()

    headers = ""
    if sorted_data:
        for key in sorted_data[0]["scores"]:
            headers += f"<th>{key.replace('_', ' ').title()}</th>"

    final_html = template.format(
        title=config["title"],
        last_updated=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        score_headers=headers,
        table_rows=rows_html,
    )

    with open(config["output_file"], "w") as f:
        f.write(final_html)

    print(f"✅ Leaderboard successfully generated at '{config['output_file']}'")


if __name__ == "__main__":
    generate_leaderboard()
