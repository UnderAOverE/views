import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from rapidfuzz import fuzz

class RenewalMatcher:
    """
    Analyzes ServiceAlerts and finds potential renewals in ConsolidatedData 
    using fuzzy string matching.
    """

    def __init__(self, uri: str, db_name: str):
        """
        :param uri: MongoDB connection string.
        :param db_name: Database name.
        """
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.alerts_coll = self.db["ServiceAlerts"]
        self.consolidated_coll = self.db["ConsolidatedData"]

    async def step_1_get_recent_alerts(self) -> List[Dict[str, Any]]:
        """
        Step 1: Fetch certificates needing attention from the last hour.
        
        :return: Flattened list of certificate alert objects.
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
        Steps 2 & 3: Find potential renewals in ConsolidatedData and score them.
        
        :param alert: The alert dictionary from Step 1.
        :type alert: Dict[str, Any]
        :return: Alert enriched with matched certificates.
        :rtype: Dict[str, Any]
        """
        # Look for valid production certs logged in the last 7 days
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        
        query = {
            "csi_application_id": alert["csi_id"],
            "status": "Valid",
            "source_properties.environment": {"$in": ["prod", "PRODUCTION"]},
            "log_date": {"$gte": seven_days_ago},
            # Ignore signers: only look for certs with > current days but < 4 years
            "days_to_expiration": {"$gt": alert["days_to_expiration"], "$lt": 1460}
        }
        
        matches = []
        # Optimization: Sort by expiration_date to find newest renewals first
        cursor = self.consolidated_coll.find(query).sort("expiration_date", -1)
        
        async for doc in cursor:
            s1 = alert["distinguished_name"].lower()
            s2 = doc["distinguished_name"].lower()
            
            # Fuzzy match: Highest of Partial or Token Set ratio
            score = max(fuzz.partial_ratio(s1, s2), fuzz.token_set_ratio(s1, s2))
            
            if score >= 80:
                matches.append({
                    "distinguished_name": doc["distinguished_name"],
                    "days_to_expiration": doc["days_to_expiration"],
                    "expiration_date": doc["expiration_date"],
                    "serial_number": doc["source_properties"].get("serial_number", "N/A"),
                    "similarity_score": round(score, 2)
                })
            
            # Fetch a small buffer, we only need the top 3
            if len(matches) >= 5:
                break

        # Ensure sorted by date and limited to 3
        matches.sort(key=lambda x: x["expiration_date"], reverse=True)
        alert["certificates_match"] = matches[:3]
        return alert

    def generate_email_html(self, results: List[Dict[str, Any]]) -> str:
        """
        Builds a modern HTML summary with urgency-based sorting.
        
        :param results: Processed results from Step 2/3.
        :type results: List[Dict[str, Any]]
        :return: Formatted HTML string.
        :rtype: str
        """
        # Sort by soonest expiring (1 -> 7 days)
        results.sort(key=lambda x: x["days_to_expiration"])
        
        table_1_rows = ""
        table_2_rows = ""

        for idx, item in enumerate(results, 1):
            # --- TABLE 1: ACTION REQUIRED ---
            table_1_rows += f"""
            <tr>
                <td style="text-align:center;">{idx}</td>
                <td style="text-align:center;">{item['csi_id']}</td>
                <td>{item['cluster_name']}<br>{item['namespace']}<br><b>{item['object_name']}</b></td>
                <td style="font-family:monospace; font-size:11px;">{item['distinguished_name']}<br>
                    <small style="color:#666;">SN: {item['serial_number']}</small>
                </td>
                <td style="text-align:center; background-color:#fff3f3; color:#d9534f;"><b>{item['days_to_expiration']}</b></td>
                <td>{item['expiration_date'].strftime('%Y-%m-%d')}</td>
            </tr>
            """

            # --- TABLE 2: RENEWAL MATCHES ---
            matches = item.get('certificates_match', [])
            
            # Per Requirement: Only show the row if at least one match was found
            if not matches:
                continue

            m_cells = ""
            # We always process 3 slots
            for i in range(3):
                if i < len(matches):
                    m = matches[i]
                    m_cells += f"""
                    <td style="background-color:#f0fff4; font-size:11px; border:1px solid #c3e6cb; width:25%;">
                        <div style="color:#155724; font-weight:bold; margin-bottom:4px;">
                            Match Score: {m['similarity_score']}%
                        </div>
                        {m['distinguished_name']}<br>
                        <span style="color:#666;">SN: {m['serial_number']}</span><br>
                        <small><b>Exp:</b> {m['expiration_date'].strftime('%Y-%m-%d')}</small>
                    </td>
                    """
                else:
                    # Per Requirement: Show N/A if 3 matches aren't available
                    m_cells += """
                    <td style="background-color:#f9f9f9; color:#999; text-align:center; font-size:11px; border:1px solid #ddd; width:25%;">
                        N/A
                    </td>
                    """

            table_2_rows += f"""
            <tr>
                <td style="font-family:monospace; font-size:11px; background-color:#fff5f5; width:25%; border:1px solid #ddd;">
                    <b>Expiring Cert:</b><br>{item['distinguished_name']}<br>
                    <small style="color:#666;">SN: {item['serial_number']}</small>
                </td>
                {m_cells}
            </tr>
            """

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.5; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
                th {{ background-color: #004a99; color: white; padding: 12px; font-size: 12px; border: 1px solid #ddd; text-align: left; }}
                td {{ padding: 10px; border: 1px solid #ddd; font-size: 12px; vertical-align: top; }}
                tr:nth-child(even) {{ background-color: #fcfcfc; }}
                .match-header {{ background-color: #28a745; }}
            </style>
        </head>
        <body>
            <h2 style="color:#004a99;">Production Certificate Renewal Report</h2>
            
            <p>The following certificates in <b>Production</b> are expiring within 7 days and were flagged for attention.</p>

            <h3>1. Certificates Expiring (Action Required)</h3>
            <table>
                <thead>
                    <tr>
                        <th>S.No.</th><th>CSI</th><th>Service Details</th><th>Expiring Certificate</th><th>Days</th><th>Expiration Date</th>
                    </tr>
                </thead>
                <tbody>{table_1_rows}</tbody>
            </table>

            <h3>2. Renewal Analysis (Database Search Results)</h3>
            <p>We searched the database for valid certificates with similar names for the same CSI ID. 
               Rows are only shown if at least one match was detected.</p>
            <table>
                <thead>
                    <tr>
                        <th style="background-color:#d9534f;">Expiring Certificate</th>
                        <th class="match-header">Match 1 (Newest)</th>
                        <th class="match-header">Match 2</th>
                        <th class="match-header">Match 3</th>
                    </tr>
                </thead>
                <tbody>{table_2_rows}</tbody>
            </table>
            
            <p style="font-size:11px; color:#777; border-top:1px solid #eee; padding-top:10px;">
                Note: Similarity scores are calculated using fuzzy token matching. A score >80% typically indicates a direct renewal or version update.
            </p>
        </body>
        </html>
        """

    async def run(self) -> None:
        """
        Main execution loop.
        """
        try:
            logging.info("Starting renewal matching process...")
            
            # Step 1: Get alerts
            alerts = await self.step_1_get_recent_alerts()
            if not alerts:
                logging.info("No expiring certificates found needing attention.")
                return

            # Step 2 & 3: Match and Score
            tasks = [self.step_2_3_find_matches(alert) for alert in alerts]
            final_results = await asyncio.gather(*tasks)
            
            # Step 4: Generate Report
            html_report = self.generate_email_html(final_results)
            
            # Here you would integrate with your SMTP sender
            logging.info("Renewal analysis report generated successfully.")
            
        except Exception as e:
            logging.error(f"Error during matching process: {e}", exc_info=True)

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    matcher = RenewalMatcher("mongodb://localhost:27017", "CertificateDB")
    asyncio.run(matcher.run())
    













db.ConsolidatedData.createIndex({
    "source_properties.microservice_name": 1,
    "status": 1,
    "source_properties.environment": 1,
    "log_date": -1
}, { name: "idx_ms_lookup_main" });


db.ConsolidatedData.createIndex({
    "csi_application_id": 1,
    "status": 1,
    "source_properties.environment": 1,
    "log_date": -1,
    "expiration_date": -1
}, { name: "idx_csi_renewal_matcher" });

db.ConsolidatedData.createIndex({
    "status": 1,
    "source_properties.environment": 1,
    "log_date": -1,
    "days_to_expiration": 1
}, { name: "idx_global_expiry_range" });




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
