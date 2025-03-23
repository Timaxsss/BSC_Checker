import http.server
import socketserver
import json
import random
import time
import tls_client
from urllib.parse import urlparse, parse_qs
from fake_useragent import UserAgent

PORT = 8000

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.sendRequest = tls_client.Session(client_identifier='chrome_103')
        super().__init__(*args, **kwargs)

    def end_headers(self):
        # Add CORS headers for all responses
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def randomise(self):
        self.identifier = random.choice([browser for browser in tls_client.settings.ClientIdentifiers.__args__ if browser.startswith(('chrome', 'safari', 'firefox', 'opera'))])
        self.sendRequest = tls_client.Session(random_tls_extension_order=True, client_identifier=self.identifier)
        self.sendRequest.timeout_seconds = 60

        parts = self.identifier.split('_')
        identifier, version, *rest = parts
        other = rest[0] if rest else None
        
        os = 'windows'
        if identifier == 'opera':
            identifier = 'chrome'
        elif version == 'ios':
            os = 'ios'

        ua = UserAgent(browsers=[identifier], os=[os], fallback='firefox')
        self.user_agent = ua.random

        self.headers = {
            'Host': 'gmgn.ai',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': 'https://gmgn.ai/?chain=bsc',
            'user-agent': self.user_agent
        }

    def do_GET(self):
        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Serve static files
        if path == '/':
            self.path = '/index.html'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        elif path == '/api/proxy':
            # Handle API proxy requests
            try:
                wallet = query_params.get('wallet', [''])[0]
                req_type = query_params.get('type', [''])[0]
                period = query_params.get('period', ['7d'])[0]

                if not wallet or not req_type:
                    self.send_error(400, "Missing wallet or type parameter")
                    return

                if req_type == 'wallet_data':
                    data = self.get_wallet_data(wallet, period)
                elif req_type == 'token_distro':
                    data = self.get_token_distro(wallet)
                elif req_type == 'token_top_traders':
                    data = self.get_token_top_traders(wallet)
                else:
                    self.send_error(400, "Invalid request type")
                    return

                # Send response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            except Exception as e:
                print(f"Error: {e}")
                self.send_error(500, str(e))
        else:
            # Serve other static files
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def get_wallet_data(self, wallet, period='7d'):
        url = f"https://gmgn.ai/defi/quotation/v1/smartmoney/bsc/walletNew/{wallet}?period={period}"
        retries = 5
        
        for attempt in range(retries):
            try:
                self.randomise()
                response = self.sendRequest.get(url, headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    if data['msg'] == "success":
                        return data
                    else:
                        raise Exception("Failed to fetch data from API")
            except Exception as e:
                print(f"Attempt {attempt+1} failed: {e}")
                time.sleep(1)
        
        raise Exception(f"Could not fetch data after {retries} attempts")
    
    def get_token_top_traders(self, contract_address):
        url = f"https://gmgn.ai/defi/quotation/v1/tokens/top_traders/bsc/{contract_address}?orderby=profit&direction=desc"
        retries = 3

        for attempt in range(retries):
            try:
                self.randomise()
                response = self.sendRequest.get(url, headers=self.headers, allow_redirects=True)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data'):
                        return {'msg': 'success', 'data': data['data']}
            except Exception as e:
                print(f"Attempt {attempt+1} failed for token_top_traders: {e}")
                time.sleep(1)
        
        return {'msg': 'error', 'data': []}

    def get_token_distro(self, wallet):
        url = f"https://gmgn.ai/defi/quotation/v1/rank/bsc/wallets/{wallet}/unique_token_7d?interval=30d"
        retries = 3
        tokenDistro = []

        for attempt in range(retries):
            try:
                self.randomise()
                response = self.sendRequest.get(url, headers=self.headers, allow_redirects=True)
                if response.status_code == 200:
                    data = response.json()
                    tokenDistro = data['data']['tokens']
                    if tokenDistro:
                        break
            except Exception as e:
                print(f"Attempt {attempt+1} failed for token_distro: {e}")
                time.sleep(1)
        
        if not tokenDistro:
            return {"No Token Distribution Data": None}

        FiftyPercentOrMore = 0
        ZeroToFifty = 0
        FiftyTo100 = 0
        TwoToFour = 0
        FiveToSix = 0
        SixPlus = 0
        NegativeToFifty = 0

        for profit in tokenDistro:
            total_profit_pnl = profit.get('total_profit_pnl')
            if total_profit_pnl is not None:
                profitMultiplier = total_profit_pnl * 100

                if profitMultiplier <= -50:
                    FiftyPercentOrMore += 1
                elif -50 < profitMultiplier < 0:
                    NegativeToFifty += 1
                elif 0 <= profitMultiplier < 50:
                    ZeroToFifty += 1
                elif 50 <= profitMultiplier < 199:
                    FiftyTo100 += 1
                elif 200 <= profitMultiplier < 499:
                    TwoToFour += 1
                elif 500 <= profitMultiplier < 600:
                    FiveToSix += 1
                elif profitMultiplier >= 600:
                    SixPlus += 1

        return {
            "-50% +": FiftyPercentOrMore,
            "0% - -50%": NegativeToFifty,
            "0 - 50%": ZeroToFifty,
            "50% - 199%": FiftyTo100,
            "200% - 499%": TwoToFour,
            "500% - 600%": FiveToSix,
            "600% +": SixPlus
        }

# Start the server
with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
    print(f"Server started on port {PORT}")
    httpd.serve_forever()