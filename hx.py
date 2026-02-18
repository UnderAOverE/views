
query = {
    "source_properties.microservice_name": {
        "$in": ms_names,
    },
    "source_properties.environment": {
        "$in": self.cm_settings.environments_to_monitor,
    },
    "log_date": {
        "$gte": cutoff,
    },
    "status": Constants.valid.capitalize(),
}

projection = {
    "distinguished_name": 1,
    "days_to_expiration": 1,
    "expiration_date": 1,
    "source_properties.serial_number": 1,
    "source_properties.microservice_name": 1,
    "_id": 0,
}

pipeline = [
    {
        "$match": {
            "log_date": {"$gte": cutoff_date},
            "source_properties.environment": {"$in": self.cm_settings.environments_to_monitor},
            "days_to_expiration": {"$lte": self.cm_settings.expiry_threshold, "$gt": 0},
            "source_properties.microservice_name": {"$ne": "null"},
            "status": Constants.valid.capitalize(),
        }
    },
    {
        "$group": {
            "_id": "$source_properties.microservice_name",
            "csi_id": {"$first": "$csi_application_id"},
            "certificates": {
                "$push": {
                    "distinguished_name": "$distinguished_name",
                    "days_to_expiration": "$days_to_expiration",
                    "expiration_date": "$expiration_date",
                    "serial_number": "$source_properties.serial_number",
                }
            },
        }
    },
]




import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from rapidfuzz import fuzz

class RenewalMatcher:
    """
    Analyzes ServiceAlerts and finds potential renewals in ConsolidatedData.
    """

    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.alerts_coll = self.db["ServiceAlerts"]
        self.consolidated_coll = self.db["ConsolidatedData"]

    async def step_1_get_recent_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetches certificates needing attention from the last hour.
        
        :return: Flattened list of certificates requiring attention.
        :rtype: List[Dict[str, Any]]
        """
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        
        pipeline = [
            {"$match": {"log_datetime": {"$gte": one_hour_ago}}},
            {"$unwind": "$certificates"},
            {"$match": {"certificates.attention_required": True}},
            {
                "$project": {
                    "_id": 0,
                    "cluster_name": 1,
                    "namespace": 1,
                    "object_name": 1,
                    "csi_id": 1,
                    "log_datetime": 1,
                    "distinguished_name": "$certificates.distinguished_name",
                    "days_to_expiration": "$certificates.days_to_expiration",
                    "expiration_date": "$certificates.expiration_date",
                    "serial_number": "$certificates.serial_number"
                }
            }
        ]
        return await self.alerts_coll.aggregate(pipeline).to_list(length=None)

    async def step_2_3_find_matches(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finds matching renewals for a single expiring certificate.
        
        :param alert: The alert dictionary from Step 1.
        :return: Alert enriched with a list of up to 3 matches.
        """
        # Range: Looking for certs logged in the last 7 days
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        
        # Filtering ConsolidatedData
        query = {
            "csi_application_id": alert["csi_id"],
            "status": "Valid",
            "source_properties.environment": {"$in": ["prod", "PRODUCTION"]},
            "log_date": {"$gte": seven_days_ago},
            # Upper bound to ignore signers (e.g., ignore anything > 4 years)
            "days_to_expiration": {"$gt": alert["days_to_expiration"], "$lt": 1460}
        }
        
        matches = []
        # Sort by expiration date so we see the newest ones first
        cursor = self.consolidated_coll.find(query).sort("expiration_date", -1)
        
        async for doc in cursor:
            # Step 3: RapidFuzz Logic
            s1 = alert["distinguished_name"].lower()
            s2 = doc["distinguished_name"].lower()
            
            # We take the best of Partial or Token Set ratio
            score = max(fuzz.partial_ratio(s1, s2), fuzz.token_set_ratio(s1, s2))
            
            if score >= 80: # Threshold for similarity
                matches.append({
                    "distinguished_name": doc["distinguished_name"],
                    "days_to_expiration": doc["days_to_expiration"],
                    "expiration_date": doc["expiration_date"],
                    "serial_number": doc["source_properties"].get("serial_number", "N/A"),
                    "similarity_score": round(score, 2)
                })
            
            if len(matches) >= 10: # Fetch a buffer, limit to 3 after final sort
                break

        # Final Sort: Newest Expiration First
        matches.sort(key=lambda x: x["expiration_date"], reverse=True)
        
        alert["certificates_match"] = matches[:3]
        return alert

    def generate_email_html(self, results: List[Dict[str, Any]]) -> str:
        """
        Builds the dual-table modern email summary.
        """
        # Sort results by urgency (days 1 to 7)
        results.sort(key=lambda x: x["days_to_expiration"])
        
        table_1_rows = ""
        table_2_rows = ""

        for idx, item in enumerate(results, 1):
            # Table 1: Expiring List
            table_1_rows += f"""
            <tr>
                <td style="text-align:center;">{idx}</td>
                <td style="text-align:center;">{item['csi_id']}</td>
                <td>{item['cluster_name']}<br>{item['namespace']}<br><b>{item['object_name']}</b></td>
                <td style="font-family:monospace; font-size:11px;">{item['distinguished_name']}<br><small>SN: {item['serial_number']}</small></td>
                <td style="text-align:center; background:#fff3f3; color:#d9534f;"><b>{item['days_to_expiration']}</b></td>
                <td>{item['expiration_date'].strftime('%Y-%m-%d')}</td>
            </tr>
            """

            # Table 2: Match Grid
            m_cells = ""
            matches = item.get('certificates_match', [])
            for i in range(3):
                if i < len(matches):
                    m = matches[i]
                    m_cells += f"""
                    <td style="background:#f0fff4; font-size:11px; border:1px solid #c3e6cb; width:25%;">
                        <b style="color:#28a745;">{m['similarity_score']}% Match</b><br>
                        {m['distinguished_name']}<br>
                        <span style="color:#666;">SN: {m['serial_number']}</span><br>
                        <small>Exp: {m['expiration_date'].strftime('%Y-%m-%d')}</small>
                    </td>
                    """
                else:
                    m_cells += "<td style='background:#f9f9f9; color:#ccc; text-align:center;'>No further match</td>"

            table_2_rows += f"""
            <tr>
                <td style="font-family:monospace; font-size:11px; background:#fff5f5; width:25%;">
                    <b>Expiring:</b><br>{item['distinguished_name']}<br><small>SN: {item['serial_number']}</small>
                </td>
                {m_cells}
            </tr>
            """

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; color: #333; line-height: 1.4; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
                th {{ background: #004a99; color: white; padding: 10px; font-size: 12px; border: 1px solid #ddd; }}
                td {{ padding: 8px; border: 1px solid #ddd; font-size: 12px; vertical-align: top; }}
                .header-match {{ background: #28a745; }}
            </style>
        </head>
        <body>
            <h3>1. Certificates Requiring Immediate Attention</h3>
            <table>
                <tr>
                    <th>S.No.</th><th>CSI</th><th>Service Details</th><th>Expiring Certificate</th><th>Days</th><th>Expiration Date</th>
                </tr>
                {table_1_rows}
            </table>

            <h3>2. Renewal Analysis (Potential Matches)</h3>
            <p>The following matches were found in the database. These certificates may have been intended as renewals:</p>
            <table>
                <tr>
                    <th style="background:#d9534f;">Expiring Certificate</th>
                    <th class="header-match">Match 1 (Newest)</th>
                    <th class="header-match">Match 2</th>
                    <th class="header-match">Match 3</th>
                </tr>
                {table_2_rows}
            </table>
        </body>
        </html>
        """

    async def run(self):
        # Step 1
        alerts = await self.step_1_get_recent_alerts()
        if not alerts:
            print("No new alerts to process.")
            return

        # Step 2 & 3
        tasks = [self.step_2_3_find_matches(alert) for alert in alerts]
        final_results = await asyncio.gather(*tasks)
        
        # Email Generation
        html_body = self.generate_email_html(final_results)
        # Send Email Logic...
        print("Analysis Complete. HTML Generated.")

# Execution
if __name__ == "__main__":
    matcher = RenewalMatcher("mongodb://localhost:27017", "your_db")
    asyncio.run(matcher.run())
