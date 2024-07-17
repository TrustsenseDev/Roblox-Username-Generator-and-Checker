import requests
import random
import string
import time
import concurrent.futures
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt
from rich.layout import Layout

console = Console()

def fetch_proxies(country='de', limit=20):
    url = f"https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&country={country}&ssl=all&anonymity=all&limit={limit}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            proxies = response.text.strip().split('\r\n')
            return [proxy for proxy in proxies if proxy]  # no empty strings pls
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching proxies: {e}[/bold red]")
    return []

def fetch_english_words(min_length=3, max_length=5, limit=100):
    url = f"https://random-word-api.herokuapp.com/word?number={limit}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            words = response.json()
            # this will filter by length
            filtered_words = [word for word in words if min_length <= len(word) <= max_length]
            return filtered_words
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching English words: {e}[/bold red]")
    return []

working_proxies = set()

def check_roblox_username(username, proxy=None):
    url = f"https://auth.roblox.com/v1/usernames/validate?request.username={username}&request.birthday=2000-01-01"
    try:
        if proxy:
            response = requests.get(url, proxies={'http': f'http://{proxy}', 'https': f'http://{proxy}'}, timeout=5)
        else:
            response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return username if data.get('code') == 0 else None
        elif response.status_code == 429:  # Too Many Requests
            time.sleep(0.1)  # Reduced wait time for faster checks
            return None
    except requests.RequestException:
        if proxy:
            working_proxies.discard(proxy)
        return None
    return None

def generate_username(min_length, max_length, use_english_words=False):
    length = random.randint(min_length, max_length)
    if use_english_words:
        words = fetch_english_words(min_length=length, max_length=length, limit=100)
        return random.choice(words) if words else None
    else:
        characters = string.ascii_letters + string.digits + '_'
        return ''.join(random.choices(characters, k=length))

def generate_and_check_usernames(num_usernames=5, use_proxies=True, use_english_words=False, min_length=5, max_length=20):
    available_usernames = []
    total_checked = 0
    
    progress = Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TextColumn("[bold blue]{task.fields[username]}"),
    )
    
    task = progress.add_task("[cyan]Checking usernames...", total=num_usernames, username="")

    def check_single_username():
        nonlocal total_checked
        username = generate_username(min_length, max_length, use_english_words)
        if not username:
            return None
        proxy = random.choice(list(working_proxies)) if use_proxies and working_proxies else None
        progress.update(task, description=f"[cyan]Checking[/cyan] [bold yellow]{username}[/bold yellow]")
        result = check_roblox_username(username, proxy)
        total_checked += 1
        progress.update(task, username=f"Checked: {total_checked}")
        return result

    with Live(progress, refresh_per_second=10):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            while len(available_usernames) < num_usernames:
                if use_proxies and not working_proxies:
                    console.print("[bold yellow]Fetching new proxies...[/bold yellow]")
                    new_proxies = fetch_proxies()
                    working_proxies.update(new_proxies)
                    if not working_proxies:
                        console.print("[bold red]No working proxies found. Switching to direct connections.[/bold red]")
                        use_proxies = False
                
                batch_size = min(100, num_usernames - len(available_usernames))
                futures = [executor.submit(check_single_username) for _ in range(batch_size)]
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        available_usernames.append(result)
                        progress.update(task, advance=1, username=f"Found: {result}")
                        if len(available_usernames) >= num_usernames:
                            break
    
    return available_usernames, total_checked

def main():
    console.clear()
    console.print(Panel.fit(
        "[bold green]Fast Roblox Username Generator and Checker[/bold green]",
        border_style="bold",
        padding=(1, 1)
    ))

    use_proxies = Prompt.ask(
        "[bold yellow]Do you want to use proxies?[/bold yellow]",
        choices=["yes", "no"],
        default="yes"
    ) == "yes"

    use_english_words = Prompt.ask(
        "[bold yellow]Do you want to use English words for usernames?[/bold yellow]",
        choices=["yes", "no"],
        default="no"
    ) == "yes"

    min_length = int(Prompt.ask(
        "[bold yellow]Enter the minimum username length[/bold yellow]",
        default="5"
    ))

    max_length = int(Prompt.ask(
        "[bold yellow]Enter the maximum username length[/bold yellow]",
        default="20"
    ))
    
    if use_proxies:
        console.print("[bold cyan]Fetching proxies from API...[/bold cyan]")
        initial_proxies = fetch_proxies()
        working_proxies.update(initial_proxies)
        console.print(f"[bold cyan]Fetched {len(working_proxies)} proxies for checking.[/bold cyan]")
    else:
        console.print("[bold cyan]Not using proxies. Checks will be performed directly.[/bold cyan]")
    
    num_usernames = int(Prompt.ask(
        "[bold yellow]How many usernames do you want to generate?[/bold yellow]",
        default="5"
    ))
    
    console.print("\n[bold cyan]Generating and checking usernames...[/bold cyan]")
    available_usernames, total_checked = generate_and_check_usernames(num_usernames, use_proxies, use_english_words, min_length, max_length)
    
    result_table = Table(show_header=True, header_style="bold magenta")
    result_table.add_column("Available Usernames", style="cyan", width=20)
    result_table.add_column("Total Checked", style="green", width=15)
    result_table.add_column("Success Rate", style="yellow", width=15)
    
    for username in available_usernames:
        result_table.add_row(username, "", "")
    
    success_rate = (len(available_usernames) / total_checked) * 100 if total_checked > 0 else 0
    result_table.add_row("", str(total_checked), f"{success_rate:.2f}%")
    
    console.print(Panel(result_table, title="[bold]Results[/bold]", expand=False))
    
    if use_proxies:
        console.print(f"\n[bold cyan]Working proxies: {len(working_proxies)}[/bold cyan]")
        if working_proxies:
            console.print("[green]Working proxy list:[/green]")
            for proxy in working_proxies:
                console.print(f"- {proxy}")
        else:
            console.print("[bold red]No working proxies found.[/bold red]")
    
    console.print("\n[bold yellow]Thank you for using the Roblox Username Generator and Checker![/bold yellow]")

if __name__ == "__main__":
    main()
