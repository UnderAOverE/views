import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from rapidfuzz import fuzz
from pymongo import UpdateOne

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CertificateMatcherEngine:
    """
    Engine to match expiring certificates from ServiceAlerts with 
    potential renewals in ConsolidatedData using fuzzy logic.
    """

    def __init__(self, mongo_uri: str, db_name: str):
        """
        :param mongo_uri: MongoDB connection string
        :type mongo_uri: str
        :param db_name: Target database name
        :type db_name: str
        """
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.service_alerts = self.db["ServiceAlerts"]
        self.consolidated = self.db["ConsolidatedData"]
        self.semaphore = asyncio.Semaphore(10)  # Limit concurrency

    async def get_expiring_alerts(self) -> List[Dict[str, Any]]:
        """
        Step 1: Fetch certificates needing attention from the last hour.
        
        :return: A list of flattened alert objects.
        :rtype: List[Dict[str, Any]]
        """
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        
        pipeline = [
            {"$match": {"log_datetime": {"$gte": one_hour_ago}}},
            {"$unwind": "$certificates"},
            {"$match": {"certificates.attention_required": True}},
            {
                "$project": {
                    "cluster_name": 1,
                    "namespace": 1,
                    "object_name": 1,
                    "csi_id": 1,
                    "log_datetime": 1,
                    "dn": "$certificates.distinguished_name",
                    "days": "$certificates.days_to_expiration",
                    "expiry": "$certificates.expiration_date",
                    "sn": "$certificates.serial_number"
                }
            }
        ]
        
        cursor = self.service_alerts.aggregate(pipeline)
        return await cursor.to_list(length=None)

    async def find_matches_for_dn(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Steps 2 & 3: Find potential renewals in ConsolidatedData and score them.
        
        :param alert: The alert document from Step 1.
        :type alert: Dict[str, Any]
        :return: Result dictionary with match list.
        :rtype: Dict[str, Any]
        """
        async with self.semaphore:
            seven_days_ago = datetime.now(UTC) - timedelta(days=7)
            
            # Optimization: Filter by CSI_ID first to avoid global regex scan
            query = {
                "csi_application_id": alert["csi_id"],
                "status": "Valid",
                "source_properties.environment": {"$in": ["prod", "PRODUCTION"]},
                "log_date": {"$gte": seven_days_ago},
                "days_to_expiration": {"$gt": alert["days"], "$lt": 1500} # Exclude obvious signers
            }

            potential_matches = []
            cursor = self.consolidated.find(query).sort("expiration_date", -1)
            
            async for doc in cursor:
                target_dn = doc["distinguished_name"]
                
                # RapidFuzz Logic
                p_score = fuzz.partial_ratio(alert["dn"].lower(), target_dn.lower())
                t_score = fuzz.token_set_ratio(alert["dn"].lower(), target_dn.lower())
                max_score = max(p_score, t_score)

                if max_score >= 80:  # 80% similarity threshold
                    potential_matches.append({
                        "distinguished_name": target_dn,
                        "days_to_expiration": doc["days_to_expiration"],
                        "expiration_date": doc["expiration_date"],
                        "serial_number": doc["source_properties"].get("serial_number"),
                        "similarity_score": round(max_score, 2)
                    })

            # Sort by expiration date descending and limit to 3
            potential_matches.sort(key=lambda x: x["expiration_date"], reverse=True)
            
            return {
                "cluster_name": alert["cluster_name"],
                "namespace": alert["namespace"],
                "object_name": alert["object_name"],
                "csi_id": alert["csi_id"],
                "distinguished_name": alert["dn"],
                "days_to_expiration": alert["days"],
                "expiration_date": alert["expiry"],
                "serial_number": alert["sn"],
                "certificates_match": potential_matches[:3],
                "log_datetime": alert["log_datetime"]
            }

    async def process(self) -> List[Dict[str, Any]]:
        """
        Orchestrates the lookup and matching process.
        
        :return: Final list of enriched alerts.
        :rtype: List[Dict[str, Any]]
        """
        logger.info("Fetching expiring alerts...")
        alerts = await self.get_expiring_alerts()
        
        if not alerts:
            logger.info("No new alerts found in the last hour.")
            return []

        logger.info(f"Processing matches for {len(alerts)} certificates...")
        tasks = [self.find_matches_for_dn(a) for a in alerts]
        results = await asyncio.gather(*tasks)
        
        # Sort final results by days_to_expiration (soonest first: 1 -> 7)
        results.sort(key=lambda x: x["days_to_expiration"])
        return results

    def generate_email_html(self, results: List[Dict[str, Any]]) -> str:
        """
        Generates a modern HTML report.
        """
        table_rows = ""
        match_rows = ""

        for idx, r in enumerate(results, 1):
            # Table 1 Rows
            table_rows += f"""
            <tr>
                <td>{idx}</td>
                <td>{r['csi_id']}</td>
                <td><b>{r['cluster_name']}</b><br>{r['namespace']}<br>{r['object_name']}</td>
                <td style="font-family:monospace; font-size:11px;">{r['distinguished_name']}<br><small>SN: {r['serial_number']}</small></td>
                <td style="text-align:center; color:{'red' if r['days_to_expiration'] < 3 else 'orange'};"><b>{r['days_to_expiration']}</b></td>
                <td>{r['expiration_date'].strftime('%Y-%m-%d %H:%M')}</td>
            </tr>
            """
            
            # Table 2 Rows (Matches)
            matches_html = ""
            if not r['certificates_match']:
                matches_html = "<td colspan='3' style='color:#999;'>No matches found in database</td>"
            else:
                for m in r['certificates_match']:
                    matches_html += f"""
                    <td style="font-size:11px; background-color:#f0fff4; border:1px solid #c3e6cb;">
                        <b>Score: {m['similarity_score']}%</b><br>
                        {m['distinguished_name']}<br>
                        <small>SN: {m['serial_number']}</small><br>
                        Exp: {m['expiration_date'].strftime('%Y-%m-%d')}
                    </td>
                    """
                # Fill empty cells if less than 3 matches
                for _ in range(3 - len(r['certificates_match'])):
                    matches_html += "<td></td>"

            match_rows += f"""
            <tr>
                <td style="font-family:monospace; font-size:11px; background:#fff5f5;">{r['distinguished_name']}</td>
                {matches_html}
            </tr>
            """

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; border: 1px solid #dee2e6; }}
                th {{ background-color: #004a99; color: white; padding: 12px; text-align: left; font-size: 13px; }}
                td {{ padding: 10px; border: 1px solid #dee2e6; font-size: 13px; vertical-align: top; }}
                tr:nth-child(even) {{ background-color: #f8f9fa; }}
                .match-header {{ background-color: #28a745; }}
                .note {{ background: #e9ecef; padding: 15px; border-left: 5px solid #004a99; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h2>Production Certificate Expiration Report</h2>
            <div class="note">
                The following certificates are expiring soon and require manual intervention. 
                We have analyzed the database and found potential renewals (matches) based on naming patterns.
            </div>
            
            <h3>1. Certificates Expiring (Action Required)</h3>
            <table>
                <tr>
                    <th>S.No.</th><th>CSI</th><th>Service Details</th><th>Expiring Certificate</th><th>Days</th><th>Expiration Date</th>
                </tr>
                {table_rows}
            </table>

            <h3>2. Potential Renewal Matches Found</h3>
            <p>We found these certificates in the database that might be the intended renewals for the expiring ones above:</p>
            <table>
                <tr>
                    <th style="background:#d9534f;">Expiring Certificate</th>
                    <th class="match-header">Match 1 (Newest)</th>
                    <th class="match-header">Match 2</th>
                    <th class="match-header">Match 3</th>
                </tr>
                {match_rows}
            </table>
        </body>
        </html>
        """
        return html

async def main():
    engine = CertificateMatcherEngine("mongodb://uri", "db_name")
    results = await engine.process()
    if results:
        email_body = engine.generate_email_html(results)
        # Add your SMTP sending logic here
        print("Report Generated Successfully.")

if __name__ == "__main__":
    asyncio.run(main())
