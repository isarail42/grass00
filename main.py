import asyncio
import random
import ssl
import os
import json
import time
import uuid
from datetime import datetime, timedelta
import requests
from loguru import logger
from fake_useragent import UserAgent

# User Agent for the requests
user_agent = UserAgent(os='windows', browsers='chrome')
random_user_agent = user_agent.random

# Webshare API settings (you'll need to fill in the API key and endpoint)
API_KEY = 'your_webshare_api_key_here'  # Replace with your actual API key
PROXY_COUNT = 50  # Number of proxies per account
ROTATION_INTERVAL = 86400  # 24 hours for proxy rotation

def log_rotation_time():
    current_time = datetime.now()
    next_rotation = current_time + timedelta(seconds=ROTATION_INTERVAL)
    logger.info(f"Current proxy rotation: {current_time.strftime('%H:%M:%S')}")
    logger.info(f"Next proxy rotation: {next_rotation.strftime('%H:%M:%S')}")

# Create new Webshare account and get proxies
def create_account():
    register_url = "https://proxy.webshare.io/api/account/register/"
    data = {
        'email': f'user_{str(uuid.uuid4())[:8]}@example.com',  # Generate random email
        'password': 'secure_password',  # Generate secure password
    }
    headers = {
        'Authorization': f'Bearer {API_KEY}'
    }
    
    response = requests.post(register_url, data=data, headers=headers)
    if response.status_code == 200:
        account_details = response.json()
        username = account_details['username']
        password = account_details['password']
        logger.info(f"Account created: {username}")
        return username, password
    else:
        logger.error(f"Failed to create account: {response.text}")
        return None

def get_proxies(account_username, account_password):
    proxy_url = "https://proxy.webshare.io/api/proxy/list/"
    auth = (account_username, account_password)
    
    response = requests.get(proxy_url, auth=auth)
    if response.status_code == 200:
        proxies = response.json().get('results', [])
        return [proxy['proxy'] for proxy in proxies]
    else:
        logger.error(f"Failed to fetch proxies: {response.text}")
        return []

async def connect_to_wss(socks5_proxy, user_id, is_premium=False):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Connecting with Device ID: {device_id}")
    
    device_type = "desktop" if is_premium else "extension"
    version = "4.28.1" if is_premium else "4.26.2"
    extension_id = "lkbnfiajjmbhnfledhphioinpickokdi" if not is_premium else None

    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            urilist = ["wss://proxy.wynd.network:4444/","wss://proxy.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(f"Sending PING: {send_message}")
                        await websocket.send(send_message)
                        await asyncio.sleep(5)
                await asyncio.sleep(1)
                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(f"Received message: {message}")
                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": custom_headers['User-Agent'],
                                "timestamp": int(time.time()),
                                "device_type": device_type,
                                "version": version
                            }
                        }
                        if extension_id:
                            auth_response["result"]["extension_id"] = extension_id
                            
                        logger.debug(f"Sending AUTH response: {auth_response}")
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(f"Sending PONG response: {pong_response}")
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            logger.error(f"Error with proxy {socks5_proxy}: {e}")

async def rotate_proxies():
    while True:
        tasks = []
        try:
            # Create new account and fetch proxies
            username, password = create_account()
            if username and password:
                proxies = get_proxies(username, password)
                selected_proxies = random.sample(proxies, min(PROXY_COUNT, len(proxies)))
                logger.info(f"Selected {len(selected_proxies)} proxies")
                
                with open('user.txt', 'r') as file:
                    user_ids = [line.strip() for line in file.readlines() if line.strip()]
                if not user_ids:
                    logger.error("user.txt file is empty or has no valid user IDs")
                    return
                
                for user_id in user_ids:
                    logger.info(f"Starting connection for User ID: {user_id}")
                    for proxy in selected_proxies:
                        tasks.append(asyncio.create_task(connect_to_wss(proxy, user_id)))
                    
                try:
                    await asyncio.wait_for(asyncio.gather(*tasks), timeout=ROTATION_INTERVAL)
                except asyncio.TimeoutError:
                    for task in tasks:
                        task.cancel()
                    logger.info("Proxy rotation: 24 hours have passed, getting new proxies...")

        except FileNotFoundError:
            logger.error("user.txt file not found")
            await asyncio.sleep(ROTATION_INTERVAL)
            continue

async def main():
    while True:
        try:
            await rotate_proxies()
        except Exception as e:
            logger.error(f"Error in proxy rotation: {e}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
