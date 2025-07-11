class DrainStatusAPIService:
    def __init__(self) -> None:
        self.http_client_config = HttpClientConfig(
            base_url=DRAINSTATUS_API_CONFIGS.get("base_url", "http://localhost"),
            default_headers=DRAINSTATUS_API_CONFIGS.get("swdc").get("headers"),
        )

    async def get_datacenter_status(self) -> tuple[bool, dict[str, str]]:
        get_status: dict[str, str] = {}
        final_status: bool = True

        async with AsyncHttpClient(self.http_client_config) as client:
            try:
                gtdc_response = await client.post(
                    endpoint=DRAINSTATUS_API_CONFIGS.get("gtdc").get("slug"),
                    json=DRAINSTATUS_API_CONFIGS.get("gtdc").get("body"),
                )
                swdc_response = await client.post(
                    endpoint=DRAINSTATUS_API_CONFIGS.get("swdc").get("slug"),
                    json=DRAINSTATUS_API_CONFIGS.get("gtdc").get("body"),
                )
                gtdc_response.raise_for_status()
                swdc_response.raise_for_status()

                if gtdc_response.status_code != 200:
                    get_status["gtdc"] = f"{gtdc_response.status_code}: {gtdc_response.reason}"
                    final_status = False

                if swdc_response.status_code != 200:
                    get_status["swdc"] = f"{swdc_response.status_code}: {swdc_response.reason}"
                    final_status = False

                get_status["gtdc"] = gtdc_response.json()[0].get("status", None)
                get_status["swdc"] = swdc_response.json()[0].get("status", None)

            except HttpClientError as http_client_error:
                get_status["gtdc"] = str(http_client_error)
                get_status["swdc"] = str(http_client_error)
                final_status = False

        return final_status, get_status