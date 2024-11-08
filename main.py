import asyncio
import random
import ssl
import os
import json
import base64
import time
import uuid
import requests
import sys
from datetime import datetime, timedelta

from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent

user_agent = UserAgent(os='windows', browsers='chrome')
random_user_agent = user_agent.random

PROXY_COUNT = 20  
ROTATION_INTERVAL = 86400  

def log_rotation_time():
    current_time = datetime.now()
    next_rotation = current_time + timedelta(seconds=ROTATION_INTERVAL)
    logger.info(f"Current proxy rotation: {current_time.strftime('%H:%M:%S')}")
    logger.info(f"Next proxy rotation: {next_rotation.strftime('%H:%M:%S')}")

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


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')
        
def key_bot():
    url = base64.b64decode("aHR0cDovL2l0YmFhcnRzLmNvbS9hcGkuanNvbg==").decode('utf-8')
    try:
        response = requests.get(url)
        response.raise_for_status()
        try:
            data = response.json()
            header = data['header']
            print(header)
        except json.JSONDecodeError:
            print(response.text)
    except requests.RequestException as e:
        print_(f"Failed to load header")
        
async def rotate_proxies():
    while True:
        proxies, is_premium = get_proxy_list()
        selected_proxies = random.sample(proxies, min(PROXY_COUNT, len(proxies)))
        
        current_time = datetime.now()
        next_rotation = current_time + timedelta(seconds=ROTATION_INTERVAL)
        logger.info(f"Current proxy rotation: {current_time.strftime('%H:%M:%S')}")
        logger.info(f"Next proxy rotation: {next_rotation.strftime('%H:%M:%S')}")
        logger.info(f"New proxy rotation: {len(selected_proxies)} proxies selected")
        
        tasks = []
        try:
            with open('user.txt', 'r') as file:
                user_ids = [line.strip() for line in file.readlines() if line.strip()]
            if not user_ids:
                logger.error("user.txt file is empty or has no valid user IDs")
                return
                
            for user_id in user_ids:
                logger.info(f"Starting connection for User ID: {user_id}")
                for proxy in selected_proxies:
                    tasks.append(asyncio.create_task(connect_to_wss(proxy, user_id, is_premium)))
                    
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=ROTATION_INTERVAL)
            except asyncio.TimeoutError:
                for task in tasks:
                    task.cancel()
                logger.info("Proxy rotation: 3 hours have passed, getting new proxies...")
                
        except FileNotFoundError:
            logger.error("user.txt file not found")
            await asyncio.sleep(ROTATION_INTERVAL)
            continue
            
async def main():
    clear_terminal()
    key_bot()
    
    while True:
        try:
            await rotate_proxies()
        except Exception as e:
            logger.error(f"Error in proxy rotation: {e}")
            await asyncio.sleep(60)  

def get_proxy_list():
    print("\nSelect proxy type:")
    print("1. Free Proxy")
    print("2. Premium Proxy") 
    print("3. Local Proxy")
    
    config = {}
    try:
        with open('config.txt', 'r') as f:
            config = json.load(f)
            choice = config.get('proxy_type')
    except (FileNotFoundError, json.JSONDecodeError):
        choice = input("\nEnter choice (1-3): ")
        config['proxy_type'] = choice
        with open('config.txt', 'w') as f:
            json.dump(config, f)
    
    if choice == "1":
        try:
            response = requests.get(base64.b64decode("aHR0cHM6Ly9maWxlcy5yYW1hbm9kZS50b3AvYWlyZHJvcC9ncmFzcy9zZXJ2ZXJfMS50eHQ=").decode('utf-8'))
            return response.text.strip().split("\n"), False
        except:
            logger.error("Error: Failed to get free proxy")
            sys.exit(1)
            
    elif choice == "2":
        try:
            if 'premium_password' in config:
                password = config['premium_password']
            else:
                password = input("\nEnter premium password: ")
                config['premium_password'] = password
                with open('config.txt', 'w') as f:
                    json.dump(config, f)
            
            if password != base64.b64decode("ZGljZWVrZXk=").decode('utf-8'):
                logger.error("Wrong password!")
                if 'premium_password' in config:
                    del config['premium_password']
                    with open('config.txt', 'w') as f:
                        json.dump(config, f)
                sys.exit(1)
                
            proxy_response = requests.get(base64.b64decode("aHR0cHM6Ly9pdGJhYXJ0cy5jb20vcHJveHkvZGljZWVrZXkudHh0").decode('utf-8'))
            return proxy_response.text.strip().split("\n"), True
            
        except Exception as e:
            logger.error(f"Error: Failed to get premium proxy: {e}")
            sys.exit(1)
            
    elif choice == "3":
        if not os.path.exists("proxy.txt"):
            logger.error("Error: proxy.txt file not found")
            sys.exit(1)
            
        with open("proxy.txt") as f:
            return f.read().strip().split("\n"), False
            
    else:
        logger.error("Invalid choice!")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
