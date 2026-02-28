"""Email digest system for ArxivScribe — sends daily/weekly paper summaries."""
import asyncio
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)


class DigestMailer:
    """Sends scheduled email digests of new papers."""

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_pass: str = "",
        from_addr: str = "",
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.from_addr = from_addr or smtp_user

    async def send_digest(self, to_addr: str, papers: List[dict], subject: str = None):
        """Send a paper digest email."""
        if not papers:
            logger.info("No papers to send in digest")
            return False

        if not subject:
            subject = f"ArxivScribe Digest — {len(papers)} papers ({datetime.now().strftime('%b %d, %Y')})"

        html = self._build_html(papers)
        plain = self._build_plain(papers)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"ArxivScribe <{self.from_addr}>"
        msg["To"] = to_addr
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            # Run SMTP in thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, to_addr, msg)
            logger.info(f"Digest sent to {to_addr} with {len(papers)} papers")
            return True
        except Exception as e:
            logger.error(f"Failed to send digest to {to_addr}: {e}")
            return False

    def _send_smtp(self, to_addr: str, msg: MIMEMultipart):
        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.from_addr, to_addr, msg.as_string())

    def _build_html(self, papers: List[dict]) -> str:
        rows = ""
        for i, p in enumerate(papers, 1):
            authors = p.get('authors', [])
            if isinstance(authors, list):
                authors = ", ".join(authors[:3])
                if len(p.get('authors', [])) > 3:
                    authors += f" +{len(p['authors']) - 3} more"
            cats = p.get('categories', [])
            if isinstance(cats, list):
                cats = ", ".join(cats[:3])
            summary = p.get('summary', '')
            title = p.get('title', 'Untitled')
            url = p.get('url', '')
            pdf = p.get('pdf_url', '')

            rows += f"""
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:16px 0;">
                    <div style="font-size:15px;font-weight:600;margin-bottom:4px;">
                        <a href="{url}" style="color:#1a73e8;text-decoration:none;">{i}. {title}</a>
                    </div>
                    <div style="font-size:12px;color:#666;margin-bottom:6px;">{authors}</div>
                    {f'<div style="font-size:13px;color:#333;margin-bottom:6px;">{summary}</div>' if summary else ''}
                    <div style="font-size:11px;color:#888;">
                        {cats}
                        {f' &middot; <a href="{pdf}" style="color:#e67700;">PDF</a>' if pdf else ''}
                    </div>
                </td>
            </tr>"""

        return f"""
        <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
            <div style="text-align:center;margin-bottom:24px;">
                <h1 style="font-size:22px;color:#1a1a1a;">ArxivScribe Digest</h1>
                <p style="color:#666;font-size:13px;">{len(papers)} new papers &middot; {datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            <table style="width:100%;border-collapse:collapse;">
                {rows}
            </table>
            <div style="text-align:center;margin-top:24px;padding-top:16px;border-top:1px solid #eee;">
                <p style="font-size:11px;color:#aaa;">
                    Sent by <a href="https://github.com/Abelo9996/ArxivScribe" style="color:#888;">ArxivScribe</a>
                </p>
            </div>
        </body></html>"""

    def _build_plain(self, papers: List[dict]) -> str:
        lines = [f"ArxivScribe Digest — {len(papers)} papers\n{'='*50}\n"]
        for i, p in enumerate(papers, 1):
            title = p.get('title', 'Untitled')
            url = p.get('url', '')
            summary = p.get('summary', '')
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if summary:
                lines.append(f"   {summary}")
            lines.append("")
        lines.append(f"\n---\nSent by ArxivScribe")
        return "\n".join(lines)


class DigestScheduler:
    """Background scheduler that sends digests at configured times."""

    def __init__(self, db, fetcher, summarizer, mailer, categories):
        self.db = db
        self.fetcher = fetcher
        self.summarizer = summarizer
        self.mailer = mailer
        self.categories = categories
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Digest scheduler started")

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Digest scheduler stopped")

    async def _run_loop(self):
        """Check every 5 minutes if any digest needs sending."""
        while True:
            try:
                await self._check_and_send()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Digest scheduler error: {e}")
            await asyncio.sleep(300)  # Check every 5 min

    async def _check_and_send(self):
        """Check digest configs and send if due."""
        configs = await self.db.get_digest_configs()
        now = datetime.utcnow()

        for config in configs:
            if not config.get('enabled'):
                continue

            last_sent = config.get('last_sent')
            schedule = config.get('schedule', 'daily')
            send_hour = config.get('send_hour', 9)

            # Determine if it's time to send
            if last_sent:
                try:
                    last_dt = datetime.fromisoformat(last_sent)
                except ValueError:
                    last_dt = now - timedelta(days=2)

                if schedule == 'daily' and (now - last_dt).total_seconds() < 20 * 3600:
                    continue
                elif schedule == 'weekly' and (now - last_dt).days < 6:
                    continue

            # Check if it's near the send hour
            if abs(now.hour - send_hour) > 1:
                continue

            # Fetch and send
            logger.info(f"Sending digest to {config['target']}...")
            await self._send_digest(config)

    async def _send_digest(self, config: dict):
        """Fetch papers and send digest."""
        from arxivscribe.bot.filters import KeywordFilter

        keywords = config.get('keywords', '').split(',') if config.get('keywords') else []
        categories = config.get('categories', '').split(',') if config.get('categories') else self.categories

        papers = await self.fetcher.fetch_papers(categories=categories, max_results=30)

        if keywords:
            filtered = KeywordFilter.filter_papers_by_keywords(papers, keywords)
            papers = [p for p, _ in filtered]

        if self.summarizer and papers:
            papers = await self.summarizer.batch_summarize(papers)

        if papers:
            success = await self.mailer.send_digest(config['target'], papers)
            if success:
                await self.db.update_digest_last_sent(config['id'])
