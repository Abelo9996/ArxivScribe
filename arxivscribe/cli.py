"""ArxivScribe CLI — fetch, search, and manage arXiv papers from the terminal."""
import asyncio
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

# Resolve config path
def _find_config():
    """Find config.yaml — check CWD, then package dir."""
    candidates = [
        Path.cwd() / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _load_deps(config_path=None):
    """Load config, DB, fetcher, summarizer."""
    import yaml
    from dotenv import load_dotenv
    load_dotenv()

    if config_path is None:
        config_path = _find_config()
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    return config


async def _get_db(config):
    from arxivscribe.storage.db import DatabaseManager
    db_path = config.get('storage', {}).get('database_path', 'arxivscribe.db')
    db = DatabaseManager(db_path)
    await db.initialize()
    return db


async def _get_fetcher(config):
    from arxivscribe.arxiv.fetcher import ArxivFetcher
    arxiv_cfg = config.get('arxiv', {})
    return ArxivFetcher(
        max_results_per_category=arxiv_cfg.get('max_results_per_category', 50),
        rate_limit_seconds=arxiv_cfg.get('rate_limit_seconds', 3.0)
    )


async def _get_summarizer(config):
    from arxivscribe.llm.summarizer import Summarizer
    llm_cfg = config.get('llm', {})
    provider = llm_cfg.get('provider', 'openai')

    # Try multiple API key sources
    api_key = None
    for env_var in [f"{provider.upper()}_API_KEY", "OPENAI_API_KEY"]:
        api_key = os.getenv(env_var)
        if api_key:
            break

    if not api_key:
        return None

    try:
        return Summarizer(
            provider=provider, api_key=api_key,
            model=llm_cfg.get('model'),
            max_concurrent=llm_cfg.get('max_concurrent', 5)
        )
    except Exception:
        return None


@click.group()
@click.version_option(version="1.0.0", prog_name="ArxivScribe")
def cli():
    """ArxivScribe — AI-powered arXiv paper digests."""
    pass


@cli.command()
@click.option('--categories', '-c', help='Comma-separated arXiv categories (e.g. cs.LG,cs.AI)')
@click.option('--keywords', '-k', help='Comma-separated keywords to filter by')
@click.option('--limit', '-l', default=50, help='Max papers per category')
@click.option('--no-summarize', is_flag=True, help='Skip AI summarization')
def fetch(categories, keywords, limit, no_summarize):
    """Fetch new papers from arXiv."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        fetcher = await _get_fetcher(config)

        cats = categories.split(',') if categories else config.get('arxiv', {}).get('categories', ['cs.LG', 'cs.AI'])

        with console.status("[bold blue]Fetching papers from arXiv..."):
            papers = await fetcher.fetch_papers(categories=cats, max_results=limit)

        if not papers:
            console.print("[yellow]No papers found.[/yellow]")
            await db.close()
            return

        console.print(f"[green]Fetched {len(papers)} papers[/green]")

        # Filter by keywords
        if keywords:
            from arxivscribe.bot.filters import KeywordFilter
            kw_list = [k.strip() for k in keywords.split(',')]
            filtered = KeywordFilter.filter_papers_by_keywords(papers, kw_list)
            papers = [p for p, _ in filtered]
            console.print(f"[blue]Filtered to {len(papers)} papers matching: {', '.join(kw_list)}[/blue]")
        else:
            # Use stored subscriptions
            subs = await db.get_channel_subscriptions(0, 0)
            if subs:
                from arxivscribe.bot.filters import KeywordFilter
                filtered = KeywordFilter.filter_papers_by_keywords(papers, subs)
                papers = [p for p, _ in filtered]
                console.print(f"[blue]Filtered to {len(papers)} papers matching subscriptions: {', '.join(subs)}[/blue]")

        if not papers:
            console.print("[yellow]No papers matched filters.[/yellow]")
            await db.close()
            return

        # Summarize
        if not no_summarize:
            summarizer = await _get_summarizer(config)
            if summarizer:
                with console.status("[bold blue]Generating AI summaries..."):
                    papers = await summarizer.batch_summarize(papers)
                console.print(f"[green]Summarized {len(papers)} papers[/green]")
            else:
                console.print("[dim]No API key — skipping summaries (set OPENAI_API_KEY for AI summaries)[/dim]")

        # Store
        stored = 0
        for paper in papers:
            if not await db.is_paper_stored(paper['id']):
                await db.store_paper_local(paper)
                stored += 1

        await db.update_last_fetch_time()
        console.print(f"[green bold]Done![/green bold] {stored} new papers stored, {len(papers) - stored} already in DB")

        # Show top 5
        _print_papers(papers[:5])

        await db.close()

    asyncio.run(_run())


@cli.command()
@click.argument('query')
@click.option('--count', '-n', default=10, help='Number of results')
@click.option('--summarize/--no-summarize', default=False, help='Generate AI summaries')
def search(query, count, summarize):
    """Search arXiv for papers."""
    async def _run():
        config = _load_deps()
        fetcher = await _get_fetcher(config)

        with console.status(f"[bold blue]Searching arXiv for '{query}'..."):
            papers = await fetcher.search_papers(query, max_results=count)

        if not papers:
            console.print(f"[yellow]No papers found for '{query}'[/yellow]")
            return

        if summarize:
            summarizer = await _get_summarizer(config)
            if summarizer:
                with console.status("[bold blue]Generating summaries..."):
                    papers = await summarizer.batch_summarize(papers)

        console.print(f"\n[bold]Found {len(papers)} papers for '[cyan]{query}[/cyan]':[/bold]\n")
        _print_papers(papers)

    asyncio.run(_run())


@cli.command('list')
@click.option('--sort', type=click.Choice(['date', 'votes', 'title']), default='date')
@click.option('--limit', '-l', default=20)
@click.option('--keyword', '-k', help='Filter by keyword')
def list_papers(sort, limit, keyword):
    """List stored papers."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        papers = await db.get_recent_papers(limit=limit, sort=sort, keyword=keyword)

        if not papers:
            console.print("[yellow]No papers in database. Run 'arxivscribe fetch' first.[/yellow]")
            await db.close()
            return

        total = await db.count_papers(keyword=keyword)
        console.print(f"\n[bold]Showing {len(papers)} of {total} papers[/bold] (sort: {sort})\n")
        _print_papers(papers)
        await db.close()

    asyncio.run(_run())


@cli.command()
@click.argument('keyword')
def subscribe(keyword):
    """Add a keyword subscription."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        keywords = [k.strip().lower() for k in keyword.split(',') if k.strip()]
        added = []
        for kw in keywords:
            if await db.add_subscription(0, 0, kw):
                added.append(kw)
        await db.close()
        if added:
            console.print(f"[green]Subscribed to: {', '.join(added)}[/green]")
        else:
            console.print(f"[yellow]Already subscribed to: {', '.join(keywords)}[/yellow]")

    asyncio.run(_run())


@cli.command()
@click.argument('keyword')
def unsubscribe(keyword):
    """Remove a keyword subscription."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        keywords = [k.strip().lower() for k in keyword.split(',') if k.strip()]
        removed = []
        for kw in keywords:
            if await db.remove_subscription(0, 0, kw):
                removed.append(kw)
        await db.close()
        if removed:
            console.print(f"[green]Unsubscribed from: {', '.join(removed)}[/green]")
        else:
            console.print(f"[yellow]Not subscribed to: {', '.join(keywords)}[/yellow]")

    asyncio.run(_run())


@cli.command()
def subscriptions():
    """List active keyword subscriptions."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        subs = await db.get_all_subscriptions()
        await db.close()

        if subs:
            console.print("\n[bold]Active subscriptions:[/bold]")
            for kw in subs:
                console.print(f"  [cyan]•[/cyan] {kw}")
            console.print()
        else:
            console.print("[yellow]No subscriptions. Use 'arxivscribe subscribe \"keyword\"' to add one.[/yellow]")

    asyncio.run(_run())


@cli.command()
@click.option('--format', '-f', 'fmt', type=click.Choice(['bibtex', 'markdown', 'csv', 'json']), default='bibtex')
@click.option('--output', '-o', help='Output file (default: stdout)')
@click.option('--limit', '-l', default=100)
@click.option('--keyword', '-k', help='Filter by keyword')
def export(fmt, output, limit, keyword):
    """Export papers to BibTeX, Markdown, CSV, or JSON."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        papers = await db.get_recent_papers(limit=limit, keyword=keyword)
        await db.close()

        if not papers:
            console.print("[yellow]No papers to export.[/yellow]")
            return

        from arxivscribe.export import export_bibtex, export_markdown, export_csv, export_json
        exporters = {
            'bibtex': export_bibtex,
            'markdown': export_markdown,
            'csv': export_csv,
            'json': export_json
        }

        result = exporters[fmt](papers)

        if output:
            Path(output).write_text(result, encoding='utf-8')
            console.print(f"[green]Exported {len(papers)} papers to {output}[/green]")
        else:
            click.echo(result)

    asyncio.run(_run())


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', '-p', default=8000, help='Port to bind to')
@click.option('--open/--no-open', default=True, help='Open browser automatically')
def serve(host, port, open):
    """Start the web UI."""
    import uvicorn
    import webbrowser

    console.print(f"\n  [bold]ArxivScribe[/bold] running at [cyan]http://{host}:{port}[/cyan]\n")

    if open:
        webbrowser.open(f"http://{host}:{port}")

    # Need to set CWD to package dir for config.yaml
    config_path = _find_config()
    if config_path:
        os.chdir(Path(config_path).parent)

    uvicorn.run("main:app", host=host, port=port, log_level="info")


@cli.command()
def stats():
    """Show database statistics."""
    async def _run():
        config = _load_deps()
        db = await _get_db(config)
        s = await db.get_global_stats()
        subs = await db.get_all_subscriptions()
        await db.close()

        panel = Panel(
            f"[bold]Papers:[/bold]     {s['total_papers']}\n"
            f"[bold]Keywords:[/bold]   {s['total_subscriptions']}\n"
            f"[bold]Votes:[/bold]      {s['total_votes']}\n"
            f"[bold]Last fetch:[/bold] {s.get('last_fetch', 'Never')}\n"
            f"[bold]Keywords:[/bold]   {', '.join(subs) if subs else 'None'}",
            title="ArxivScribe Stats",
            border_style="blue"
        )
        console.print(panel)

    asyncio.run(_run())


def _print_papers(papers):
    """Pretty-print papers using Rich."""
    table = Table(box=box.ROUNDED, show_lines=True, width=min(console.width, 120))
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold", max_width=50)
    table.add_column("Authors", style="dim", max_width=25)
    table.add_column("Date", width=10)
    table.add_column("Score", justify="center", width=5)

    for i, paper in enumerate(papers, 1):
        authors = paper.get('authors', [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(',')]
        author_str = ", ".join(authors[:2])
        if len(authors) > 2:
            author_str += f" +{len(authors) - 2}"

        date = (paper.get('published', '') or paper.get('fetched_at', '') or '')[:10]
        score = str(paper.get('score', 0))

        title = paper.get('title', 'Untitled')
        if len(title) > 80:
            title = title[:77] + "..."

        table.add_row(str(i), title, author_str, date, score)

    console.print(table)

    # Print summaries below if available
    for i, paper in enumerate(papers, 1):
        summary = paper.get('summary', '')
        if summary and summary != "No summary available.":
            console.print(f"  [dim]{i}.[/dim] [italic]{summary}[/italic]")
    console.print()


if __name__ == '__main__':
    cli()
