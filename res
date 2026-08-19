async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: list[str] | None = None,
        ) -> None:

        """
        Sends a rich HTML email to a specific recipient without blocking the event loop.
        Used by the zelle facade for per-attempt maintenance notifications; unlike
        send_alert there is no production gate (the caller owns that switch) and the
        recipient comes from the caller, not the developers list.

        :param to: Recipient email address.
        :type to: str
        :param subject: Email subject.
        :type subject: str
        :param html_body: HTML email body.
        :type html_body: str
        :param cc: Optional CC recipient addresses.
        :type cc: list[str] | None
        :return: None
        """

        def _sync_send() -> None:

            """Synchronous email sending function."""

            message = EmailMessage()
            message.set_content(html_body, subtype="html")

            message["Subject"] = subject
            message["From"] = self.from_address
            message["To"] = to
            if cc:
                message["Cc"] = ", ".join(cc)

            # endIf

            try:
                with smtplib.SMTP(self.smtp_server) as server:
                    server.send_message(message)

                # endWith

            except Exception as smtplib_exception:
                logger.error(f"EmailService SMTP Error: {smtplib_exception}")

            # endTryExcept

        # endDef

        await asyncio.to_thread(_sync_send)

    # endAsyncDef
